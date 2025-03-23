# airavat
A platform which is actually a digital twin of a person with the same bio informatics of a live person. Basically the brain is AI which enforced with LLM and a reinforcement model so that the correct stimulations are awarded and the wrong ones are not repeated. This is to test the drug stimulations on a body and then it can be applied in body .
| **Component**         | **Technology / Tool**                     | **Purpose**                                                             |
|-----------------------|-------------------------------------------|-------------------------------------------------------------------------|
| **Database**          | Firebase Firestore                        | Secure, real-time data sync for patient vitals, reports, drugs         |
| **Storage**           | Firebase Storage                          | For storing CBC PDFs, CT scans, reports                                |
| **Auth**              | Firebase Auth                             | Role-based login: patient, caregiver, oncologist                       |
| **Compute (ML logic)**| Cloud Functions (Firebase) / AWS Lambda   | Trigger treatment simulation, drug synergy, alerts                     |
| **Monitoring & Logging**| Firebase Analytics / Stackdriver        | Track usage, system behavior, custom patient metrics                   |
| **Frontend (Phase 2)**| Flutter (Mobile/Web)                      | Cross-platform UI for patient & doctor dashboards                      |


🧠 Modules to Implement
🔹 1. Patient Profile Microservice
Stores age, gender, blood type, current treatments, known resistances, dietary flags.

Accessible via Flutter or API.

🔹 2. Biomarker Uploader + Parser
Manual upload form for CBC, EMT markers, etc.

Auto-extracts key values from lab reports using ML or regex parsers.

Stored in Firestore per patientID, timestamped.

🔹 3. Therapy Simulation Engine (Serverless Function)
Triggered via:

New lab report upload

Scheduled (daily/weekly)

Uses AI to simulate:

Tumor growth/shrinkage under Everolimus for case study A.This can be changed to other therapies for cancer.

Drug synergy scores

Apoptosis likelihood

EMT reversal prediction

Returns recommended action, alert level

🔹 4. Drug Discovery & Combo Synergy Engine
Runs when triggered from dashboard:

Uses RDKit + DeepChem on backend (Lambda container or Cloud Run)

Inputs: patient tumor behavior, CTC markers, resistance profile

Outputs: novel compound match suggestions, dose modulator simulations

🔹 5. Alert System (Smart Monitoring)
Flags critical events:

Hemoglobin drop

Platelet fall

CTC spike risk

Sends push/email alerts

Auto-logs suggestions in report

🔹 6. Report Generator
Bi-weekly summary to:

Email doctor

Patient dashboard (Flutter)

Auto-populates graphs of Hb, WBC, weight, immunity trend.

** Directory Structure *** 

/cloud_twin/
├── functions/                  # Firebase/Cloud Functions for ML & AI logic
│   ├── simulateTherapy.js
│   ├── predictApoptosis.js
│   └── drugDiscovery.js
├── firestore.rules             # Access control
├── database/
│   └── patient_profiles/
│   └── biomarkers/
│   └── treatments/
├── storage/
│   └── reports/
│   └── scans/
├── pubsub_triggers/            # Triggers on report upload or time
├── ui/                         # For future Flutter app
│   └── flutter_twin_app/
└── README.md


