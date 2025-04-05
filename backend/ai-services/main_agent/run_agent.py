from tools.simulate import simulate_risk
from tools.suggest_diet import suggest_diet
from planner import generate_plan

# Example test patient input
biomarkers = {"hemoglobin": 8.4, "platelets": 140, "wbc": 12.1}
symptoms = {"gastric_reflux": True}
context = {
    "hemoglobin": biomarkers["hemoglobin"],
    "therapy": "Everolimus 5mg daily",
    "risk_assessment": simulate_risk(biomarkers)
}

print("🧪 Risk:\n", context["risk_assessment"])
print("\n🥗 Diet:\n", suggest_diet({"meds": ["everolimus"], "weight_loss": True, "symptoms": symptoms}))
print("\n📈 Plan:\n", generate_plan(context))
