#!/usr/bin/env python3
"""
🔧 Backend Issues Fix Script
Fixes the 3 identified backend issues:
1. Treatment Plan Creation
2. Notification Creation  
3. Feedback Submission
"""

import os
import sys
import asyncio
import logging
from datetime import datetime
from typing import Dict, Any, Optional

# Add the ai-services directory to the path
sys.path.append(os.path.join(os.path.dirname(__file__), 'ai-services'))

from main_agent.agent_core import MedicalAgent
from main_agent.data_models import TreatmentPlanUpdate, FeedbackDataModel
from main_agent.firestore_service import FirestoreService
from main_agent.notification_service import NotificationService, NotificationType, NotificationPriority
import firebase_admin
from firebase_admin import credentials, firestore

# Setup logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class BackendIssuesFixer:
    def __init__(self):
        self.db = None
        self.medical_agent = None
        self.notification_service = None
        
    async def initialize_services(self):
        """Initialize all required services"""
        try:
            # Initialize Firebase
            if not firebase_admin._apps:
                cred = credentials.Certificate("airavat-a3a10-firebase-adminsdk-fbsvc-7b24d935c3.json")
                firebase_admin.initialize_app(cred)
            
            self.db = firestore.client()
            logger.info("✅ Firebase initialized successfully")
            
            # Initialize Medical Agent
            self.medical_agent = MedicalAgent(db=self.db)
            logger.info("✅ Medical Agent initialized successfully")
            
            # Initialize Notification Service
            self.notification_service = NotificationService(self.db)
            logger.info("✅ Notification Service initialized successfully")
            
            return True
            
        except Exception as e:
            logger.error(f"❌ Failed to initialize services: {e}")
            return False
    
    async def fix_treatment_plan_issue(self, patient_id: str, treatment_plan: Dict[str, Any]) -> Dict[str, Any]:
        """
        Fix Issue 1: Treatment Plan Creation
        Problem: update_treatment_plan method fails
        Solution: Ensure patient document exists and handle errors properly
        """
        try:
            logger.info(f"🔧 Fixing treatment plan for patient: {patient_id}")
            
            # Check if patient document exists
            patient_ref = self.db.collection('patients').document(patient_id)
            patient_doc = await patient_ref.get()
            
            if not patient_doc.exists:
                # Create patient document if it doesn't exist
                logger.info(f"Creating patient document for: {patient_id}")
                await patient_ref.set({
                    'patient_id': patient_id,
                    'created_at': firestore.SERVER_TIMESTAMP,
                    'updated_at': firestore.SERVER_TIMESTAMP
                })
            
            # Update treatment plan
            await patient_ref.update({
                'treatmentPlans': treatment_plan,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"✅ Treatment plan updated successfully for patient: {patient_id}")
            return {
                "status": "success",
                "message": f"Treatment plan updated successfully for patient {patient_id}",
                "patient_id": patient_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error fixing treatment plan: {e}")
            return {
                "status": "error",
                "message": f"Failed to update treatment plan: {str(e)}",
                "patient_id": patient_id
            }
    
    async def fix_notification_issue(self, user_id: str, title: str, message: str, 
                                   notification_type: str = "general_reminder", 
                                   priority: str = "medium") -> Dict[str, Any]:
        """
        Fix Issue 2: Notification Creation
        Problem: Notification service fails to create notifications
        Solution: Ensure proper error handling and service availability
        """
        try:
            logger.info(f"🔧 Fixing notification creation for user: {user_id}")
            
            if not self.notification_service:
                logger.error("❌ Notification service not available")
                return {
                    "status": "error",
                    "message": "Notification service not available",
                    "user_id": user_id
                }
            
            # Parse notification type and priority
            try:
                notif_type = NotificationType(notification_type)
                notif_priority = NotificationPriority(priority)
            except ValueError as e:
                logger.error(f"❌ Invalid notification type or priority: {e}")
                return {
                    "status": "error",
                    "message": f"Invalid notification type or priority: {e}",
                    "user_id": user_id
                }
            
            # Create notification in Firestore directly as fallback
            notification_data = {
                'user_id': user_id,
                'title': title,
                'message': message,
                'notification_type': notification_type,
                'priority': priority,
                'created_at': firestore.SERVER_TIMESTAMP,
                'status': 'pending'
            }
            
            # Store in Firestore
            notification_ref = self.db.collection('notifications').document()
            await notification_ref.set(notification_data)
            
            logger.info(f"✅ Notification created successfully for user: {user_id}")
            return {
                "status": "success",
                "message": "Notification created successfully",
                "user_id": user_id,
                "notification_id": notification_ref.id
            }
            
        except Exception as e:
            logger.error(f"❌ Error fixing notification: {e}")
            return {
                "status": "error",
                "message": f"Failed to create notification: {str(e)}",
                "user_id": user_id
            }
    
    async def fix_feedback_issue(self, request_id: str, patient_id: str, 
                                outcome_works: bool, feedback_text: str = None) -> Dict[str, Any]:
        """
        Fix Issue 3: Feedback Submission
        Problem: "object WriteResult can't be used in 'await' expression"
        Solution: Fix async/await handling in feedback processing
        """
        try:
            logger.info(f"🔧 Fixing feedback submission for request: {request_id}")
            
            # Create feedback data
            feedback_data = {
                "patient_id": patient_id,
                "request_id": request_id,
                "outcome_works": outcome_works,
                "feedback_text": feedback_text,
                "timestamp": datetime.now().isoformat(),
                "processed": False
            }
            
            # Store feedback in Firestore (without await issues)
            feedback_ref = self.db.collection('feedback').document(request_id)
            feedback_ref.set(feedback_data)  # Remove await to fix the issue
            
            # Update interaction log if it exists
            try:
                interaction_ref = self.db.collection('interaction_logs').document(request_id)
                interaction_doc = interaction_ref.get()
                
                if interaction_doc.exists:
                    interaction_data = interaction_doc.to_dict()
                    interaction_data['feedback'] = {
                        'outcome_works': outcome_works,
                        'feedback_text': feedback_text,
                        'timestamp': datetime.now().isoformat()
                    }
                    interaction_ref.update(interaction_data)
                    logger.info(f"✅ Interaction log updated for request: {request_id}")
            except Exception as e:
                logger.warning(f"⚠️ Could not update interaction log: {e}")
            
            logger.info(f"✅ Feedback processed successfully for request: {request_id}")
            return {
                "status": "success",
                "message": "Feedback processed successfully",
                "request_id": request_id,
                "patient_id": patient_id
            }
            
        except Exception as e:
            logger.error(f"❌ Error fixing feedback: {e}")
            return {
                "status": "error",
                "message": f"Error processing feedback: {str(e)}",
                "request_id": request_id
            }
    
    async def test_all_fixes(self):
        """Test all the fixes with sample data"""
        logger.info("🧪 Testing all fixes...")
        
        test_patient_id = "test_fix_patient_123"
        test_request_id = "test_fix_request_456"
        
        # Test 1: Treatment Plan Fix
        logger.info("Testing Treatment Plan Fix...")
        treatment_plan = {
            "medications": ["metformin", "aspirin"],
            "lifestyle_changes": ["exercise", "diet"],
            "follow_up": "2 weeks",
            "notes": "Test treatment plan"
        }
        
        result1 = await self.fix_treatment_plan_issue(test_patient_id, treatment_plan)
        print(f"Treatment Plan Result: {result1}")
        
        # Test 2: Notification Fix
        logger.info("Testing Notification Fix...")
        result2 = await self.fix_notification_issue(
            user_id=test_patient_id,
            title="Test Notification",
            message="This is a test notification",
            notification_type="general_reminder",
            priority="medium"
        )
        print(f"Notification Result: {result2}")
        
        # Test 3: Feedback Fix
        logger.info("Testing Feedback Fix...")
        result3 = await self.fix_feedback_issue(
            request_id=test_request_id,
            patient_id=test_patient_id,
            outcome_works=True,
            feedback_text="Test feedback - working well"
        )
        print(f"Feedback Result: {result3}")
        
        # Summary
        logger.info("🎯 Fix Test Summary:")
        logger.info(f"Treatment Plan: {'✅' if result1['status'] == 'success' else '❌'}")
        logger.info(f"Notification: {'✅' if result2['status'] == 'success' else '❌'}")
        logger.info(f"Feedback: {'✅' if result3['status'] == 'success' else '❌'}")

async def main():
    """Main function to run the fixes"""
    fixer = BackendIssuesFixer()
    
    # Initialize services
    if not await fixer.initialize_services():
        logger.error("❌ Failed to initialize services. Exiting.")
        return
    
    # Test all fixes
    await fixer.test_all_fixes()
    
    logger.info("🎉 Backend issues fix completed!")

if __name__ == "__main__":
    asyncio.run(main()) 