import os
import asyncio
import logging
from datetime import datetime, timedelta
from typing import Dict, List, Optional, Any
from dataclasses import dataclass, asdict
from enum import Enum
import firebase_admin
from firebase_admin import firestore
from .email_service import EmailService, EmailType

logger = logging.getLogger(__name__)

class NotificationType(Enum):
    MEDICATION_REMINDER = "medication_reminder"
    APPOINTMENT_REMINDER = "appointment_reminder"
    HEALTH_CHECK = "health_check"
    TREATMENT_UPDATE = "treatment_update"
    BIOMARKER_ALERT = "biomarker_alert"
    GENERAL_REMINDER = "general_reminder"
    EMERGENCY_ALERT = "emergency_alert"

class NotificationPriority(Enum):
    LOW = "low"
    MEDIUM = "medium"
    HIGH = "high"
    URGENT = "urgent"

@dataclass
class Notification:
    id: str
    patient_id: str
    type: NotificationType
    title: str
    message: str
    priority: NotificationPriority
    scheduled_time: datetime
    sent_time: Optional[datetime] = None
    status: str = "pending"  # pending, sent, failed, cancelled
    metadata: Dict[str, Any] = None
    created_at: datetime = None

@dataclass
class Reminder:
    id: str
    patient_id: str
    title: str
    description: str
    reminder_time: datetime
    frequency: str = "once"  # once, daily, weekly, monthly
    is_active: bool = True
    notification_type: NotificationType = NotificationType.GENERAL_REMINDER
    metadata: Dict[str, Any] = None
    created_at: datetime = None

class NotificationService:
    """
    Comprehensive notification and reminder service for Airavat Medical AI Assistant
    Handles scheduling, sending, and managing notifications and reminders
    """
    
    def __init__(self, db: firestore.client = None):
        self.db = db
        self.email_service = EmailService()
        self._notification_task = None
        self._scheduler_started = False
    
    async def _ensure_scheduler_started(self):
        """Ensure the notification scheduler is started"""
        if not self._scheduler_started and self.db:
            self._notification_task = asyncio.create_task(self._start_notification_scheduler())
            self._scheduler_started = True
    
    async def _start_notification_scheduler(self):
        """Start the background task for processing scheduled notifications"""
        while True:
            try:
                await self._process_pending_notifications()
                await asyncio.sleep(60)  # Check every minute
            except Exception as e:
                logger.error(f"Error in notification scheduler: {e}")
                await asyncio.sleep(300)  # Wait 5 minutes on error
    
    async def _process_pending_notifications(self):
        """Process all pending notifications that are due"""
        try:
            if not self.db:
                return
            
            await self._ensure_scheduler_started()
            
            now = datetime.utcnow()
            
            # Get pending notifications that are due
            notifications_ref = self.db.collection('notifications')
            query = notifications_ref.where('status', '==', 'pending').where('scheduled_time', '<=', now)
            docs = query.get()
            
            for doc in docs:
                notification_data = doc.to_dict()
                await self._send_notification(doc.id, notification_data)
                
        except Exception as e:
            logger.error(f"Error processing pending notifications: {e}")
    
    async def _send_notification(self, notification_id: str, notification_data: Dict[str, Any]):
        """Send a single notification"""
        try:
            patient_id = notification_data.get('patient_id')
            notification_type = NotificationType(notification_data.get('type'))
            
            # Get patient data for email
            patient_data = await self._get_patient_data(patient_id)
            if not patient_data:
                logger.error(f"Patient data not found for notification {notification_id}")
                return
            
            # Send email notification
            email_sent = await self._send_email_notification(
                patient_data, notification_data, notification_type
            )
            
            # Update notification status
            status = 'sent' if email_sent else 'failed'
            await self._update_notification_status(notification_id, status)
            
            logger.info(f"Notification {notification_id} sent with status: {status}")
            
        except Exception as e:
            logger.error(f"Error sending notification {notification_id}: {e}")
            await self._update_notification_status(notification_id, 'failed')
    
    async def _send_email_notification(self, patient_data: Dict[str, Any], 
                                     notification_data: Dict[str, Any], 
                                     notification_type: NotificationType) -> bool:
        """Send email notification based on type"""
        try:
            email = patient_data.get('email')
            user_name = patient_data.get('display_name', 'User')
            
            if notification_type == NotificationType.MEDICATION_REMINDER:
                return await self.email_service.send_medication_reminder(
                    patient_data.get('user_id', ''),
                    email,
                    user_name,
                    notification_data.get('title', ''),
                    notification_data.get('message', ''),
                    notification_data.get('metadata', {})
                )
            elif notification_type == NotificationType.APPOINTMENT_REMINDER:
                return await self.email_service.send_appointment_reminder(
                    patient_data.get('user_id', ''),
                    email,
                    user_name,
                    notification_data.get('title', ''),
                    notification_data.get('message', ''),
                    notification_data.get('metadata', {})
                )
            else:
                # Send generic medical alert
                return await self.email_service.send_medical_alert(
                    patient_data.get('user_id', ''),
                    email,
                    user_name,
                    notification_data.get('title', ''),
                    notification_data.get('message', ''),
                    notification_data.get('metadata', {}).get('recommended_actions', []),
                    notification_data.get('priority', 'medium')
                )
                
        except Exception as e:
            logger.error(f"Error sending email notification: {e}")
            return False
    
    async def _get_patient_data(self, patient_id: str) -> Optional[Dict[str, Any]]:
        """Get patient data from Firestore"""
        try:
            if not self.db:
                return None
            
            doc = self.db.collection('patients').document(patient_id).get()
            if doc.exists:
                return doc.to_dict()
            return None
        except Exception as e:
            logger.error(f"Error getting patient data: {e}")
            return None
    
    async def _update_notification_status(self, notification_id: str, status: str):
        """Update notification status in Firestore"""
        try:
            if not self.db:
                return
            
            update_data = {
                'status': status,
                'sent_time': firestore.SERVER_TIMESTAMP if status == 'sent' else None
            }
            
            self.db.collection('notifications').document(notification_id).update(update_data)
            
        except Exception as e:
            logger.error(f"Error updating notification status: {e}")
    
    async def schedule_notification(self, notification: Notification) -> bool:
        """Schedule a new notification"""
        try:
            if not self.db:
                return False
            
            await self._ensure_scheduler_started()
            
            notification_data = asdict(notification)
            notification_data['created_at'] = firestore.SERVER_TIMESTAMP
            
            # Store in Firestore
            doc_ref = self.db.collection('notifications').document(notification.id)
            doc_ref.set(notification_data)
            
            logger.info(f"Notification scheduled: {notification.id} for {notification.scheduled_time}")
            return True
            
        except Exception as e:
            logger.error(f"Error scheduling notification: {e}")
            return False
    
    async def create_reminder(self, reminder: Reminder) -> bool:
        """Create a new reminder"""
        try:
            if not self.db:
                return False
            
            reminder_data = asdict(reminder)
            reminder_data['created_at'] = firestore.SERVER_TIMESTAMP
            
            # Store in Firestore
            doc_ref = self.db.collection('reminders').document(reminder.id)
            doc_ref.set(reminder_data)
            
            # Create initial notification
            notification = Notification(
                id=f"notif_{reminder.id}",
                patient_id=reminder.patient_id,
                type=reminder.notification_type,
                title=reminder.title,
                message=reminder.description,
                priority=NotificationPriority.MEDIUM,
                scheduled_time=reminder.reminder_time,
                metadata=reminder.metadata
            )
            
            await self.schedule_notification(notification)
            
            logger.info(f"Reminder created: {reminder.id}")
            return True
            
        except Exception as e:
            logger.error(f"Error creating reminder: {e}")
            return False
    
    async def get_patient_reminders(self, patient_id: str) -> List[Dict[str, Any]]:
        """Get all reminders for a patient"""
        try:
            if not self.db:
                return []
            
            reminders_ref = self.db.collection('reminders')
            query = reminders_ref.where('patient_id', '==', patient_id).where('is_active', '==', True)
            docs = query.get()
            
            reminders = []
            for doc in docs:
                reminder_data = doc.to_dict()
                reminder_data['id'] = doc.id
                reminders.append(reminder_data)
            
            return reminders
            
        except Exception as e:
            logger.error(f"Error getting patient reminders: {e}")
            return []
    
    async def update_reminder(self, reminder_id: str, updates: Dict[str, Any]) -> bool:
        """Update a reminder"""
        try:
            if not self.db:
                return False
            
            self.db.collection('reminders').document(reminder_id).update(updates)
            logger.info(f"Reminder updated: {reminder_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error updating reminder: {e}")
            return False
    
    async def delete_reminder(self, reminder_id: str) -> bool:
        """Delete a reminder"""
        try:
            if not self.db:
                return False
            
            # Mark as inactive instead of deleting
            self.db.collection('reminders').document(reminder_id).update({
                'is_active': False
            })
            
            logger.info(f"Reminder deleted: {reminder_id}")
            return True
            
        except Exception as e:
            logger.error(f"Error deleting reminder: {e}")
            return False
    
    async def send_immediate_notification(self, patient_id: str, title: str, message: str, 
                                        notification_type: NotificationType = NotificationType.GENERAL_REMINDER,
                                        priority: NotificationPriority = NotificationPriority.MEDIUM) -> bool:
        """Send an immediate notification"""
        try:
            notification = Notification(
                id=f"immediate_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                patient_id=patient_id,
                type=notification_type,
                title=title,
                message=message,
                priority=priority,
                scheduled_time=datetime.utcnow(),
                status="pending"
            )
            
            # Schedule for immediate sending
            success = await self.schedule_notification(notification)
            if success:
                # Process immediately
                await self._send_notification(notification.id, asdict(notification))
            
            return success
            
        except Exception as e:
            logger.error(f"Error sending immediate notification: {e}")
            return False
    
    async def create_medication_reminder(self, patient_id: str, medication_name: str, 
                                       reminder_time: datetime, frequency: str = "daily") -> bool:
        """Create a medication reminder"""
        try:
            reminder = Reminder(
                id=f"med_reminder_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                patient_id=patient_id,
                title=f"Medication Reminder: {medication_name}",
                description=f"Time to take your {medication_name}",
                reminder_time=reminder_time,
                frequency=frequency,
                notification_type=NotificationType.MEDICATION_REMINDER,
                metadata={
                    'medication_name': medication_name,
                    'dosage': 'As prescribed',
                    'instructions': 'Take with food if required'
                }
            )
            
            return await self.create_reminder(reminder)
            
        except Exception as e:
            logger.error(f"Error creating medication reminder: {e}")
            return False
    
    async def create_appointment_reminder(self, patient_id: str, appointment_title: str,
                                        appointment_time: datetime, location: str = "") -> bool:
        """Create an appointment reminder"""
        try:
            # Schedule reminder 1 hour before appointment
            reminder_time = appointment_time - timedelta(hours=1)
            
            reminder = Reminder(
                id=f"appt_reminder_{datetime.utcnow().strftime('%Y%m%d_%H%M%S')}",
                patient_id=patient_id,
                title=f"Appointment Reminder: {appointment_title}",
                description=f"You have an appointment in 1 hour: {appointment_title}",
                reminder_time=reminder_time,
                frequency="once",
                notification_type=NotificationType.APPOINTMENT_REMINDER,
                metadata={
                    'appointment_title': appointment_title,
                    'appointment_time': appointment_time.isoformat(),
                    'location': location
                }
            )
            
            return await self.create_reminder(reminder)
            
        except Exception as e:
            logger.error(f"Error creating appointment reminder: {e}")
            return False 