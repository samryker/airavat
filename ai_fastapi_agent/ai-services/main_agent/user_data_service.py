import os
import json
import logging
import asyncio
from typing import Dict, List, Optional, Any, Union
from datetime import datetime, timedelta
import firebase_admin
from firebase_admin import firestore, auth
from dataclasses import dataclass, asdict
from enum import Enum
import uuid
from .email_service import EmailService

logger = logging.getLogger(__name__)

class UserRole(Enum):
    PATIENT = "patient"
    DOCTOR = "doctor"
    CAREGIVER = "caregiver"
    ADMIN = "admin"

class TreatmentStatus(Enum):
    PLANNED = "Planned"
    ONGOING = "Ongoing"
    COMPLETED = "Completed"
    PAUSED = "Paused"
    CANCELLED = "Cancelled"

@dataclass
class TreatmentPlan:
    """Matches the Flutter TreatmentPlan class structure"""
    treatmentName: str
    condition: Optional[str] = None
    startDate: Optional[datetime] = None
    endDate: Optional[datetime] = None
    status: Optional[str] = None

@dataclass
class DoctorContact:
    """Doctor contact information"""
    doctor_id: str
    name: str
    email: str
    specialty: str
    phone: Optional[str] = None
    hospital: Optional[str] = None
    notes: Optional[str] = None
    added_date: datetime = None

@dataclass
class MedicalHistory:
    """Medical history entry"""
    entry_id: str
    date: datetime
    condition: str
    diagnosis: str
    treatment: str
    doctor: str
    notes: Optional[str] = None
    severity: str = "medium"  # low, medium, high

@dataclass
class UserProfile:
    """Complete user profile matching Flutter frontend fields"""
    # Basic Information (from Flutter account_screen.dart)
    user_id: str
    email: str
    display_name: Optional[str] = None
    
    # Personal Information (exact field names from Flutter)
    bmiIndex: Optional[str] = None  # Underweight, Normal, Overweight, Obese
    age: Optional[int] = None
    race: Optional[str] = None  # Asian, Black, White, Hispanic, Other
    gender: Optional[str] = None  # Male, Female, Other
    
    # Medical Information (exact field names from Flutter)
    medicines: str = ""  # comma-separated string
    allergies: str = ""  # comma-separated string
    history: str = ""  # Significant Health History
    goal: str = ""  # Health Goal
    
    # Lifestyle Habits (exact field names from Flutter)
    habits: List[str] = None  # Smoking, Unsafe Sex, Alcohol Abuse, etc.
    
    # Treatment Plans (exact structure from Flutter)
    treatmentPlans: List[Dict[str, Any]] = None
    
    # Additional fields for enhanced functionality
    role: UserRole = UserRole.PATIENT
    created_date: datetime = None
    updated_date: datetime = None
    last_login: Optional[datetime] = None
    is_active: bool = True
    email_verified: bool = False
    
    # Doctor contacts (new feature)
    doctor_contacts: List[Dict[str, Any]] = None
    
    # Medical history (new feature)
    medical_history: List[Dict[str, Any]] = None
    
    # Emergency contacts (new feature)
    emergency_contacts: List[Dict[str, Any]] = None
    
    # Insurance information (new feature)
    insurance_info: Dict[str, Any] = None
    
    # Preferences
    notification_preferences: Dict[str, Any] = None
    privacy_settings: Dict[str, Any] = None

class UserDataService:
    """
    Comprehensive user data service for Airavat Medical AI Assistant
    Properly maps to existing Firebase collections and Flutter frontend fields
    """
    
    def __init__(self, db: firestore.client = None):
        # Initialize Firebase
        self.db = db
        if not self.db:
            try:
                self.db = firestore.client()
            except Exception as e:
                logger.error(f"Failed to initialize Firestore: {e}")
                self.db = None
        
        # Initialize email service
        try:
            self.email_service = EmailService()
        except Exception as e:
            logger.error(f"Failed to initialize EmailService: {e}")
            self.email_service = None
        
        # Field mappings to ensure consistency
        self.field_mappings = {
            # Flutter frontend fields -> Firebase fields (exact matches)
            'bmiIndex': 'bmiIndex',
            'medicines': 'medicines',
            'allergies': 'allergies',
            'history': 'history',
            'goal': 'goal',
            'age': 'age',
            'race': 'race',
            'gender': 'gender',
            'habits': 'habits',
            'treatmentPlans': 'treatmentPlans',
            'updatedAt': 'updated_date'
        }
        
        # Valid values for dropdown fields (from Flutter)
        self.valid_values = {
            'bmiIndex': ['Underweight', 'Normal', 'Overweight', 'Obese'],
            'race': ['Asian', 'Black', 'White', 'Hispanic', 'Other'],
            'gender': ['Male', 'Female', 'Other'],
            'habits': [
                'Smoking', 'Unsafe Sex', 'Alcohol Abuse', 'Teetotaler', 
                'Drug Use', 'Sugary Foods'
            ],
            'treatment_status': [
                'Planned', 'Ongoing', 'Completed', 'Paused', 'Cancelled'
            ],
            'conditions': [
                'Cancer - Breast', 'Cancer - Lung', 'Cancer - Prostate',
                'Cancer - Colorectal', 'Cancer - Melanoma', 'Cancer - Leukemia',
                'Cancer - Lymphoma', 'Diabetes Type 1', 'Diabetes Type 2',
                'Hypertension', 'Heart Disease', 'Asthma', 'Arthritis',
                'Chronic Kidney Disease', 'Other Cancer', 'Other Chronic Illness'
            ]
        }
    
    async def get_user_profile(self, user_id: str) -> Optional[UserProfile]:
        """Get complete user profile from Firebase"""
        try:
            if not self.db:
                return None
            
            # Get user data from patients collection (matches Flutter structure)
            doc = await self.db.collection('patients').document(user_id).get()
            
            if not doc.exists:
                return None
            
            data = doc.to_dict()
            
            # Create UserProfile object with exact field mapping
            profile = UserProfile(
                user_id=user_id,
                email=data.get('email', ''),
                display_name=data.get('display_name'),
                
                # Personal Information (exact Flutter field names)
                bmiIndex=data.get('bmiIndex'),
                age=data.get('age'),
                race=data.get('race'),
                gender=data.get('gender'),
                
                # Medical Information (exact Flutter field names)
                medicines=data.get('medicines', ''),
                allergies=data.get('allergies', ''),
                history=data.get('history', ''),
                goal=data.get('goal', ''),
                
                # Lifestyle Habits (exact Flutter field names)
                habits=data.get('habits', []),
                
                # Treatment Plans (exact Flutter structure)
                treatmentPlans=data.get('treatmentPlans', []),
                
                # Additional fields
                created_date=data.get('createdAt'),
                updated_date=data.get('updatedAt'),
                last_login=data.get('lastLogin'),
                is_active=data.get('isActive', True),
                email_verified=data.get('emailVerified', False),
                
                # New features
                doctor_contacts=data.get('doctor_contacts', []),
                medical_history=data.get('medical_history', []),
                emergency_contacts=data.get('emergency_contacts', []),
                insurance_info=data.get('insurance_info', {}),
                notification_preferences=data.get('notification_preferences', {}),
                privacy_settings=data.get('privacy_settings', {})
            )
            
            return profile
            
        except Exception as e:
            logger.error(f"Failed to get user profile: {e}")
            return None
    
    async def save_user_profile(self, profile: UserProfile) -> bool:
        """Save user profile to Firebase with exact field mapping"""
        try:
            if not self.db:
                return False
            
            # Prepare data with exact Flutter field names
            data = {
                # Basic information
                'email': profile.email,
                'display_name': profile.display_name,
                
                # Personal Information (exact Flutter field names)
                'bmiIndex': profile.bmiIndex,
                'age': profile.age,
                'race': profile.race,
                'gender': profile.gender,
                
                # Medical Information (exact Flutter field names)
                'medicines': profile.medicines,
                'allergies': profile.allergies,
                'history': profile.history,
                'goal': profile.goal,
                
                # Lifestyle Habits (exact Flutter field names)
                'habits': profile.habits or [],
                
                # Treatment Plans (exact Flutter structure)
                'treatmentPlans': profile.treatmentPlans or [],
                
                # Additional fields
                'createdAt': profile.created_date or firestore.SERVER_TIMESTAMP,
                'updatedAt': firestore.SERVER_TIMESTAMP,
                'lastLogin': profile.last_login,
                'isActive': profile.is_active,
                'emailVerified': profile.email_verified,
                
                # New features
                'doctor_contacts': profile.doctor_contacts or [],
                'medical_history': profile.medical_history or [],
                'emergency_contacts': profile.emergency_contacts or [],
                'insurance_info': profile.insurance_info or {},
                'notification_preferences': profile.notification_preferences or {},
                'privacy_settings': profile.privacy_settings or {}
            }
            
            # Save to patients collection (matches Flutter structure)
            await self.db.collection('patients').document(profile.user_id).set(
                data, merge=True
            )
            
            logger.info(f"User profile saved: {profile.user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to save user profile: {e}")
            return False
    
    async def update_user_field(self, user_id: str, field_name: str, value: Any) -> bool:
        """Update a specific user field with validation"""
        try:
            if not self.db:
                return False
            
            # Validate field name exists in mappings
            if field_name not in self.field_mappings:
                logger.error(f"Invalid field name: {field_name}")
                return False
            
            # Validate value for dropdown fields
            if field_name in self.valid_values and value not in self.valid_values[field_name]:
                logger.error(f"Invalid value for {field_name}: {value}")
                return False
            
            # Update field
            update_data = {
                self.field_mappings[field_name]: value,
                'updatedAt': firestore.SERVER_TIMESTAMP
            }
            
            await self.db.collection('patients').document(user_id).update(update_data)
            
            logger.info(f"Updated field {field_name} for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update user field: {e}")
            return False
    
    async def add_treatment_plan(self, user_id: str, treatment_plan: TreatmentPlan) -> bool:
        """Add a treatment plan (matches Flutter structure)"""
        try:
            if not self.db:
                return False
            
            # Convert to dictionary format (matches Flutter TreatmentPlan.toMap())
            plan_data = {
                'treatmentName': treatment_plan.treatmentName,
                'condition': treatment_plan.condition,
                'startDate': firestore.SERVER_TIMESTAMP if treatment_plan.startDate else None,
                'endDate': firestore.SERVER_TIMESTAMP if treatment_plan.endDate else None,
                'status': treatment_plan.status
            }
            
            # Get current treatment plans
            doc = await self.db.collection('patients').document(user_id).get()
            current_plans = doc.to_dict().get('treatmentPlans', []) if doc.exists else []
            
            # Add new plan
            current_plans.append(plan_data)
            
            # Update the field
            await self.db.collection('patients').document(user_id).update({
                'treatmentPlans': current_plans,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Treatment plan added for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add treatment plan: {e}")
            return False
    
    async def update_treatment_plan(self, user_id: str, plan_index: int, 
                                  treatment_plan: TreatmentPlan) -> bool:
        """Update a treatment plan at specific index"""
        try:
            if not self.db:
                return False
            
            # Get current treatment plans
            doc = await self.db.collection('patients').document(user_id).get()
            if not doc.exists:
                return False
            
            current_plans = doc.to_dict().get('treatmentPlans', [])
            
            if plan_index >= len(current_plans):
                logger.error(f"Invalid plan index: {plan_index}")
                return False
            
            # Update the plan
            plan_data = {
                'treatmentName': treatment_plan.treatmentName,
                'condition': treatment_plan.condition,
                'startDate': firestore.SERVER_TIMESTAMP if treatment_plan.startDate else None,
                'endDate': firestore.SERVER_TIMESTAMP if treatment_plan.endDate else None,
                'status': treatment_plan.status
            }
            
            current_plans[plan_index] = plan_data
            
            # Update the field
            await self.db.collection('patients').document(user_id).update({
                'treatmentPlans': current_plans,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Treatment plan updated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update treatment plan: {e}")
            return False
    
    async def remove_treatment_plan(self, user_id: str, plan_index: int) -> bool:
        """Remove a treatment plan at specific index"""
        try:
            if not self.db:
                return False
            
            # Get current treatment plans
            doc = await self.db.collection('patients').document(user_id).get()
            if not doc.exists:
                return False
            
            current_plans = doc.to_dict().get('treatmentPlans', [])
            
            if plan_index >= len(current_plans):
                logger.error(f"Invalid plan index: {plan_index}")
                return False
            
            # Remove the plan
            current_plans.pop(plan_index)
            
            # Update the field
            await self.db.collection('patients').document(user_id).update({
                'treatmentPlans': current_plans,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Treatment plan removed for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to remove treatment plan: {e}")
            return False
    
    async def add_doctor_contact(self, user_id: str, doctor_contact: DoctorContact) -> bool:
        """Add a doctor contact"""
        try:
            if not self.db:
                return False
            
            # Get current doctor contacts
            doc = await self.db.collection('patients').document(user_id).get()
            current_contacts = doc.to_dict().get('doctor_contacts', []) if doc.exists else []
            
            # Add new contact
            contact_data = asdict(doctor_contact)
            contact_data['added_date'] = firestore.SERVER_TIMESTAMP
            current_contacts.append(contact_data)
            
            # Update the field
            await self.db.collection('patients').document(user_id).update({
                'doctor_contacts': current_contacts,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Doctor contact added for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add doctor contact: {e}")
            return False
    
    async def add_medical_history(self, user_id: str, medical_history: MedicalHistory) -> bool:
        """Add a medical history entry"""
        try:
            if not self.db:
                return False
            
            # Get current medical history
            doc = await self.db.collection('patients').document(user_id).get()
            current_history = doc.to_dict().get('medical_history', []) if doc.exists else []
            
            # Add new entry
            history_data = asdict(medical_history)
            history_data['date'] = firestore.SERVER_TIMESTAMP
            current_history.append(history_data)
            
            # Update the field
            await self.db.collection('patients').document(user_id).update({
                'medical_history': current_history,
                'updatedAt': firestore.SERVER_TIMESTAMP
            })
            
            logger.info(f"Medical history added for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to add medical history: {e}")
            return False
    
    async def get_user_biomarkers(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user biomarkers from twin_customizations collection"""
        try:
            if not self.db:
                return None
            
            doc = await self.db.collection('twin_customizations').document(user_id).get()
            
            if doc.exists:
                data = doc.to_dict()
                return data.get('biomarkers', {})
            
            return None
            
        except Exception as e:
            logger.error(f"Failed to get user biomarkers: {e}")
            return None
    
    async def update_user_biomarkers(self, user_id: str, biomarkers: Dict[str, Any]) -> bool:
        """Update user biomarkers in twin_customizations collection"""
        try:
            if not self.db:
                return False
            
            await self.db.collection('twin_customizations').document(user_id).set({
                'userId': user_id,
                'biomarkers': biomarkers,
                'lastUpdated': firestore.SERVER_TIMESTAMP
            }, merge=True)
            
            logger.info(f"Biomarkers updated for user {user_id}")
            return True
            
        except Exception as e:
            logger.error(f"Failed to update biomarkers: {e}")
            return False
    
    async def validate_user_data(self, user_id: str) -> Dict[str, Any]:
        """Validate user data completeness and return validation results"""
        try:
            profile = await self.get_user_profile(user_id)
            if not profile:
                return {'valid': False, 'missing_fields': ['profile']}
            
            missing_fields = []
            validation_issues = []
            
            # Check required fields
            required_fields = ['bmiIndex', 'age', 'race', 'gender']
            for field in required_fields:
                if not getattr(profile, field):
                    missing_fields.append(field)
            
            # Check medical information
            if not profile.medicines and not profile.allergies and not profile.history:
                validation_issues.append("No medical information provided")
            
            # Check treatment plans
            if not profile.treatmentPlans:
                validation_issues.append("No treatment plans added")
            
            # Check habits
            if not profile.habits:
                validation_issues.append("No lifestyle habits selected")
            
            return {
                'valid': len(missing_fields) == 0 and len(validation_issues) == 0,
                'missing_fields': missing_fields,
                'validation_issues': validation_issues,
                'completeness_percentage': self._calculate_completeness(profile)
            }
            
        except Exception as e:
            logger.error(f"Failed to validate user data: {e}")
            return {'valid': False, 'error': str(e)}
    
    def _calculate_completeness(self, profile: UserProfile) -> float:
        """Calculate profile completeness percentage"""
        total_fields = 10  # Total number of important fields
        filled_fields = 0
        
        if profile.bmiIndex: filled_fields += 1
        if profile.age: filled_fields += 1
        if profile.race: filled_fields += 1
        if profile.gender: filled_fields += 1
        if profile.medicines: filled_fields += 1
        if profile.allergies: filled_fields += 1
        if profile.history: filled_fields += 1
        if profile.goal: filled_fields += 1
        if profile.habits: filled_fields += 1
        if profile.treatmentPlans: filled_fields += 1
        
        return (filled_fields / total_fields) * 100
    
    async def get_user_statistics(self, user_id: str) -> Dict[str, Any]:
        """Get user statistics and insights"""
        try:
            profile = await self.get_user_profile(user_id)
            if not profile:
                return {}
            
            biomarkers = await self.get_user_biomarkers(user_id)
            
            stats = {
                'profile_completeness': self._calculate_completeness(profile),
                'treatment_plans_count': len(profile.treatmentPlans or []),
                'active_treatments': len([p for p in profile.treatmentPlans or [] 
                                       if p.get('status') == 'Ongoing']),
                'doctor_contacts_count': len(profile.doctor_contacts or []),
                'medical_history_entries': len(profile.medical_history or []),
                'lifestyle_habits_count': len(profile.habits or []),
                'has_biomarkers': biomarkers is not None,
                'last_updated': profile.updated_date.isoformat() if profile.updated_date else None
            }
            
            return stats
            
        except Exception as e:
            logger.error(f"Failed to get user statistics: {e}")
            return {}

# Global user data service instance
user_data_service = UserDataService() 