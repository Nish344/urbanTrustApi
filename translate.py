# translate.py

import google.generativeai as genai
import os
# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API"))
# Load the model
model = genai.GenerativeModel(model_name="gemini-1.5-pro-latest")

def translate_to_kannada(text: str) -> str:
    """
    Translates English text to Kannada using Gemini.

    Args:
        text (str): The English text to translate.

    Returns:
        str: The translated Kannada text.
    """
    prompt = f"Translate this to Kannada and provide only one line of translation: '{text}'"
    
    try:
        response = model.generate_content(prompt)
        return response.text.strip()
    except Exception as e:
        print("Translation error:", e)
        return ""
