import os
from dotenv import load_dotenv
import google.generativeai as genai

load_dotenv()
genai.configure(api_key=os.getenv("GEMINI_API_KEY"))

for model in genai.list_models():
    if "generateContent" in model.supported_generation_methods:
        print(f"✅ {model.name} — supports generateContent")
    else:
        print(f"❌ {model.name} — not usable for generation")
