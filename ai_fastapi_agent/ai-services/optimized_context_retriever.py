"""
Optimized Context Retriever for Token Efficiency and Cost Management
Designed to minimize Gemini API costs while maintaining response quality
"""

import re
import json
from typing import Dict, Any, List, Optional, Tuple
from datetime import datetime, timedelta

# Token counting utilities
def _count_tokens_accurate(text: str) -> int:
    """More accurate token counting for cost estimation"""
    # Gemini uses ~4 characters per token on average
    # This is more conservative for cost estimation
    return max(1, len(text) // 3.5)

def _normalize_text(text: str) -> str:
    """Normalize text for processing"""
    if not text:
        return ""
    text = text.lower()
    text = re.sub(r"\s+", " ", text).strip()
    return text

def _extract_key_terms(text: str, max_terms: int = 10) -> List[str]:
    """Extract key medical terms from text"""
    # Medical keywords that are most relevant
    medical_keywords = [
        'pain', 'headache', 'fever', 'nausea', 'dizziness', 'fatigue', 'cough', 'chest',
        'blood', 'pressure', 'heart', 'diabetes', 'allergy', 'medication', 'treatment',
        'symptom', 'diagnosis', 'chronic', 'acute', 'severe', 'mild', 'chronic'
    ]
    
    words = re.findall(r'\b[a-z]+\b', text.lower())
    # Prioritize medical terms
    key_terms = []
    for word in words:
        if word in medical_keywords and word not in key_terms:
            key_terms.append(word)
        if len(key_terms) >= max_terms:
            break
    
    return key_terms

def _compress_medical_data(data: Dict[str, Any], max_length: int = 200) -> str:
    """Compress medical data to essential information only"""
    if not data:
        return ""
    
    # Priority fields for medical context
    priority_fields = [
        'age', 'gender', 'allergies', 'medicines', 'history', 'symptoms', 
        'diagnosis', 'treatment', 'medication', 'condition'
    ]
    
    compressed = {}
    for field in priority_fields:
        if field in data and data[field]:
            value = data[field]
            if isinstance(value, list):
                compressed[field] = ', '.join(str(v) for v in value[:3])  # Limit to 3 items
            else:
                compressed[field] = str(value)[:50]  # Limit length
    
    result = json.dumps(compressed, separators=(',', ':'))
    return result[:max_length] if len(result) > max_length else result

class OptimizedContextRetriever:
    """
    Token-optimized context retriever for cost management
    - Prioritizes most relevant information
    - Uses intelligent truncation
    - Implements token budgeting
    - Supports file upload context
    """
    
    def __init__(self, firestore_service, max_tokens: int = 2000):
        self.firestore_service = firestore_service
        self.max_tokens = max_tokens  # Conservative token limit
        self.token_budget = {
            'header': 50,
            'profile': 300,
            'biomarkers': 200,
            'treatments': 400,
            'conversation': 300,
            'files': 500,
            'buffer': 250  # Safety buffer
        }
    
    async def retrieve(self, patient_id: str, query_text: str, 
                      uploaded_files: Optional[List[Dict[str, Any]]] = None) -> Dict[str, Any]:
        """
        Retrieve optimized context with token budgeting
        """
        query_terms = _extract_key_terms(query_text)
        context_parts = []
        used_tokens = 0
        
        # 1. Essential header (always included)
        header = f"Patient: {patient_id}\nQuery: {query_text[:100]}\n"
        context_parts.append(header)
        used_tokens += _count_tokens_accurate(header)
        
        # 2. Patient profile (high priority, limited tokens)
        profile_context = await self._get_profile_context(patient_id, query_terms)
        if profile_context and used_tokens + _count_tokens_accurate(profile_context) <= self.max_tokens:
            context_parts.append(profile_context)
            used_tokens += _count_tokens_accurate(profile_context)
        
        # 3. Recent biomarkers (if relevant)
        biomarkers_context = await self._get_biomarkers_context(patient_id, query_terms)
        if biomarkers_context and used_tokens + _count_tokens_accurate(biomarkers_context) <= self.max_tokens:
            context_parts.append(biomarkers_context)
            used_tokens += _count_tokens_accurate(biomarkers_context)
        
        # 4. Active treatments (if relevant)
        treatments_context = await self._get_treatments_context(patient_id, query_terms)
        if treatments_context and used_tokens + _count_tokens_accurate(treatments_context) <= self.max_tokens:
            context_parts.append(treatments_context)
            used_tokens += _count_tokens_accurate(treatments_context)
        
        # 5. Recent conversation (if space allows)
        conversation_context = await self._get_conversation_context(patient_id, query_terms)
        if conversation_context and used_tokens + _count_tokens_accurate(conversation_context) <= self.max_tokens:
            context_parts.append(conversation_context)
            used_tokens += _count_tokens_accurate(conversation_context)
        
        # 6. File upload context (if files provided)
        if uploaded_files:
            files_context = self._process_uploaded_files(uploaded_files, query_terms)
            if files_context and used_tokens + _count_tokens_accurate(files_context) <= self.max_tokens:
                context_parts.append(files_context)
                used_tokens += _count_tokens_accurate(files_context)
        
        # Combine all context
        full_context = "\n".join(context_parts)
        
        return {
            "patient_id": patient_id,
            "query": query_text,
            "trimmed_context_text": full_context,
            "approx_tokens": _count_tokens_accurate(full_context),
            "token_budget_used": used_tokens,
            "token_budget_max": self.max_tokens,
            "efficiency": f"{(used_tokens/self.max_tokens)*100:.1f}%"
        }
    
    async def _get_profile_context(self, patient_id: str, query_terms: List[str]) -> str:
        """Get essential patient profile information"""
        try:
            profile = await self.firestore_service.get_patient_data(patient_id)
            if not profile:
                return ""
            
            # Extract only essential fields
            essential_data = {
                'age': profile.get('age'),
                'gender': profile.get('gender'),
                'allergies': profile.get('allergies', [])[:2],  # Limit to 2 allergies
                'medicines': profile.get('medicines', [])[:3],  # Limit to 3 medicines
                'history': profile.get('history', [])[:2]      # Limit to 2 history items
            }
            
            # Remove None values
            essential_data = {k: v for k, v in essential_data.items() if v}
            
            if not essential_data:
                return ""
            
            context = f"Profile: {_compress_medical_data(essential_data, 150)}"
            return context
            
        except Exception:
            return ""
    
    async def _get_biomarkers_context(self, patient_id: str, query_terms: List[str]) -> str:
        """Get recent biomarkers if relevant to query"""
        # Only include if query mentions biomarkers, blood, lab, etc.
        biomarker_keywords = ['blood', 'lab', 'test', 'biomarker', 'glucose', 'cholesterol', 'pressure']
        if not any(keyword in query_terms for keyword in biomarker_keywords):
            return ""
        
        try:
            biomarkers = await self.firestore_service.get_latest_biomarkers(patient_id)
            if not biomarkers:
                return ""
            
            # Extract only recent and relevant biomarkers
            recent_biomarkers = {}
            for key, value in biomarkers.items():
                if isinstance(value, (int, float)) and value != 0:
                    recent_biomarkers[key] = value
            
            if not recent_biomarkers:
                return ""
            
            context = f"Recent Biomarkers: {_compress_medical_data(recent_biomarkers, 100)}"
            return context
            
        except Exception:
            return ""
    
    async def _get_treatments_context(self, patient_id: str, query_terms: List[str]) -> str:
        """Get active treatments if relevant"""
        try:
            treatments = await self.firestore_service.get_treatment_history(patient_id, limit=2)
            if not treatments:
                return ""
            
            # Get only active or recent treatments
            active_treatments = []
            for treatment in treatments[:2]:  # Limit to 2 treatments
                if treatment.get('status') in ['active', 'ongoing'] or not treatment.get('status'):
                    active_treatments.append({
                        'type': treatment.get('type', 'treatment'),
                        'medication': treatment.get('medication', ''),
                        'start_date': treatment.get('start_date', '')
                    })
            
            if not active_treatments:
                return ""
            
            context = f"Active Treatments: {_compress_medical_data({'treatments': active_treatments}, 150)}"
            return context
            
        except Exception:
            return ""
    
    async def _get_conversation_context(self, patient_id: str, query_terms: List[str]) -> str:
        """Get recent conversation context if relevant"""
        try:
            conversation = await self.firestore_service.get_conversation_history(patient_id, limit=3)
            if not conversation:
                return ""
            
            # Get only recent relevant messages
            recent_messages = []
            for msg in conversation[:3]:
                if msg.get('query_text') and any(term in msg['query_text'].lower() for term in query_terms):
                    recent_messages.append({
                        'query': msg.get('query_text', '')[:50],
                        'timestamp': msg.get('timestamp', '')
                    })
            
            if not recent_messages:
                return ""
            
            context = f"Recent Context: {_compress_medical_data({'messages': recent_messages}, 100)}"
            return context
            
        except Exception:
            return ""
    
    def _process_uploaded_files(self, files: List[Dict[str, Any]], query_terms: List[str]) -> str:
        """Process uploaded files for context"""
        if not files:
            return ""
        
        file_contexts = []
        for file_info in files[:2]:  # Limit to 2 files
            file_type = file_info.get('type', 'unknown')
            file_name = file_info.get('name', 'file')
            
            # Extract relevant content based on file type
            if file_type in ['genetic', 'lab_report', 'medical']:
                # For medical files, include key findings
                content = file_info.get('content', '')
                if content:
                    # Extract key medical terms
                    key_findings = _extract_key_terms(content, 5)
                    if key_findings:
                        file_contexts.append(f"{file_name}: {', '.join(key_findings)}")
            elif file_type == 'image':
                # For images, include description if available
                description = file_info.get('description', '')
                if description:
                    file_contexts.append(f"{file_name}: {description[:50]}")
        
        if not file_contexts:
            return ""
        
        return f"Uploaded Files: {'; '.join(file_contexts)}"
    
    def get_token_usage_estimate(self, context: str) -> Dict[str, Any]:
        """Get detailed token usage estimate for cost calculation"""
        tokens = _count_tokens_accurate(context)
        
        # Cost calculation based on Gemini pricing
        # Input: $0.30 per 1M tokens, Output: $2.50 per 1M tokens
        input_cost = (tokens / 1_000_000) * 0.30
        output_cost_estimate = (tokens / 1_000_000) * 2.50  # Estimate for response
        
        return {
            "input_tokens": tokens,
            "estimated_input_cost": f"${input_cost:.6f}",
            "estimated_output_cost": f"${output_cost_estimate:.6f}",
            "total_estimated_cost": f"${input_cost + output_cost_estimate:.6f}",
            "budget_utilization": f"{(tokens/self.max_tokens)*100:.1f}%"
        }
