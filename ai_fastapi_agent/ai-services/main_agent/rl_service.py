# rl_service.py
# This module will handle the Reinforcement Learning aspects for patient treatment plans.

import random
from typing import Dict, Any, Optional, Tuple
from firebase_admin import firestore
# from .firestore_service import FirestoreService # Might be needed later for direct interaction

# Constants for rewards
REWARD_SUCCESS = 3
REWARD_FAIL_LESS_SEVERE = -1
REWARD_FAIL_SEVERE = -3

# Severity levels
SEVERITY_NONE = 0       # e.g., "✅ Biomarker parameters are currently stable."
SEVERITY_LESS = 1       # e.g., One "⚠️" risk factor
SEVERITY_SEVERE = 2     # e.g., Multiple "⚠️" risk factors or specific critical ones

def determine_severity_level(risk_assessment_str: Optional[str]) -> int:
    """
    Determines a numerical severity level from the risk_assessment string.
    Args:
        risk_assessment_str: The string output from simulate_risk().
    Returns:
        An integer representing the severity (SEVERITY_NONE, SEVERITY_LESS, SEVERITY_SEVERE).
    """
    if not risk_assessment_str or "✅" in risk_assessment_str:
        return SEVERITY_NONE
    
    # Count number of risk warnings
    warning_count = risk_assessment_str.count("⚠️")
    
    if warning_count == 0: # Should be caught by the first check, but as a safeguard
        return SEVERITY_NONE
    elif warning_count == 1:
        # Define if specific single warnings should be considered severe
        # For now, any single warning is "LESS_SEVERE"
        # Example: if "critical_warning_text" in risk_assessment_str: return SEVERITY_SEVERE
        return SEVERITY_LESS
    else: # 2 or more warnings
        return SEVERITY_SEVERE

def calculate_reward(outcome_works: bool, severity_level: int) -> int:
    """
    Calculates the reward based on treatment outcome and severity.
    Args:
        outcome_works: Boolean indicating if the treatment plan worked.
        severity_level: Numerical severity level (SEVERITY_NONE, SEVERITY_LESS, SEVERITY_SEVERE).
    Returns:
        The calculated reward points.
    """
    if outcome_works:
        return REWARD_SUCCESS
    else:
        if severity_level == SEVERITY_SEVERE:
            return REWARD_FAIL_SEVERE
        else: # SEVERITY_NONE or SEVERITY_LESS (less severe or stable but still failed)
            return REWARD_FAIL_LESS_SEVERE

class PatientRLAgent:
    def __init__(self, patient_id: str, db: firestore.client, learning_rate=0.1, discount_factor=0.9, exploration_rate=0.1):
        self.patient_id = patient_id
        self.db = db # Firestore client
        self.q_table: Dict[Tuple, Dict[Any, float]] = {} 
        self.lr = learning_rate
        self.gamma = discount_factor
        self.epsilon = exploration_rate
        
        self.rl_model_collection = "patient_rl_models" # Firestore collection to store Q-tables
        # self.load_model() # Load model on initialization

    def _get_state_representation(self, gemini_features: Dict[str, Any], 
                                 risk_assessment_str: Optional[str],
                                 # Add other relevant patient context here
                                 ) -> Tuple:
        """
        Converts the raw inputs into a hashable state representation for the Q-table.
        This needs careful design based on what defines a 'state'.
        Example: (gemini_feature_summary, quantified_risk, last_action_type)
        For now, a placeholder.
        """
        severity = determine_severity_level(risk_assessment_str)
        # Placeholder: Simplistic state based on severity and a dummy gemini feature
        # TODO: Define meaningful feature extraction from gemini_features
        gemini_feature_category = gemini_features.get("category", "general_advice") 
        return (str(gemini_feature_category), int(severity)) # Ensure hashable types

    def get_action(self, gemini_features: Dict[str, Any], risk_assessment_str: Optional[str]) -> Any:
        """
        Chooses an action based on the current state using an epsilon-greedy policy.
        The 'action' could be an adjustment to the plan, a choice between plans, etc.
        For now, placeholder: returns 0 (e.g., "no change") or 1 ("alternative suggestion").
        """
        current_state = self._get_state_representation(gemini_features, risk_assessment_str)

        # Define action space - e.g., 0: use planner output as is, 1: use gemini suggestion as primary
        possible_actions = [0, 1] 

        if random.random() < self.epsilon:
            action = random.choice(possible_actions)
            print(f"RL Agent ({self.patient_id}): Exploring - random action: {action}")
        else:
            action_values = self.q_table.get(current_state)
            if action_values: # If state exists in Q-table
                action = max(action_values, key=action_values.get)
            else: # New state, default to a safe or random action
                action = random.choice(possible_actions) # Or a predefined default action e.g. 0
            print(f"RL Agent ({self.patient_id}): Exploiting - action: {action} for state {current_state}")
        return action

    async def update_model(self, 
                         gemini_features_state: Dict[str, Any], risk_assessment_state: Optional[str],
                         action_taken: Any, 
                         reward: int, 
                         gemini_features_next_state: Optional[Dict[str, Any]], risk_assessment_next_state: Optional[str]):
        """
        Updates the Q-table based on the experience (state, action, reward, next_state).
        """
        current_state = self._get_state_representation(gemini_features_state, risk_assessment_state)
        
        if gemini_features_next_state is not None and risk_assessment_next_state is not None:
            next_state_tuple = self._get_state_representation(gemini_features_next_state, risk_assessment_next_state)
            next_action_values = self.q_table.get(next_state_tuple)
            next_max_q = max(next_action_values.values()) if next_action_values else 0.0
        else:
            next_max_q = 0.0

        if current_state not in self.q_table:
            self.q_table[current_state] = {0: 0.0, 1: 0.0} # Initialize Q-values for actions
        
        old_q_value = self.q_table[current_state].get(action_taken, 0.0)
        
        new_q_value = old_q_value + self.lr * (reward + self.gamma * next_max_q - old_q_value)
        self.q_table[current_state][action_taken] = new_q_value

        print(f"RL Agent ({self.patient_id}): Updated Q-value for state {current_state}, action {action_taken} to {new_q_value}")
        await self.save_model() # Save model after update

    async def load_model(self):
        """Loads the Q-table from Firestore."""
        if not self.db:
            print(f"RL Agent ({self.patient_id}): Firestore client not available. Cannot load model.")
            return
        try:
            doc_ref = self.db.collection(self.rl_model_collection).document(self.patient_id)
            doc = await doc_ref.get()
            if doc.exists:
                data = doc.to_dict()
                # Firestore stores dict keys as strings. Tuples used as Q-table keys were stringified.
                # We need to convert them back to tuples using eval(), carefully.
                raw_q_table = data.get("q_table_str_keys", {})
                self.q_table = {}
                for k_str, v_actions in raw_q_table.items():
                    try:
                        # Example k_str: "('general_advice', 0)"
                        state_tuple = eval(k_str) # Be cautious with eval
                        if isinstance(state_tuple, tuple):
                            self.q_table[state_tuple] = {int(act_k): float(act_v) for act_k, act_v in v_actions.items()}                        
                        else:
                            print(f"RL Agent ({self.patient_id}): Skipped invalid key format during Q-table load: {k_str}")
                    except Exception as e_eval:
                        print(f"RL Agent ({self.patient_id}): Error evaluating Q-table key '{k_str}': {e_eval}")
                
                self.lr = data.get("learning_rate", self.lr)
                self.gamma = data.get("discount_factor", self.gamma)
                self.epsilon = data.get("exploration_rate", self.epsilon)
                print(f"RL Agent ({self.patient_id}): Model loaded. Q-table size: {len(self.q_table)}")
            else:
                print(f"RL Agent ({self.patient_id}): No existing model found. Starting fresh.")
                self.q_table = {}
        except Exception as e:
            print(f"RL Agent ({self.patient_id}): Error loading model - {e}. Starting fresh.")
            self.q_table = {}

    async def save_model(self):
        """Saves the Q-table to Firestore."""
        if not self.db:
            print(f"RL Agent ({self.patient_id}): Firestore client not available. Cannot save model.")
            return
        try:
            q_table_str_keys = {str(k): v for k, v in self.q_table.items()}
            data_to_save = {
                "q_table_str_keys": q_table_str_keys,
                "learning_rate": self.lr,
                "discount_factor": self.gamma,
                "exploration_rate": self.epsilon,
                "last_updated": firestore.SERVER_TIMESTAMP
            }
            doc_ref = self.db.collection(self.rl_model_collection).document(self.patient_id)
            await doc_ref.set(data_to_save, merge=True)
            print(f"RL Agent ({self.patient_id}): Model saved successfully.")
        except Exception as e:
            print(f"RL Agent ({self.patient_id}): Error saving model - {e}.")

# Need to import random for exploration
import random 