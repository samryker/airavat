import os
from dotenv import load_dotenv
from langchain_google_genai import ChatGoogleGenerativeAI

load_dotenv()
gemini = ChatGoogleGenerativeAI(model="gemini-2.0-flash-thinking-exp-01-21", google_api_key=os.getenv("GEMINI_API_KEY"))

def generate_plan(context: dict) -> str:
    """
    LLM creates a forward-looking treatment goal plan.
    """
    hemoglobin = context.get("hemoglobin", 10)
    risk_notes = context.get("risk_assessment", "No acute risk")
    therapy = context.get("therapy", "Everolimus 5mg daily")

    prompt = f"""
You are a digital oncologist agent. 
Patient is on {therapy}. Current hemoglobin: {hemoglobin}.

Clinical risk summary: {risk_notes}.

Please:
1. Suggest immediate steps
2. Timeline for next labs or imaging
3. Dietary reminder
4. Motivation for patient

Return in plain bullet points.
"""

    return gemini.invoke(prompt)
