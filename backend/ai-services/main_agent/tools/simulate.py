def simulate_risk(data: dict) -> str:
    """
    Analyze biomarker data and return clinical risk interpretation.
    """
    hemoglobin = data.get("hemoglobin", 12)
    platelets = data.get("platelets", 250)
    wbc = data.get("wbc", 5.5)

    risk = []
    if hemoglobin < 9.0:
        risk.append("⚠️ Hemoglobin is low. Anemia risk present.")
    if platelets < 150:
        risk.append("⚠️ Thrombocytopenia possible. Monitor for bleeding.")
    if wbc > 11:
        risk.append("⚠️ Elevated WBC. Potential infection or inflammation.")
    if not risk:
        return "✅ Biomarker parameters are currently stable."

    return "\n".join(risk)
