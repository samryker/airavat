import os
import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from email.mime.base import MIMEBase
from email import encoders
from typing import List, Dict, Optional, Any
import logging
from datetime import datetime, timedelta
import jwt
from jinja2 import Template
import firebase_admin
from firebase_admin import auth, firestore
import asyncio
from dataclasses import dataclass
from enum import Enum

logger = logging.getLogger(__name__)

class EmailType(Enum):
    WELCOME = "welcome"
    PASSWORD_RESET = "password_reset"
    EMAIL_VERIFICATION = "email_verification"
    MEDICAL_ALERT = "medical_alert"
    APPOINTMENT_REMINDER = "appointment_reminder"
    MEDICATION_REMINDER = "medication_reminder"
    DOCTOR_NOTIFICATION = "doctor_notification"
    CRISPR_REPORT_READY = "crispr_report_ready"
    BIOMARKER_UPDATE = "biomarker_update"

@dataclass
class EmailTemplate:
    subject: str
    html_template: str
    text_template: str

class EmailService:
    """
    Enterprise-grade email service for Airavat Medical AI Assistant
    Supports authentication, notifications, and medical alerts
    """
    
    def __init__(self):
        self.smtp_server = os.getenv("SMTP_SERVER", "smtp.gmail.com")
        self.smtp_port = int(os.getenv("SMTP_PORT", "587"))
        self.smtp_username = os.getenv("SMTP_USERNAME")
        self.smtp_password = os.getenv("SMTP_PASSWORD")
        self.from_email = os.getenv("FROM_EMAIL", "noreply@airavat.ai")
        self.from_name = os.getenv("FROM_NAME", "Airavat Medical AI")
        self.jwt_secret = os.getenv("JWT_SECRET", "your-secret-key-change-in-production")
        self.base_url = os.getenv("BASE_URL", "https://airavat-a3a10.web.app")
        
        # Initialize Firebase
        try:
            self.db = firestore.client()
        except Exception as e:
            logger.error(f"Failed to initialize Firestore: {e}")
            self.db = None
            
        # Email templates
        self.templates = self._load_email_templates()
        
    def _load_email_templates(self) -> Dict[EmailType, EmailTemplate]:
        """Load email templates for different types of emails"""
        return {
            EmailType.WELCOME: EmailTemplate(
                subject="Welcome to Airavat - Your Personal Medical AI Assistant",
                html_template="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Welcome to Airavat</title>
                    <style>
                        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                        .button { display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>Welcome to Airavat</h1>
                            <p>Your Personal Medical AI Assistant</p>
                        </div>
                        <div class="content">
                            <h2>Hello {{ user_name }},</h2>
                            <p>Welcome to Airavat! You've just joined the future of personalized healthcare.</p>
                            
                            <h3>What Airavat offers:</h3>
                            <ul>
                                <li>🤖 AI-powered medical consultations</li>
                                <li>🧬 Genetic report analysis and CRISPR insights</li>
                                <li>📊 Personalized biomarker tracking</li>
                                <li>🔔 Smart medication and appointment reminders</li>
                                <li>👨‍⚕️ Direct communication with your healthcare providers</li>
                            </ul>
                            
                            <p>Your account is now ready. Please verify your email to unlock all features:</p>
                            
                            <a href="{{ verification_url }}" class="button">Verify Email Address</a>
                            
                            <p><strong>Security Note:</strong> This verification link will expire in 24 hours.</p>
                            
                            <p>If you have any questions, our support team is here to help.</p>
                            
                            <p>Best regards,<br>The Airavat Team</p>
                        </div>
                        <div class="footer">
                            <p>This email was sent to {{ email }}. If you didn't create an Airavat account, please ignore this email.</p>
                            <p>Airavat - Advancing Healthcare Through AI</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                Welcome to Airavat - Your Personal Medical AI Assistant
                
                Hello {{ user_name }},
                
                Welcome to Airavat! You've just joined the future of personalized healthcare.
                
                What Airavat offers:
                - AI-powered medical consultations
                - Genetic report analysis and CRISPR insights
                - Personalized biomarker tracking
                - Smart medication and appointment reminders
                - Direct communication with your healthcare providers
                
                Your account is now ready. Please verify your email to unlock all features:
                {{ verification_url }}
                
                Security Note: This verification link will expire in 24 hours.
                
                If you have any questions, our support team is here to help.
                
                Best regards,
                The Airavat Team
                
                This email was sent to {{ email }}. If you didn't create an Airavat account, please ignore this email.
                """
            ),
            
            EmailType.PASSWORD_RESET: EmailTemplate(
                subject="Reset Your Airavat Password",
                html_template="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Password Reset</title>
                    <style>
                        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                        .header { background: #dc3545; color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                        .button { display: inline-block; padding: 12px 24px; background: #dc3545; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>Password Reset Request</h1>
                        </div>
                        <div class="content">
                            <h2>Hello {{ user_name }},</h2>
                            <p>We received a request to reset your Airavat password.</p>
                            
                            <p>Click the button below to create a new password:</p>
                            
                            <a href="{{ reset_url }}" class="button">Reset Password</a>
                            
                            <p><strong>Security Note:</strong></p>
                            <ul>
                                <li>This link will expire in 1 hour</li>
                                <li>If you didn't request this reset, please ignore this email</li>
                                <li>Your current password will remain unchanged</li>
                            </ul>
                            
                            <p>If the button doesn't work, copy and paste this link into your browser:</p>
                            <p>{{ reset_url }}</p>
                            
                            <p>Best regards,<br>The Airavat Security Team</p>
                        </div>
                        <div class="footer">
                            <p>This email was sent to {{ email }}. If you didn't request a password reset, please contact support immediately.</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                Password Reset Request
                
                Hello {{ user_name }},
                
                We received a request to reset your Airavat password.
                
                Click the link below to create a new password:
                {{ reset_url }}
                
                Security Note:
                - This link will expire in 1 hour
                - If you didn't request this reset, please ignore this email
                - Your current password will remain unchanged
                
                Best regards,
                The Airavat Security Team
                
                This email was sent to {{ email }}. If you didn't request a password reset, please contact support immediately.
                """
            ),
            
            EmailType.MEDICAL_ALERT: EmailTemplate(
                subject="Medical Alert from Airavat",
                html_template="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>Medical Alert</title>
                    <style>
                        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                        .header { background: #ffc107; color: #333; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                        .alert { background: #fff3cd; border: 1px solid #ffeaa7; padding: 15px; border-radius: 5px; margin: 20px 0; }
                        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>⚠️ Medical Alert</h1>
                        </div>
                        <div class="content">
                            <h2>Hello {{ user_name }},</h2>
                            
                            <div class="alert">
                                <h3>{{ alert_title }}</h3>
                                <p>{{ alert_message }}</p>
                            </div>
                            
                            <h3>Recommended Actions:</h3>
                            <ul>
                                {% for action in recommended_actions %}
                                <li>{{ action }}</li>
                                {% endfor %}
                            </ul>
                            
                            <p><strong>Priority:</strong> {{ priority_level }}</p>
                            <p><strong>Timestamp:</strong> {{ timestamp }}</p>
                            
                            <p>Please review this information and take appropriate action. If you have concerns, contact your healthcare provider.</p>
                            
                            <p>Best regards,<br>Airavat Medical AI</p>
                        </div>
                        <div class="footer">
                            <p>This is an automated medical alert from Airavat. For emergencies, call 911 immediately.</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                Medical Alert from Airavat
                
                Hello {{ user_name }},
                
                MEDICAL ALERT: {{ alert_title }}
                
                {{ alert_message }}
                
                Recommended Actions:
                {% for action in recommended_actions %}
                - {{ action }}
                {% endfor %}
                
                Priority: {{ priority_level }}
                Timestamp: {{ timestamp }}
                
                Please review this information and take appropriate action. If you have concerns, contact your healthcare provider.
                
                Best regards,
                Airavat Medical AI
                
                This is an automated medical alert from Airavat. For emergencies, call 911 immediately.
                """
            ),
            
            EmailType.CRISPR_REPORT_READY: EmailTemplate(
                subject="Your CRISPR Analysis Report is Ready",
                html_template="""
                <!DOCTYPE html>
                <html>
                <head>
                    <meta charset="utf-8">
                    <title>CRISPR Report Ready</title>
                    <style>
                        body { font-family: Arial, sans-serif; line-height: 1.6; color: #333; }
                        .container { max-width: 600px; margin: 0 auto; padding: 20px; }
                        .header { background: linear-gradient(135deg, #667eea 0%, #764ba2 100%); color: white; padding: 30px; text-align: center; border-radius: 10px 10px 0 0; }
                        .content { background: #f9f9f9; padding: 30px; border-radius: 0 0 10px 10px; }
                        .button { display: inline-block; padding: 12px 24px; background: #667eea; color: white; text-decoration: none; border-radius: 5px; margin: 20px 0; }
                        .footer { text-align: center; margin-top: 30px; color: #666; font-size: 12px; }
                    </style>
                </head>
                <body>
                    <div class="container">
                        <div class="header">
                            <h1>🧬 CRISPR Analysis Complete</h1>
                            <p>Your Genetic Report Analysis is Ready</p>
                        </div>
                        <div class="content">
                            <h2>Hello {{ user_name }},</h2>
                            <p>Great news! Your genetic report has been analyzed and your CRISPR insights are ready.</p>
                            
                            <h3>Analysis Summary:</h3>
                            <ul>
                                <li><strong>Report Type:</strong> {{ report_type }}</li>
                                <li><strong>Analysis Date:</strong> {{ analysis_date }}</li>
                                <li><strong>Key Findings:</strong> {{ key_findings_count }} genetic markers identified</li>
                                <li><strong>CRISPR Targets:</strong> {{ crispr_targets_count }} potential editing targets</li>
                            </ul>
                            
                            <p>View your detailed CRISPR analysis report:</p>
                            
                            <a href="{{ report_url }}" class="button">View CRISPR Report</a>
                            
                            <p><strong>Important:</strong> This report contains sensitive genetic information. Please review it in a private setting and discuss with your healthcare provider.</p>
                            
                            <p>Best regards,<br>Airavat Genetic Analysis Team</p>
                        </div>
                        <div class="footer">
                            <p>This report contains confidential genetic information. Please handle with appropriate care.</p>
                        </div>
                    </div>
                </body>
                </html>
                """,
                text_template="""
                CRISPR Analysis Complete
                
                Hello {{ user_name }},
                
                Great news! Your genetic report has been analyzed and your CRISPR insights are ready.
                
                Analysis Summary:
                - Report Type: {{ report_type }}
                - Analysis Date: {{ analysis_date }}
                - Key Findings: {{ key_findings_count }} genetic markers identified
                - CRISPR Targets: {{ crispr_targets_count }} potential editing targets
                
                View your detailed CRISPR analysis report:
                {{ report_url }}
                
                Important: This report contains sensitive genetic information. Please review it in a private setting and discuss with your healthcare provider.
                
                Best regards,
                Airavat Genetic Analysis Team
                
                This report contains confidential genetic information. Please handle with appropriate care.
                """
            )
        }
    
    def _generate_jwt_token(self, user_id: str, email: str, purpose: str, expires_in: int = 3600) -> str:
        """Generate JWT token for email verification and password reset"""
        payload = {
            'user_id': user_id,
            'email': email,
            'purpose': purpose,
            'exp': datetime.utcnow() + timedelta(seconds=expires_in),
            'iat': datetime.utcnow()
        }
        return jwt.encode(payload, self.jwt_secret, algorithm='HS256')
    
    def _verify_jwt_token(self, token: str, purpose: str) -> Optional[Dict[str, Any]]:
        """Verify JWT token and return payload if valid"""
        try:
            payload = jwt.decode(token, self.jwt_secret, algorithms=['HS256'])
            if payload.get('purpose') == purpose:
                return payload
        except jwt.ExpiredSignatureError:
            logger.warning("JWT token expired")
        except jwt.InvalidTokenError:
            logger.warning("Invalid JWT token")
        return None
    
    async def send_email(self, to_email: str, email_type: EmailType, context: Dict[str, Any]) -> bool:
        """Send email with proper error handling and logging"""
        try:
            if not self.smtp_username or not self.smtp_password:
                logger.error("SMTP credentials not configured")
                return False
            
            template = self.templates.get(email_type)
            if not template:
                logger.error(f"Email template not found for type: {email_type}")
                return False
            
            # Render templates
            html_template = Template(template.html_template)
            text_template = Template(template.text_template)
            
            html_content = html_template.render(**context)
            text_content = text_template.render(**context)
            
            # Create message
            msg = MIMEMultipart('alternative')
            msg['Subject'] = template.subject
            msg['From'] = f"{self.from_name} <{self.from_email}>"
            msg['To'] = to_email
            
            # Attach parts
            text_part = MIMEText(text_content, 'plain')
            html_part = MIMEText(html_content, 'html')
            msg.attach(text_part)
            msg.attach(html_part)
            
            # Send email
            with smtplib.SMTP(self.smtp_server, self.smtp_port) as server:
                server.starttls(context=ssl.create_default_context())
                server.login(self.smtp_username, self.smtp_password)
                server.send_message(msg)
            
            logger.info(f"Email sent successfully to {to_email} (type: {email_type})")
            
            # Log email in database
            await self._log_email_sent(to_email, email_type, context)
            
            return True
            
        except Exception as e:
            logger.error(f"Failed to send email to {to_email}: {e}")
            return False
    
    async def _log_email_sent(self, to_email: str, email_type: EmailType, context: Dict[str, Any]):
        """Log email sent to database for tracking"""
        if not self.db:
            return
        
        try:
            await self.db.collection('email_logs').add({
                'to_email': to_email,
                'email_type': email_type.value,
                'context': context,
                'sent_at': firestore.SERVER_TIMESTAMP,
                'status': 'sent'
            })
        except Exception as e:
            logger.error(f"Failed to log email: {e}")
    
    async def send_welcome_email(self, user_id: str, email: str, user_name: str) -> bool:
        """Send welcome email with email verification link"""
        try:
            # Generate verification token
            token = self._generate_jwt_token(user_id, email, 'email_verification', 86400)  # 24 hours
            verification_url = f"{self.base_url}/verify-email?token={token}"
            
            context = {
                'user_name': user_name,
                'email': email,
                'verification_url': verification_url
            }
            
            return await self.send_email(email, EmailType.WELCOME, context)
            
        except Exception as e:
            logger.error(f"Failed to send welcome email: {e}")
            return False
    
    async def send_password_reset_email(self, user_id: str, email: str, user_name: str) -> bool:
        """Send password reset email"""
        try:
            # Generate reset token
            token = self._generate_jwt_token(user_id, email, 'password_reset', 3600)  # 1 hour
            reset_url = f"{self.base_url}/reset-password?token={token}"
            
            context = {
                'user_name': user_name,
                'email': email,
                'reset_url': reset_url
            }
            
            return await self.send_email(email, EmailType.PASSWORD_RESET, context)
            
        except Exception as e:
            logger.error(f"Failed to send password reset email: {e}")
            return False
    
    async def send_medical_alert(self, user_id: str, email: str, user_name: str, 
                                alert_title: str, alert_message: str, 
                                recommended_actions: List[str], priority_level: str) -> bool:
        """Send medical alert email"""
        try:
            context = {
                'user_name': user_name,
                'email': email,
                'alert_title': alert_title,
                'alert_message': alert_message,
                'recommended_actions': recommended_actions,
                'priority_level': priority_level,
                'timestamp': datetime.now().strftime("%Y-%m-%d %H:%M:%S UTC")
            }
            
            return await self.send_email(email, EmailType.MEDICAL_ALERT, context)
            
        except Exception as e:
            logger.error(f"Failed to send medical alert: {e}")
            return False
    
    async def send_crispr_report_ready_email(self, user_id: str, email: str, user_name: str,
                                           report_type: str, analysis_date: str,
                                           key_findings_count: int, crispr_targets_count: int,
                                           report_url: str) -> bool:
        """Send CRISPR report ready notification"""
        try:
            context = {
                'user_name': user_name,
                'email': email,
                'report_type': report_type,
                'analysis_date': analysis_date,
                'key_findings_count': key_findings_count,
                'crispr_targets_count': crispr_targets_count,
                'report_url': report_url
            }
            
            return await self.send_email(email, EmailType.CRISPR_REPORT_READY, context)
            
        except Exception as e:
            logger.error(f"Failed to send CRISPR report email: {e}")
            return False
    
    def verify_email_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify email verification token"""
        return self._verify_jwt_token(token, 'email_verification')
    
    def verify_reset_token(self, token: str) -> Optional[Dict[str, Any]]:
        """Verify password reset token"""
        return self._verify_jwt_token(token, 'password_reset')

# Global email service instance
email_service = EmailService() 