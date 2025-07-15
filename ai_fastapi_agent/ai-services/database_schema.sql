-- MCP Database Schema for Lifelong Medical Assistant
-- This schema supports persistent memory and context for each patient

-- Patient Context Table - Stores lifelong memory and context
CREATE TABLE IF NOT EXISTS patient_context (
    patient_id VARCHAR(255) PRIMARY KEY,
    context_data JSONB NOT NULL,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP
);

-- Conversation History Table - Stores all interactions
CREATE TABLE IF NOT EXISTS conversation_history (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(255) NOT NULL,
    session_id VARCHAR(255) NOT NULL,
    message_type VARCHAR(50) NOT NULL, -- 'user' or 'ai'
    message_content TEXT NOT NULL,
    message_metadata JSONB,
    timestamp TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patient_context(patient_id)
);

-- Treatment Plans Table - Stores current and historical treatment plans
CREATE TABLE IF NOT EXISTS treatment_plans (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(255) NOT NULL,
    plan_name VARCHAR(255) NOT NULL,
    plan_type VARCHAR(100) NOT NULL, -- 'medication', 'lifestyle', 'therapy', etc.
    plan_details JSONB NOT NULL,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'completed', 'discontinued'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    effective_date DATE,
    end_date DATE,
    FOREIGN KEY (patient_id) REFERENCES patient_context(patient_id)
);

-- Health Goals Table - Patient's health objectives
CREATE TABLE IF NOT EXISTS health_goals (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(255) NOT NULL,
    goal_title VARCHAR(255) NOT NULL,
    goal_description TEXT,
    goal_type VARCHAR(100), -- 'weight_loss', 'fitness', 'medication_adherence', etc.
    target_value DECIMAL(10,2),
    current_value DECIMAL(10,2),
    target_date DATE,
    status VARCHAR(50) DEFAULT 'active', -- 'active', 'achieved', 'abandoned'
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patient_context(patient_id)
);

-- Medical Events Table - Important medical events and milestones
CREATE TABLE IF NOT EXISTS medical_events (
    id SERIAL PRIMARY KEY,
    patient_id VARCHAR(255) NOT NULL,
    event_type VARCHAR(100) NOT NULL, -- 'diagnosis', 'procedure', 'medication_change', 'symptom', etc.
    event_title VARCHAR(255) NOT NULL,
    event_description TEXT,
    event_date DATE NOT NULL,
    severity VARCHAR(50), -- 'low', 'medium', 'high', 'critical'
    event_data JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patient_context(patient_id)
);

-- Patient Preferences Table - User preferences and settings
CREATE TABLE IF NOT EXISTS patient_preferences (
    patient_id VARCHAR(255) PRIMARY KEY,
    communication_style VARCHAR(50) DEFAULT 'conversational', -- 'formal', 'conversational', 'detailed'
    detail_level VARCHAR(50) DEFAULT 'moderate', -- 'basic', 'moderate', 'detailed'
    notification_preferences JSONB,
    privacy_settings JSONB,
    accessibility_preferences JSONB,
    created_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (patient_id) REFERENCES patient_context(patient_id)
);

-- Agent Sessions Table - Track agent interaction sessions
CREATE TABLE IF NOT EXISTS agent_sessions (
    session_id VARCHAR(255) PRIMARY KEY,
    patient_id VARCHAR(255) NOT NULL,
    session_start TIMESTAMP WITH TIME ZONE DEFAULT CURRENT_TIMESTAMP,
    session_end TIMESTAMP WITH TIME ZONE,
    interaction_count INTEGER DEFAULT 0,
    session_summary TEXT,
    session_metadata JSONB,
    FOREIGN KEY (patient_id) REFERENCES patient_context(patient_id)
);

-- Create indexes for better performance
CREATE INDEX IF NOT EXISTS idx_conversation_history_patient_id ON conversation_history(patient_id);
CREATE INDEX IF NOT EXISTS idx_conversation_history_timestamp ON conversation_history(timestamp);
CREATE INDEX IF NOT EXISTS idx_treatment_plans_patient_id ON treatment_plans(patient_id);
CREATE INDEX IF NOT EXISTS idx_treatment_plans_status ON treatment_plans(status);
CREATE INDEX IF NOT EXISTS idx_health_goals_patient_id ON health_goals(patient_id);
CREATE INDEX IF NOT EXISTS idx_medical_events_patient_id ON medical_events(patient_id);
CREATE INDEX IF NOT EXISTS idx_medical_events_date ON medical_events(event_date);
CREATE INDEX IF NOT EXISTS idx_agent_sessions_patient_id ON agent_sessions(patient_id);

-- Create triggers for automatic timestamp updates
CREATE OR REPLACE FUNCTION update_updated_at_column()
RETURNS TRIGGER AS $$
BEGIN
    NEW.updated_at = CURRENT_TIMESTAMP;
    RETURN NEW;
END;
$$ language 'plpgsql';

CREATE TRIGGER update_patient_context_updated_at 
    BEFORE UPDATE ON patient_context 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_treatment_plans_updated_at 
    BEFORE UPDATE ON treatment_plans 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_health_goals_updated_at 
    BEFORE UPDATE ON health_goals 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

CREATE TRIGGER update_patient_preferences_updated_at 
    BEFORE UPDATE ON patient_preferences 
    FOR EACH ROW EXECUTE FUNCTION update_updated_at_column();

-- Create views for common queries
CREATE OR REPLACE VIEW patient_summary AS
SELECT 
    pc.patient_id,
    pc.context_data,
    COUNT(ch.id) as total_conversations,
    COUNT(tp.id) as active_treatments,
    COUNT(hg.id) as active_goals,
    MAX(ch.timestamp) as last_interaction,
    MAX(me.event_date) as last_medical_event
FROM patient_context pc
LEFT JOIN conversation_history ch ON pc.patient_id = ch.patient_id
LEFT JOIN treatment_plans tp ON pc.patient_id = tp.patient_id AND tp.status = 'active'
LEFT JOIN health_goals hg ON pc.patient_id = hg.patient_id AND hg.status = 'active'
LEFT JOIN medical_events me ON pc.patient_id = me.patient_id
GROUP BY pc.patient_id, pc.context_data;

-- Insert sample data for testing
INSERT INTO patient_context (patient_id, context_data) VALUES 
('test-patient-123', '{"total_interactions": 0, "health_goals": [], "treatment_preferences": {}}')
ON CONFLICT (patient_id) DO NOTHING; 