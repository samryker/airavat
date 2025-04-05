def suggest_diet(data: dict) -> str:
    """
    Suggest safe cancer diet based on medication and side effects.
    """
    is_on_everolimus = data.get("meds", []).count("everolimus") > 0
    weight_loss = data.get("weight_loss", True)
    gastric = data.get("symptoms", {}).get("gastric_reflux", False)

    suggestions = ["🥦 Emphasize cruciferous vegetables (broccoli, cauliflower, cabbage)"]
    
    if is_on_everolimus:
        suggestions.append("🚫 Avoid grapefruit, pomegranate, guava (CYP3A4 inhibitors)")
        suggestions.append("💧 Ensure hydration: 2.5L+ per day to support kidney function")
    if weight_loss:
        suggestions.append("🍲 Add healthy fats: flaxseed oil, olive oil, and soaked almonds")
    if gastric:
        suggestions.append("⚠️ Avoid raw tomatoes, chilies, vinegar. Prefer steamed, alkaline foods")

    suggestions.append("✅ Prioritize oats, cooked green veggies, turmeric-infused lentils, coconut water")

    return "\n".join(suggestions)
