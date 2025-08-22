import os
import google.generativeai as genai

# Gemini API disabled for security reasons
print("Gemini API has been disabled for security reasons.")
print("API key removed from codebase.")

# genai.configure(api_key=os.getenv("GEMINI_API_KEY"))  # Disabled
# for m in genai.list_models():  # Disabled
#   if 'generateContent' in m.supported_generation_methods:
#     print(m.name)
