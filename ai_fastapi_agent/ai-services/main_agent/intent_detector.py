"""
Intent Detection Module for Medical Agent
Detects the intent of patient queries to provide appropriate responses.
"""

from enum import Enum
from typing import Dict, List, Optional
import re
import logging

logger = logging.getLogger(__name__)

class IntentType(Enum):
    """Enumeration of possible query intents"""
    GENERAL_QUESTION = "general_question"
    SYMPTOM_DESCRIPTION = "symptom_description"
    MEDICATION_QUERY = "medication_query"
    APPOINTMENT_REQUEST = "appointment_request"
    EMERGENCY = "emergency"
    TREATMENT_UPDATE = "treatment_update"
    TEST_RESULTS = "test_results"
    LIFESTYLE_ADVICE = "lifestyle_advice"
    UNKNOWN = "unknown"

class IntentDetector:
    """Detects the intent of patient queries"""
    
    def __init__(self):
        # Keywords for different intents
        self.intent_keywords = {
            IntentType.SYMPTOM_DESCRIPTION: [
                "pain", "ache", "hurt", "sore", "uncomfortable", "feeling",
                "headache", "fever", "cough", "cold", "nausea", "dizziness",
                "tired", "fatigue", "weak", "sick", "ill", "symptom"
            ],
            IntentType.MEDICATION_QUERY: [
                "medicine", "medication", "pill", "drug", "prescription",
                "dosage", "side effect", "interaction", "when to take",
                "how much", "refill", "pharmacy"
            ],
            IntentType.APPOINTMENT_REQUEST: [
                "appointment", "schedule", "book", "visit", "see doctor",
                "consultation", "checkup", "follow-up", "next visit"
            ],
            IntentType.EMERGENCY: [
                "emergency", "urgent", "severe", "critical", "immediate",
                "chest pain", "difficulty breathing", "unconscious",
                "bleeding", "broken", "fracture", "heart attack", "stroke"
            ],
            IntentType.TREATMENT_UPDATE: [
                "treatment", "therapy", "plan", "progress", "improvement",
                "worse", "better", "recovery", "healing"
            ],
            IntentType.TEST_RESULTS: [
                "test", "result", "lab", "blood", "urine", "x-ray",
                "scan", "mri", "ct", "biopsy", "report"
            ],
            IntentType.LIFESTYLE_ADVICE: [
                "diet", "exercise", "sleep", "stress", "lifestyle",
                "nutrition", "fitness", "wellness", "healthy"
            ]
        }
        
        # Emergency patterns that require immediate attention
        self.emergency_patterns = [
            r"chest\s+pain",
            r"difficulty\s+breathing",
            r"can't\s+breathe",
            r"unconscious",
            r"severe\s+bleeding",
            r"broken\s+bone",
            r"heart\s+attack",
            r"stroke",
            r"severe\s+headache",
            r"paralysis",
            r"seizure"
        ]
    
    def detect_intent(self, query_text: str) -> IntentType:
        """
        Detect the intent of a patient query
        
        Args:
            query_text: The patient's query text
            
        Returns:
            IntentType: The detected intent
        """
        if not query_text:
            return IntentType.UNKNOWN
        
        # Convert to lowercase for matching
        query_lower = query_text.lower()
        
        # Check for emergency patterns first
        for pattern in self.emergency_patterns:
            if re.search(pattern, query_lower):
                logger.warning(f"Emergency intent detected: {pattern}")
                return IntentType.EMERGENCY
        
        # Count keyword matches for each intent
        intent_scores = {}
        
        for intent_type, keywords in self.intent_keywords.items():
            score = 0
            for keyword in keywords:
                if keyword in query_lower:
                    score += 1
            intent_scores[intent_type] = score
        
        # Find the intent with the highest score
        if intent_scores:
            best_intent = max(intent_scores.items(), key=lambda x: x[1])
            if best_intent[1] > 0:
                logger.info(f"Intent detected: {best_intent[0]} (score: {best_intent[1]})")
                return best_intent[0]
        
        # Default to general question if no specific intent detected
        return IntentType.GENERAL_QUESTION
    
    def get_intent_confidence(self, query_text: str, detected_intent: IntentType) -> float:
        """
        Calculate confidence score for the detected intent
        
        Args:
            query_text: The patient's query text
            detected_intent: The detected intent
            
        Returns:
            float: Confidence score between 0 and 1
        """
        if not query_text or detected_intent == IntentType.UNKNOWN:
            return 0.0
        
        query_lower = query_text.lower()
        keywords = self.intent_keywords.get(detected_intent, [])
        
        if not keywords:
            return 0.5  # Default confidence for unknown intents
        
        # Count matched keywords
        matched_keywords = sum(1 for keyword in keywords if keyword in query_lower)
        total_keywords = len(keywords)
        
        # Calculate confidence as ratio of matched keywords
        confidence = min(matched_keywords / total_keywords, 1.0)
        
        # Boost confidence for emergency intents
        if detected_intent == IntentType.EMERGENCY:
            confidence = min(confidence + 0.3, 1.0)
        
        return confidence
    
    def extract_entities(self, query_text: str) -> Dict[str, List[str]]:
        """
        Extract entities from the query text
        
        Args:
            query_text: The patient's query text
            
        Returns:
            Dict[str, List[str]]: Extracted entities by type
        """
        entities = {
            "symptoms": [],
            "medications": [],
            "body_parts": [],
            "time_references": []
        }
        
        if not query_text:
            return entities
        
        query_lower = query_text.lower()
        
        # Extract symptoms (basic implementation)
        symptom_keywords = [
            "headache", "fever", "cough", "cold", "nausea", "dizziness",
            "fatigue", "pain", "ache", "sore", "tired", "weak"
        ]
        
        for symptom in symptom_keywords:
            if symptom in query_lower:
                entities["symptoms"].append(symptom)
        
        # Extract medications (basic implementation)
        medication_keywords = [
            "aspirin", "ibuprofen", "acetaminophen", "tylenol", "advil",
            "antibiotic", "prescription", "medicine", "pill"
        ]
        
        for med in medication_keywords:
            if med in query_lower:
                entities["medications"].append(med)
        
        # Extract body parts (basic implementation)
        body_parts = [
            "head", "chest", "stomach", "back", "leg", "arm", "hand",
            "foot", "neck", "throat", "eye", "ear", "nose"
        ]
        
        for part in body_parts:
            if part in query_lower:
                entities["body_parts"].append(part)
        
        # Extract time references (basic implementation)
        time_patterns = [
            r"yesterday", r"today", r"tomorrow", r"last\s+week",
            r"this\s+morning", r"this\s+afternoon", r"tonight"
        ]
        
        for pattern in time_patterns:
            matches = re.findall(pattern, query_lower)
            entities["time_references"].extend(matches)
        
        return entities

# Global instance
intent_detector = IntentDetector() 