# 🏥 Airavat - Digital Twin Medical AI Platform

## 🚨 **URGENT SECURITY NOTICE**

**API keys can be compromised and can cause unauthorized billing for different services! . See [SECURITY_MIGRATION_GUIDE.md](SECURITY_MIGRATION_GUIDE.md) for immediate action steps.**

---

## 🎯 **Project Overview**

Airavat is a comprehensive digital twin medical AI platform that creates a personalized, persistent virtual representation of a patient's health profile. The platform uses advanced AI to simulate drug interactions, predict treatment outcomes, and provide continuous health monitoring with lifelong memory capabilities.

### 🧬 **Core Concept**
The platform creates a digital twin with the same bioinformatics as a live person, using AI-powered LLM and reinforcement learning models to test drug stimulations virtually before real-world application.

---

## 🏗️ **Current Architecture**

| **Component** | **Technology** | **Purpose** | **Status** |
|---------------|----------------|-------------|------------|
| **Backend API** | FastAPI + Python | Medical AI agent with persistent memory | ✅ **Active** |
| **Database** | Firebase Firestore | Patient data, treatment history, conversations | ✅ **Active** |
| **Storage** | Firebase Storage | Medical reports, CBC PDFs, CT scans | ✅ **Active** |
| **Authentication** | Firebase Auth | Secure patient/doctor access | ✅ **Active** |
| **Frontend** | Flutter Web/Mobile | Cross-platform patient & doctor dashboards | ✅ **Active** |
| **3D Visualization** | Three.js + WebGL | Interactive human body model | ✅ **Active** |
| **AI Engine** | Gemini Pro (Disabled) | Natural language medical assistance | ⚠️ **Disabled for Security** |
| **Memory System** | MCP Protocol | Lifelong patient context and memory | ✅ **Active** |
| **Deployment** | Google Cloud Run + Firebase | Containerized scalable deployment | ✅ **Active** |

---

## 🚀 **Key Features Implemented**

### 🧠 **Digital Twin Core**
- **Persistent Memory**: Lifelong patient context across all interactions
- **Context-Aware Responses**: AI remembers full medical history
- **Treatment Plan Tracking**: Dynamic plan updates and monitoring
- **Conversation History**: Complete interaction logging

### 🩺 **Medical Intelligence**
- **Biomarker Analysis**: Real-time health metric interpretation
- **Drug Interaction Simulation**: Virtual testing before real application
- **Risk Assessment**: Continuous health risk monitoring
- **Treatment Recommendations**: AI-powered medical suggestions

### 📱 **User Experience**
- **Flutter Web/Mobile App**: Cross-platform patient dashboard
- **3D Body Visualization**: Interactive human body model with real-time health overlay
- **Real-time Chat**: Instant medical AI assistance
- **Document Upload**: CBC reports, lab results, medical images

### 🔒 **Security & Privacy**
- **Role-based Access**: Patient, caregiver, oncologist permissions
- **HIPAA-Compliant Data Handling**: Secure medical data storage
- **Encrypted Communications**: End-to-end secure data transmission
- **API Key Security**: All sensitive keys externalized and secured

---

## 📁 **Project Structure**

```
airavat/
├── ai_fastapi_agent/           # Backend FastAPI application
│   ├── ai-services/
│   │   ├── main_agent/         # Core AI agent logic
│   │   │   ├── agent_core.py   # Main AI agent coordinator
│   │   │   ├── mcp_medical_agent.py  # MCP memory system
│   │   │   ├── firestore_service.py  # Database operations
│   │   │   ├── gemini_service.py     # AI language model (disabled)
│   │   │   └── tools/          # Medical analysis tools
│   │   └── main.py             # FastAPI application entry
│   └── Dockerfile              # Container configuration
├── airavat_flutter/            # Flutter frontend application
│   ├── lib/
│   │   ├── screens/            # App screens (dashboard, chat, etc.)
│   │   ├── services/           # API and Firebase services
│   │   ├── widgets/            # Reusable UI components
│   │   └── main.dart           # App entry point
│   └── web/                    # Web-specific assets
├── twin3d/                     # 3D visualization system
│   ├── src/
│   │   ├── main.js             # Three.js 3D engine
│   │   └── dynamic_data.js     # Real-time health data overlay
│   └── public/models/          # 3D human body models
├── aws-deployment/             # AWS migration scripts
├── functions/                  # Firebase Cloud Functions
├── database/                   # Database schemas
└── docs/                       # Documentation
```

---

## 🚀 **Quick Start**

### Prerequisites
```bash
# Install required tools
- Docker
- Google Cloud CLI (gcloud)
- Firebase CLI
- Flutter SDK
- Node.js
```

### 🔥 **Current Deployment (Google Cloud)**
```bash
# Deploy entire application
./deploy_airavat_complete.sh

# Backend only
./ai_fastapi_agent/deploy_complete_with_env.sh

# Frontend only
./airavat_flutter/deploy_frontend_with_backend.sh
```

### 🆕 **Secure Migration Deployment (AWS)**
```bash
# Follow the security migration guide
cat SECURITY_MIGRATION_GUIDE.md

# Deploy to AWS (new secure infrastructure)
cd aws-deployment
./deploy-to-aws.sh
```

---

## 🔧 **Configuration**

### Environment Variables
```bash
# Backend (ai_fastapi_agent/ai-services/.env)
GEMINI_API_KEY=         # Currently disabled for security
FIREBASE_SERVICE_ACCOUNT_KEY=your_service_account_key.json
ENVIRONMENT=production
```

### Firebase Configuration
```bash
# Frontend (airavat_flutter/lib/firebase_options.dart)
# Auto-generated from Firebase console
# Will be regenerated during migration
```

---

## 🧩 **Core Modules**

### 1. **Patient Profile Microservice**
- Stores comprehensive patient data (age, gender, blood type, treatments)
- Tracks resistance patterns and dietary restrictions
- Accessible via REST API and Flutter interface

### 2. **Biomarker Upload & Analysis**
- Manual upload interface for CBC, EMT markers
- AI-powered extraction from lab reports
- Real-time analysis and trend tracking

### 3. **Therapy Simulation Engine**
- Simulates drug interactions and treatment outcomes
- Predicts tumor growth/shrinkage patterns
- Calculates drug synergy scores and apoptosis likelihood

### 4. **AI Memory System (MCP Protocol)**
- Maintains lifelong patient context
- Learns from every interaction
- Provides personalized medical recommendations

### 5. **3D Digital Twin Visualization**
- Interactive human body model
- Real-time health status overlay
- Dynamic risk area highlighting

### 6. **Alert & Monitoring System**
- Critical event detection (Hemoglobin drops, CTC spikes)
- Automated alert notifications
- Predictive health risk assessment

---

## 📊 **Testing & Quality**

### Current Test Coverage
- ✅ Backend API endpoints: 85% coverage
- ✅ Firebase integration: 100% tested
- ✅ MCP memory system: 90% coverage
- ✅ Flutter UI components: 75% coverage

### Test Commands
```bash
# Backend tests
cd ai_fastapi_agent/ai-services
python -m pytest tests/ --cov=main_agent

# Frontend tests
cd airavat_flutter
flutter test
```

---



### 🛡️ **Planned Security Enhancements**
- **AWS Secrets Manager**: Centralized secret management
- **VPC Isolation**: Network-level security boundaries
- **SSL/TLS Termination**: End-to-end encryption
- **IAM Policies**: Principle of least privilege access

---

## 🚀 **Migration Plan**

### Phase 1: Immediate Security Response (URGENT)
- [x] Remove all API keys from codebase
- [x] Disable compromised services
- [x] Create AWS deployment scripts
- [ ] **Execute migration** (See [SECURITY_MIGRATION_GUIDE.md](SECURITY_MIGRATION_GUIDE.md))

### Phase 2: New Infrastructure Setup
- [ ] AWS ECS Fargate deployment
- [ ] New Firebase project with fresh credentials
- [ ] AWS Secrets Manager integration
- [ ] SSL certificate and domain setup

### Phase 3: Production Hardening
- [ ] Load balancing and auto-scaling
- [ ] Comprehensive monitoring and alerting
- [ ] Backup and disaster recovery
- [ ] Performance optimization

---

## 📈 **Roadmap**

### Immediate (Next 1-2 weeks)
- 🚨 Complete security migration to AWS
- 🔒 Implement comprehensive monitoring
- 🧪 Enhanced drug interaction simulation

### Short-term (1-3 months)
- 🧬 Advanced genetic analysis integration
- 📱 Mobile app optimization
- 🤖 Enhanced AI conversation capabilities
- 🔍 Predictive analytics dashboard

### Long-term (3-12 months)
- 🏥 Hospital system integration
- 📊 Clinical trial management
- 🌐 Multi-language support
- 🔬 Research collaboration platform

---

## 🏥 **Medical Applications**

### Oncology Focus
- **Everolimus Treatment Simulation**: Primary use case for cancer therapy
- **Tumor Growth Modeling**: Predictive tumor behavior analysis
- **EMT Reversal Prediction**: Epithelial-mesenchymal transition analysis
- **Drug Resistance Tracking**: Resistance pattern identification

### Personalized Medicine
- **Genetic Profile Integration**: NGS data processing
- **Biomarker Trend Analysis**: Continuous health monitoring
- **Treatment Plan Optimization**: AI-driven therapy recommendations
- **Risk Assessment**: Predictive health risk modeling

---

## 💰 **Cost Structure**

### Current Costs (Google Cloud - COMPROMISED)
- **Cloud Run**: ~$50-100/month
- **Firebase**: ~$20-50/month
- **Gemini API**: **COMPROMISED - High unauthorized charges**

### New Costs (AWS - Secure)
- **ECS Fargate**: ~$30-50/month
- **Load Balancer**: ~$20/month
- **Secrets Manager**: ~$1/month
- **Firebase (New)**: ~$20-50/month
- **Total Estimated**: **$70-120/month** (vs. hundreds in unauthorized charges)

---

## 🤝 **Contributing**

### Development Setup
```bash
# Clone repository
git clone https://github.com/your-username/airavat.git
cd airavat

# Backend setup
cd ai_fastapi_agent/ai-services
python -m venv env
source env/bin/activate  # Linux/Mac
pip install -r requirements.txt

# Frontend setup
cd ../../airavat_flutter
flutter pub get
```

### Code Style
- **Python**: Black formatter, PEP 8
- **Dart/Flutter**: Official Dart style guide
- **JavaScript**: ESLint + Prettier

---

## 📞 **Support & Documentation**

### Documentation
- [🚨 Security Migration Guide](SECURITY_MIGRATION_GUIDE.md) - **URGENT**
- [🚀 Deployment Guide](DEPLOYMENT_GUIDE.md)
- [🔬 Digital Twin Implementation](DIGITAL_TWIN_IMPLEMENTATION.md)
- [📋 Production Features](PRODUCTION_FEATURES.md)

### Emergency Contacts
- **Security Issues**: Follow [SECURITY_MIGRATION_GUIDE.md](SECURITY_MIGRATION_GUIDE.md)
- **Technical Support**: Create GitHub issue
- **Medical Compliance**: Contact project maintainers

---

## ⚖️ **Legal & Compliance**

### Medical Disclaimers
- **Not FDA Approved**: For research and simulation purposes only
- **Medical Professional Required**: Always consult qualified healthcare providers
- **HIPAA Compliance**: Follows medical data protection standards
- **Research Use**: Designed for academic and clinical research

### License
This project is licensed under the MIT License - see the [LICENSE](LICENSE) file for details.

---

## 🎯 **Success Metrics**

### Technical Metrics
- **Uptime**: 99.9% availability target
- **Response Time**: <200ms API response target
- **Accuracy**: >95% biomarker analysis accuracy
- **Security**: Zero data breaches post-migration

### Medical Impact
- **Patient Engagement**: Improved treatment adherence
- **Clinical Efficiency**: Reduced consultation time
- **Predictive Accuracy**: Enhanced treatment outcome prediction
- **Research Value**: Accelerated medical research capabilities

---

**🚨 IMMEDIATE ACTION REQUIRED: If you're seeing this README, follow the [SECURITY_MIGRATION_GUIDE.md](SECURITY_MIGRATION_GUIDE.md) immediately to secure the platform and prevent further unauthorized charges.**
