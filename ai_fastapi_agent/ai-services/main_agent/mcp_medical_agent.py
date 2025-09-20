"""
MCP-Based Medical Agent for Lifelong Medical Assistant
This agent maintains persistent memory and context across all user interactions.
"""

import os
import asyncio
from typing import Dict, List, Optional, Any
from datetime import datetime, timedelta
import json
import google.generativeai as genai
from dotenv import load_dotenv
import logging

# Module-level logger used throughout this module
logger = logging.getLogger("api")

# Load environment variables (override to ensure .env takes effect)
load_dotenv(override=True)
try:
    _module_env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
    load_dotenv(_module_env_path, override=True)
except Exception:
    pass

# Use the shared Gemini client from gemini_service to avoid reconfiguring the SDK
try:
    from .gemini_service import model as model, is_gemini_available as _gemini_available
    if model is not None:
        logger.info("Gemini client initialized successfully in MCP agent (shared)")
    else:
        logger.warning("Shared Gemini client unavailable - MCP agent will use fallback responses")
except Exception as _e:
    logger.exception(f"Failed to import shared Gemini client: {_e}")
    model = None

# Try to import MCP dependencies, but handle gracefully if not available
try:
    from langchain_google_alloydb_pg import AlloyDBEngine
except ImportError:
    AlloyDBEngine = None

try:
    from langchain_google_cloud_sql_pg import CloudSQLEngine
except ImportError:
    CloudSQLEngine = None

try:
    from langgraph.checkpoint.memory import MemorySaver
    from langgraph.graph import StateGraph, END
    from langgraph.prebuilt import create_react_agent
    LANGGRAPH_AVAILABLE = True
except ImportError:
    MemorySaver = None
    StateGraph = None
    END = None
    create_react_agent = None
    LANGGRAPH_AVAILABLE = False

# from langchain_core.tools import tool
# from langchain_core.messages import HumanMessage, AIMessage
# from langchain_google_genai import ChatGoogleGenerativeAI
# from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder

from .data_models import PatientQuery, AgentResponse, TreatmentSuggestion
from .firestore_service import FirestoreService

# Initialize Gemini model reference (shared)
gemini_model = model
if gemini_model:
    print("✅ Gemini API initialized successfully. AI responses enabled.")
else:
    print("⚠️ Gemini API not available. Using fallback responses.")

# Message classes for compatibility
class HumanMessage:
    def __init__(self, content):
        self.content = content

class AIMessage:
    def __init__(self, content):
        self.content = content

class ChatPromptTemplate:
    def __init__(self, messages):
        self.messages = messages
    
    @classmethod
    def from_messages(cls, messages):
        return cls(messages)
    
    def format_messages(self, **kwargs):
        # Extract the system message and user message
        system_msg = ""
        user_msg = ""
        
        for role, content in self.messages:
            if role == "system":
                system_msg = content
            elif role == "human":
                user_msg = content
        
        # Format the prompt for Gemini
        if system_msg and user_msg:
            return f"{system_msg}\n\n{user_msg}"
        elif user_msg:
            return user_msg
        else:
            return system_msg

class MessagesPlaceholder:
    def __init__(self, variable_name):
        self.variable_name = variable_name

def tool(func):
    """Simple decorator to mark functions as tools"""
    return func

class RealGeminiLLM:
    def __init__(self, model, temperature, max_tokens, convert_system_message_to_human):
        self.model = model
        self.temperature = temperature
        self.max_tokens = max_tokens
        self.convert_system_message_to_human = convert_system_message_to_human
    
    async def ainvoke(self, prompt_or_messages):
        """Async invoke method that actually calls Gemini API"""
        try:
            if gemini_model is None:
                return AIMessage("I'm experiencing technical difficulties. Please try again later or contact your healthcare provider for immediate concerns.")
            
            # Handle both string prompts and message lists
            if isinstance(prompt_or_messages, str):
                prompt = prompt_or_messages
            elif isinstance(prompt_or_messages, dict):
                # Extract messages from the dict
                messages = prompt_or_messages.get("messages", [])
                if messages:
                    # Combine all messages into a single prompt
                    prompt_parts = []
                    for msg in messages:
                        if hasattr(msg, 'content'):
                            prompt_parts.append(msg.content)
                    prompt = "\n\n".join(prompt_parts)
                else:
                    # Handle other dict formats
                    prompt = str(prompt_or_messages)
            else:
                prompt = str(prompt_or_messages)
            
            # Call Gemini API (compat with sync SDK versions)
            if hasattr(gemini_model, "generate_content_async"):
                response = await gemini_model.generate_content_async(prompt)
            else:
                response = await asyncio.to_thread(gemini_model.generate_content, prompt)
            return AIMessage(response.text)
            
        except Exception as e:
            print(f"Error calling Gemini API: {e}")
            return AIMessage("I'm having trouble processing your request right now. Please try again or contact your healthcare provider for immediate concerns.")

class MCPMedicalAgent:
    """
    Lifelong Medical Assistant using MCP Toolbox
    Maintains persistent memory and context for each user
    """
    
    def __init__(self, db_engine: Optional[Any] = None, firestore_service: Optional[FirestoreService] = None):
        self.db_engine = db_engine
        self.firestore_service = firestore_service
        
        # Check if MCP dependencies are available
        if not LANGGRAPH_AVAILABLE:
            print("Warning: LangGraph not available. MCP features will be limited.")
            self.memory_saver = None
            self.agent_graph = None
        else:
            self.memory_saver = MemorySaver()
            self.agent_graph = self._create_agent_graph()
        
        # Use real Gemini LLM instead of hardcoded fallback
        self.llm = RealGeminiLLM(
            model="gemini-1.5-pro",
            temperature=0.1,
            max_tokens=2048,
            convert_system_message_to_human=True
        )
        
    def _create_agent_graph(self) -> Optional[Any]:
        """Create the agent workflow graph with memory persistence"""
        if not LANGGRAPH_AVAILABLE:
            return None
            
        # Define the state schema
        class AgentState:
            messages: List[Any]
            patient_id: str
            current_context: Dict[str, Any]
            treatment_history: List[Dict[str, Any]]
            latest_biomarkers: Dict[str, Any]
            user_preferences: Dict[str, Any]
            session_data: Dict[str, Any]
            
        # Create the graph
        workflow = StateGraph(AgentState)
        
        # Add nodes
        workflow.add_node("load_patient_context", self._load_patient_context)
        workflow.add_node("analyze_query", self._analyze_query)
        workflow.add_node("generate_response", self._generate_response)
        workflow.add_node("update_memory", self._update_memory)
        workflow.add_node("save_context", self._save_context)
        
        # Define edges
        workflow.add_edge("load_patient_context", "analyze_query")
        workflow.add_edge("analyze_query", "generate_response")
        workflow.add_edge("generate_response", "update_memory")
        workflow.add_edge("update_memory", "save_context")
        workflow.add_edge("save_context", END)
        
        # Compile with memory
        return workflow.compile(checkpointer=self.memory_saver)
    
    async def _load_patient_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Load patient's complete medical context and history"""
        patient_id = state["patient_id"]
        
        # Load complete context from Firestore
        if self.firestore_service:
            complete_context = await self.firestore_service.get_complete_patient_context(patient_id)
            
            # Extract individual components
            patient_data = complete_context.get("profile", {})
            treatment_history = complete_context.get("treatment_plans", [])
            biomarkers = complete_context.get("biomarkers", {})
            conversation_history = complete_context.get("conversation_history", [])
            
            # Create a comprehensive context summary for the LLM
            context_summary = self._create_context_summary(
                patient_data, treatment_history, biomarkers, conversation_history
            )
            
            state.update({
                "patient_data": patient_data,
                "treatment_history": treatment_history,
                "latest_biomarkers": biomarkers,
                "conversation_history": conversation_history,
                "context_summary": context_summary,
                "user_preferences": patient_data.get("preferences", {}),
                "session_data": {
                    "session_start": datetime.now().isoformat(),
                    "interaction_count": 0,
                    "total_conversations": len(conversation_history)
                }
            })
        else:
            # Fallback if Firestore service is not available
            state.update({
                "patient_data": {},
                "treatment_history": [],
                "latest_biomarkers": {},
                "conversation_history": [],
                "context_summary": "No patient context available.",
                "user_preferences": {},
                "session_data": {
                    "session_start": datetime.now().isoformat(),
                    "interaction_count": 0,
                    "total_conversations": 0
                }
            })
            
        # Load from MCP database if available (for conversation memory)
        if self.db_engine:
            try:
                async with self.db_engine.connect() as conn:
                    result = await conn.execute(
                        "SELECT context_data FROM patient_context WHERE patient_id = %s ORDER BY updated_at DESC LIMIT 1",
                        (patient_id,)
                    )
                    row = await result.fetchone()
                    if row:
                        mcp_context = json.loads(row[0])
                        state["mcp_memory"] = mcp_context
                    else:
                        state["mcp_memory"] = {}
            except Exception as e:
                print(f"Error loading MCP memory: {e}")
                state["mcp_memory"] = {}
        
        return state
    
    def _create_context_summary(self, patient_data: Dict[str, Any], treatment_history: List[Dict[str, Any]], 
                               biomarkers: Dict[str, Any], conversation_history: List[Dict[str, Any]]) -> str:
        """Create a comprehensive context summary for the LLM"""
        summary_parts = []
        
        # Patient Profile Summary
        if patient_data:
            summary_parts.append("PATIENT PROFILE:")
            if patient_data.get("age"):
                summary_parts.append(f"- Age: {patient_data['age']}")
            if patient_data.get("gender"):
                summary_parts.append(f"- Gender: {patient_data['gender']}")
            if patient_data.get("bmiIndex"):
                summary_parts.append(f"- BMI: {patient_data['bmiIndex']}")
            if patient_data.get("goal"):
                summary_parts.append(f"- Health Goal: {patient_data['goal']}")
            if patient_data.get("allergies"):
                summary_parts.append(f"- Allergies: {patient_data['allergies']}")
            if patient_data.get("medicines"):
                summary_parts.append(f"- Current Medications: {patient_data['medicines']}")
            if patient_data.get("habits"):
                summary_parts.append(f"- Health Habits: {', '.join(patient_data['habits'])}")
            if patient_data.get("history"):
                summary_parts.append(f"- Medical History: {patient_data['history']}")
        
        # Treatment Plans Summary
        if treatment_history:
            summary_parts.append("\nTREATMENT PLANS:")
            for i, plan in enumerate(treatment_history[:3], 1):  # Show last 3 plans
                summary_parts.append(f"- Plan {i}: {plan.get('treatmentName', 'Unknown')}")
                if plan.get('condition'):
                    summary_parts.append(f"  Condition: {plan['condition']}")
                if plan.get('status'):
                    summary_parts.append(f"  Status: {plan['status']}")
        
        # Biomarkers Summary
        if biomarkers:
            summary_parts.append("\nLATEST BIOMARKERS:")
            for key, value in biomarkers.items():
                if key != 'timestamp' and value is not None:
                    summary_parts.append(f"- {key}: {value}")
        
        # Conversation History Summary
        if conversation_history:
            summary_parts.append(f"\nCONVERSATION HISTORY:")
            summary_parts.append(f"- Total conversations: {len(conversation_history)}")
            # Show last 3 conversation topics
            recent_topics = []
            for conv in conversation_history[:3]:
                if conv.get('query_text'):
                    topic = conv['query_text'][:50] + "..." if len(conv['query_text']) > 50 else conv['query_text']
                    recent_topics.append(topic)
            if recent_topics:
                summary_parts.append(f"- Recent topics: {', '.join(recent_topics)}")
        
        return "\n".join(summary_parts) if summary_parts else "No patient context available."
    
    async def _analyze_query(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Analyze the user query and determine required actions"""
        messages = state["messages"]
        current_context = state["current_context"]
        
        # Create analysis prompt
        analysis_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are a medical AI assistant analyzing a patient query. 
            Determine the type of query and what medical context is needed.
            
            Current patient context: {context}
            
            Analyze the query and return a JSON with:
            - query_type: (general_health, symptom_check, treatment_question, medication, emergency, follow_up)
            - urgency_level: (low, medium, high, emergency)
            - required_context: [list of medical data needed]
            - suggested_actions: [list of actions to take]
            """),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        chain = analysis_prompt | self.llm
        result = await chain.ainvoke({
            "context": json.dumps(current_context),
            "messages": messages
        })
        
        try:
            analysis = json.loads(result.content)
            state["query_analysis"] = analysis
        except:
            state["query_analysis"] = {
                "query_type": "general_health",
                "urgency_level": "low",
                "required_context": [],
                "suggested_actions": ["provide_general_advice"]
            }
        
        return state
    
    async def _generate_response(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Generate personalized medical response based on complete patient context"""
        messages = state["messages"]
        patient_data = state["patient_data"]
        treatment_history = state["treatment_history"]
        latest_biomarkers = state["latest_biomarkers"]
        conversation_history = state["conversation_history"]
        context_summary = state["context_summary"]
        mcp_memory = state.get("mcp_memory", {})
        
        # Create comprehensive medical prompt with digital twin context
        medical_prompt = ChatPromptTemplate.from_messages([
            ("system", """You are Airavat, a lifelong medical AI assistant and digital twin. You have complete knowledge of this patient's medical history, treatment plans, and previous conversations. You are their personal health companion who remembers everything about their health journey.

COMPLETE PATIENT CONTEXT:
{context_summary}

PREVIOUS CONVERSATIONS: {conversation_count} total conversations
MCP MEMORY: {mcp_memory}

DIGITAL TWIN GUIDELINES:
1. **Personal Connection**: Address the patient by their context, reference their specific conditions, medications, and goals
2. **Continuity**: Reference previous conversations, treatment plans, and health progress
3. **Personalized Advice**: Consider their specific allergies, medications, habits, and health goals
4. **Treatment Context**: Reference their current treatment plans and suggest modifications if needed
5. **Biomarker Awareness**: Consider their latest biomarker values in your recommendations
6. **Health Journey**: Acknowledge their progress and maintain continuity across sessions
7. **Professional Care**: Always recommend consulting healthcare professionals for serious concerns

Remember: You are this patient's lifelong medical companion. You know their complete health story and should act like a trusted family doctor who remembers every detail."""),
            MessagesPlaceholder(variable_name="messages")
        ])
        
        # Prepare conversation history for context
        recent_conversations = []
        for conv in conversation_history[:3]:  # Last 3 conversations
            if conv.get('query_text') and conv.get('response_text'):
                recent_conversations.append({
                    'query': conv['query_text'],
                    'response': conv['response_text'][:200] + "..." if len(conv['response_text']) > 200 else conv['response_text']
                })
        
        chain = medical_prompt | self.llm
        result = await chain.ainvoke({
            "context_summary": context_summary,
            "conversation_count": len(conversation_history),
            "mcp_memory": json.dumps(mcp_memory),
            "messages": messages
        })
        
        # Add AI response to messages
        messages.append(AIMessage(content=result.content))
        state["messages"] = messages
        state["ai_response"] = result.content
        
        return state
    
    async def _update_memory(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Update the patient's memory and context"""
        patient_id = state["patient_id"]
        messages = state["messages"]
        current_context = state["current_context"]
        
        # Update session data
        state["session_data"]["interaction_count"] += 1
        
        # Update context with new information
        new_context = {
            "last_interaction": datetime.now().isoformat(),
            "total_interactions": current_context.get("total_interactions", 0) + 1,
            "conversation_summary": self._summarize_conversation(messages),
            "key_topics": self._extract_key_topics(messages),
            "treatment_preferences": self._extract_treatment_preferences(messages),
            "health_goals": self._extract_health_goals(messages),
            "session_data": state["session_data"]
        }
        
        state["current_context"] = {**current_context, **new_context}
        
        return state
    
    async def _save_context(self, state: Dict[str, Any]) -> Dict[str, Any]:
        """Save updated context to persistent storage"""
        patient_id = state["patient_id"]
        current_context = state["current_context"]
        
        # Save to MCP database
        if self.db_engine:
            async with self.db_engine.connect() as conn:
                await conn.execute(
                    """INSERT INTO patient_context (patient_id, context_data, updated_at) 
                    VALUES (%s, %s, %s)
                    ON CONFLICT (patient_id) 
                    DO UPDATE SET context_data = %s, updated_at = %s""",
                    (
                        patient_id,
                        json.dumps(current_context),
                        datetime.now(),
                        json.dumps(current_context),
                        datetime.now()
                    )
                )
                await conn.commit()
        
        # Save to Firestore as backup
        if self.firestore_service:
            await self.firestore_service.update_patient_context(patient_id, current_context)
        
        return state
    
    def _summarize_conversation(self, messages: List[Any]) -> str:
        """Create a summary of the conversation for memory"""
        # This would use the LLM to create a concise summary
        return "Conversation summary placeholder"
    
    def _extract_key_topics(self, messages: List[Any]) -> List[str]:
        """Extract key health topics from conversation"""
        return ["general_health", "wellness"]
    
    def _extract_treatment_preferences(self, messages: List[Any]) -> Dict[str, Any]:
        """Extract patient's treatment preferences"""
        return {"preferred_communication": "conversational", "detail_level": "moderate"}
    
    def _extract_health_goals(self, messages: List[Any]) -> List[str]:
        """Extract patient's health goals"""
        return ["maintain_health", "prevent_illness"]
    
    async def process_query(self, patient_query: PatientQuery) -> AgentResponse:
        """Process a patient query with lifelong memory and context"""
        
        # If agent_graph is not available, use fallback implementation
        if not self.agent_graph:
            return await self._fallback_process_query(patient_query)
        
        # Create initial state
        initial_state = {
            "messages": [HumanMessage(content=patient_query.query_text)],
            "patient_id": patient_query.patient_id,
            "current_context": {},
            "treatment_history": [],
            "latest_biomarkers": {},
            "user_preferences": {},
            "session_data": {}
        }
        
        # Run the agent workflow
        config = {"configurable": {"thread_id": patient_query.patient_id}}
        result = await self.agent_graph.ainvoke(initial_state, config)
        
        # Extract response
        ai_response = result.get("ai_response", "I'm here to help with your health questions.")
        
        return AgentResponse(
            request_id=patient_query.request_id,
            response_text=ai_response,
            suggestions=[
                TreatmentSuggestion(
                    suggestion_text=ai_response,
                    confidence_score=0.9,
                    supporting_evidence_ids=None
                )
            ]
        )
    
    async def _fallback_process_query(self, patient_query: PatientQuery) -> AgentResponse:
        """Fallback implementation when MCP agent graph is not available"""
        try:
            # Get patient context for personalized response
            patient_context = {}
            if self.firestore_service:
                try:
                    patient_context = await self.firestore_service.get_complete_patient_context(patient_query.patient_id)
                except Exception as e:
                    print(f"Error getting patient context: {e}")
            
            # Create a comprehensive prompt with patient context
            context_summary = self._create_context_summary(
                patient_context.get("profile", {}),
                patient_context.get("treatment_plans", []),
                patient_context.get("biomarkers", {}),
                patient_context.get("conversation_history", [])
            )
            
            prompt = f"""You are Airavat, a medical AI assistant and digital twin. You have access to the patient's medical context and should provide personalized, caring responses.

PATIENT CONTEXT:
{context_summary}

PATIENT QUERY: "{patient_query.query_text}"

Please provide a helpful, personalized response that:
1. Addresses the specific query with empathy and care
2. References the patient's medical context when relevant
3. Provides evidence-based information
4. Always recommends consulting healthcare professionals for serious concerns
5. Is conversational yet professional
6. Offers actionable next steps when appropriate

Response:"""
            
            result = await self.llm.ainvoke(prompt)
            ai_response = result.content
            
            # Generate dynamic suggestions based on the response
            suggestions = await self._generate_dynamic_suggestions(ai_response, patient_query.query_text, patient_context)
            
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text=ai_response,
                suggestions=suggestions
            )
        except Exception as e:
            print(f"Error in fallback process_query: {e}")
            return AgentResponse(
                request_id=patient_query.request_id,
                response_text="I'm experiencing technical difficulties right now. Please try again in a few moments or contact your healthcare provider for immediate concerns.",
                suggestions=[
                    TreatmentSuggestion(
                        suggestion_text="Try again in a few moments",
                        confidence_score=0.7,
                        supporting_evidence_ids=None
                    ),
                    TreatmentSuggestion(
                        suggestion_text="Contact your healthcare provider for immediate concerns",
                        confidence_score=0.9,
                        supporting_evidence_ids=None
                    )
                ]
            )
    
    async def _generate_dynamic_suggestions(self, response_text: str, original_query: str, patient_context: Dict[str, Any]) -> List[TreatmentSuggestion]:
        """Generate dynamic suggestions based on the response and patient context"""
        try:
            if gemini_model is None:
                return self._get_fallback_suggestions()
            
            suggestion_prompt = f"""
            Based on this medical response and the patient's query, generate 3-5 actionable suggestions.
            
            Patient Query: "{original_query}"
            AI Response: "{response_text}"
            
            Generate suggestions that are:
            1. Relevant to the specific query and response
            2. Actionable and practical
            3. Appropriate for the patient's context
            4. Include confidence scores (0.0-1.0)
            
            Return as JSON array with format:
            [
                {{
                    "suggestion_text": "specific actionable suggestion",
                    "confidence_score": 0.8
                }}
            ]
            """
            
            if hasattr(gemini_model, "generate_content_async"):
                response = await gemini_model.generate_content_async(suggestion_prompt)
            else:
                response = await asyncio.to_thread(gemini_model.generate_content, suggestion_prompt)
            
            try:
                suggestions_data = json.loads(response.text)
                if isinstance(suggestions_data, list):
                    return [
                        TreatmentSuggestion(
                            suggestion_text=item.get("suggestion_text", ""),
                            confidence_score=item.get("confidence_score", 0.7)
                        )
                        for item in suggestions_data
                        if item.get("suggestion_text")
                    ]
            except (json.JSONDecodeError, KeyError) as e:
                print(f"Error parsing suggestions: {e}")
            
            return self._get_fallback_suggestions()
            
        except Exception as e:
            print(f"Error generating dynamic suggestions: {e}")
            return self._get_fallback_suggestions()
    
    def _get_fallback_suggestions(self) -> List[TreatmentSuggestion]:
        """Get basic fallback suggestions when dynamic generation fails"""
        return [
            TreatmentSuggestion(
                suggestion_text="Schedule a consultation with your healthcare provider",
                confidence_score=0.8,
                supporting_evidence_ids=None
            ),
            TreatmentSuggestion(
                suggestion_text="Monitor your symptoms and keep a detailed log",
                confidence_score=0.7,
                supporting_evidence_ids=None
            ),
            TreatmentSuggestion(
                suggestion_text="Follow up with your doctor for personalized advice",
                confidence_score=0.8,
                supporting_evidence_ids=None
            )
        ]
    
    async def get_patient_memory(self, patient_id: str) -> Dict[str, Any]:
        """
        Get patient's memory and context from MCP system
        """
        try:
            if self.agent_graph and self.memory_saver:
                # Get memory from LangGraph checkpointer
                memory = await self.memory_saver.get_memory(patient_id)
                return {
                    'patient_id': patient_id,
                    'memory': memory,
                    'has_memory': bool(memory)
                }
            else:
                # Fallback to Firestore
                if self.firestore_service:
                    context = await self.firestore_service.get_complete_patient_context(patient_id)
                    return {
                        'patient_id': patient_id,
                        'context': context,
                        'has_memory': bool(context)
                    }
                return {
                    'patient_id': patient_id,
                    'memory': {},
                    'has_memory': False
                }
        except Exception as e:
            print(f"Error getting patient memory: {e}")
            return {
                'patient_id': patient_id,
                'memory': {},
                'has_memory': False,
                'error': str(e)
            }

    async def get_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """
        Get patient's complete context for LLM integration
        """
        try:
            if self.firestore_service:
                complete_context = await self.firestore_service.get_complete_patient_context(patient_id)
                return {
                    'patient_id': patient_id,
                    'context': complete_context,
                    'has_context': bool(complete_context)
                }
            else:
                return {
                    'patient_id': patient_id,
                    'context': {},
                    'has_context': False
                }
        except Exception as e:
            print(f"Error getting patient context: {e}")
            return {
                'patient_id': patient_id,
                'context': {},
                'has_context': False,
                'error': str(e)
            }
    
    async def update_treatment_plan(self, patient_id: str, treatment_plan: Dict[str, Any]) -> bool:
        """Update patient's treatment plan in memory"""
        try:
            memory = await self.get_patient_memory(patient_id)
            memory["current_treatment_plan"] = treatment_plan
            memory["treatment_plan_updated"] = datetime.now().isoformat()
            
            if self.db_engine:
                async with self.db_engine.connect() as conn:
                    await conn.execute(
                        """INSERT INTO patient_context (patient_id, context_data, updated_at) 
                        VALUES (%s, %s, %s)
                        ON CONFLICT (patient_id) 
                        DO UPDATE SET context_data = %s, updated_at = %s""",
                        (
                            patient_id,
                            json.dumps(memory),
                            datetime.now(),
                            json.dumps(memory),
                            datetime.now()
                        )
                    )
                    await conn.commit()
            
            return True
        except Exception as e:
            print(f"Error updating treatment plan: {e}")
            return False 