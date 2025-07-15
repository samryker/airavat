# firestore_service.py
# This module will handle all Firestore interactions for the planner and MCP integration.

import datetime
from firebase_admin import firestore # Import firestore for Query
from typing import Optional, Dict, Any, List

class FirestoreService:
    def __init__(self, db: firestore.client): # Add type hint for db
        self.db = db

    async def get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get complete patient profile data from Firebase.
        This includes all the data from the account screen.
        """
        if not self.db:
            print("Firestore client not available. Cannot retrieve patient data.")
            return None

        try:
            doc_ref = self.db.collection('patients').document(patient_id)
            doc = await doc_ref.get()
            
            if doc.exists:
                data = doc.to_dict()
                # Convert Firestore timestamps to ISO strings for JSON serialization
                if 'updatedAt' in data and data['updatedAt']:
                    data['updatedAt'] = data['updatedAt'].isoformat()
                return data
            else:
                print(f"No patient data found for ID: {patient_id}")
                return None
        except Exception as e:
            print(f"Error retrieving patient data for {patient_id}: {e}")
            return None

    async def get_treatment_history(self, patient_id: str, limit: int = 5) -> List[Dict[str, Any]]:
        """
        Get treatment plans history for the patient.
        """
        if not self.db:
            print("Firestore client not available. Cannot retrieve treatment history.")
            return []

        try:
            # Get treatment plans from patient document
            patient_data = await self.get_patient_data(patient_id)
            if patient_data and 'treatmentPlans' in patient_data:
                plans = patient_data['treatmentPlans']
                # Convert Firestore timestamps
                for plan in plans:
                    if 'startDate' in plan and plan['startDate']:
                        plan['startDate'] = plan['startDate'].isoformat()
                    if 'endDate' in plan and plan['endDate']:
                        plan['endDate'] = plan['endDate'].isoformat()
                return plans[:limit]
            return []
        except Exception as e:
            print(f"Error retrieving treatment history for {patient_id}: {e}")
            return []

    async def get_latest_biomarkers(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """
        Get the latest biomarkers for the patient.
        """
        if not self.db:
            print("Firestore client not available. Cannot retrieve biomarkers.")
            return None

        try:
            query = self.db.collection('biomarkers').document(patient_id).collection('reports').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(1)
            docs_stream = query.stream()
            
            async for doc in docs_stream:
                data = doc.to_dict()
                if 'timestamp' in data and data['timestamp']:
                    data['timestamp'] = data['timestamp'].isoformat()
                return data
            return None
        except Exception as e:
            print(f"Error retrieving biomarkers for {patient_id}: {e}")
            return None

    async def get_conversation_history(self, patient_id: str, limit: int = 10) -> List[Dict[str, Any]]:
        """
        Get conversation history for the patient from interaction logs.
        """
        if not self.db:
            print("Firestore client not available. Cannot retrieve conversation history.")
            return []

        try:
            query = self.db.collection('interaction_logs').where('patient_id', '==', patient_id).order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
            docs_stream = query.stream()
            
            conversations = []
            async for doc in docs_stream:
                data = doc.to_dict()
                if 'timestamp' in data and data['timestamp']:
                    data['timestamp'] = data['timestamp'].isoformat()
                conversations.append(data)
            return conversations
        except Exception as e:
            print(f"Error retrieving conversation history for {patient_id}: {e}")
            return []

    async def update_patient_context(self, patient_id: str, context_data: Dict[str, Any]) -> bool:
        """
        Update patient's MCP context in Firestore.
        """
        if not self.db:
            print("Firestore client not available. Cannot update patient context.")
            return False

        try:
            doc_ref = self.db.collection('patient_context').document(patient_id)
            await doc_ref.set({
                'context_data': context_data,
                'updated_at': datetime.datetime.utcnow(),
                'patient_id': patient_id
            }, merge=True)
            return True
        except Exception as e:
            print(f"Error updating patient context for {patient_id}: {e}")
            return False

    async def get_complete_patient_context(self, patient_id: str) -> Dict[str, Any]:
        """
        Get complete patient context including profile, treatment plans, biomarkers, and conversation history.
        This is the main method for MCP integration.
        """
        context = {
            'patient_id': patient_id,
            'profile': None,
            'treatment_plans': [],
            'biomarkers': None,
            'conversation_history': [],
            'last_updated': datetime.datetime.utcnow().isoformat()
        }

        # Get all data concurrently
        try:
            # Get profile data
            context['profile'] = await self.get_patient_data(patient_id)
            
            # Get treatment plans
            context['treatment_plans'] = await self.get_treatment_history(patient_id)
            
            # Get latest biomarkers
            context['biomarkers'] = await self.get_latest_biomarkers(patient_id)
            
            # Get conversation history
            context['conversation_history'] = await self.get_conversation_history(patient_id)
            
            return context
        except Exception as e:
            print(f"Error getting complete patient context for {patient_id}: {e}")
            return context

    async def store_plan(self, patient_id: str, plan_details: dict, query_text: Optional[str] = None) -> str:
        '''
        Stores a new plan for a patient in their 'plans' subcollection.
        Each plan will have a timestamp and the plan details.
        Args:
            patient_id: The ID of the patient.
            plan_details: A dictionary containing the plan generated by the LLM.
                          e.g., {"plan_text": "...", "goals": [...]}
            query_text: The user query that led to this plan (optional).
        Returns:
            The ID of the newly created plan document.
        '''
        if not self.db:
            print("Firestore client not available. Cannot store plan.")
            return "" # Or raise an exception

        try:
            timestamp = datetime.datetime.utcnow()
            plan_data_to_store = {
                "timestamp": timestamp,
                "plan_details": plan_details, # This would be the direct output from the LLM or a structured version of it
            }
            if query_text:
                plan_data_to_store["triggering_query"] = query_text

            # DocumentReference for the new plan
            # Using patient_id as document ID in 'customer_plans'
            # and then a subcollection 'plans' for multiple plan entries.
            plan_ref = self.db.collection('customer_plans').document(patient_id).collection('plans').document()
            await plan_ref.set(plan_data_to_store)
            print(f"Plan stored for patient {patient_id} with ID: {plan_ref.id}")
            return plan_ref.id
        except Exception as e:
            print(f"Error storing plan for patient {patient_id}: {e}")
            # Consider raising the exception or returning an error indicator
            return ""

    async def get_plan_history(self, patient_id: str, limit: int = 1) -> list[dict]:
        '''
        Retrieves the plan history for a patient, ordered by the most recent first.
        Args:
            patient_id: The ID of the patient.
            limit: The maximum number of past plans to retrieve.
        Returns:
            A list of plan data dictionaries, or an empty list if none found or error.
        '''
        if not self.db:
            print("Firestore client not available. Cannot retrieve plan history.")
            return []

        plans = []
        try:
            # Query the 'plans' subcollection for the given patient_id
            query = self.db.collection('customer_plans').document(patient_id).collection('plans').order_by('timestamp', direction=firestore.Query.DESCENDING).limit(limit)
            docs_stream = query.stream() # Use stream() for async iteration

            # Asynchronously iterate over documents
            async for doc in docs_stream:
                plan_data = doc.to_dict()
                plan_data["plan_id"] = doc.id # Add the document ID to the data
                plans.append(plan_data)
            
            if not plans:
                print(f"No plan history found for patient {patient_id}")
            return plans
        except Exception as e:
            print(f"Error retrieving plan history for patient {patient_id}: {e}")
            return []

    # We might add methods for storing/retrieving dynamic prompt configurations here too.
    # For example:
    # async def get_customer_prompt_config(self, customer_id: str):
    #     # ...
    # async def store_customer_prompt_config(self, customer_id: str, config: dict):
    #     # ... 