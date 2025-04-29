# image_validate.py

import google.generativeai as genai
from PIL import Image
import base64
import io

# Configure Gemini API
genai.configure(api_key="AIzaSyDKlh1S1jfkZhW-e6cZDSaWFEfEb8WSvOM")  # Replace with your actual API key

# Load the model
model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-04-17")

def verify_image_matches_description(image_data_base64: str, description: str) -> bool:
    """
    Verifies whether the given image matches the textual description using Gemini.

    Args:
        image_data_base64 (str): Base64-encoded image.
        description (str): Text description to validate.

    Returns:
        bool: True if image and description match, False otherwise.
    """
    # Convert base64 to PIL image
    image_bytes = base64.b64decode(image_data_base64)
    image = Image.open(io.BytesIO(image_bytes))

    prompt = f"Does this image match the description: '{description}'? Answer with 'yes' or 'no'."

    try:
        response = model.generate_content([image, prompt], stream=False)
        answer = response.text.strip().lower()
        return 'yes' in answer
    except Exception as e:
        print("Image validation error:", e)
        return False
