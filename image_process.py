# image_validate.py

import google.generativeai as genai
from PIL import Image
import base64
import io
import os
import json

# Configure Gemini API
genai.configure(api_key=os.getenv("GEMINI_API"))  # Replace with your actual API key

# Load the model
model = genai.GenerativeModel(model_name="gemini-2.5-flash-preview-04-17")

def verify_image_matches_description(image_data_base64: str, description: str, category: str) -> dict:
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

    prompt = f"Does this image match the description: '{description}' , category: '{category}'? Answer in given json format: category: (correct category identified: pothole, streetlight, or garbage), description: you derived, match: a bool of if it matches given category. Remember this will be parsed directly as a json or dict in python."

    try:
        response = model.generate_content([image, prompt], stream=False)
        answer = response.text.strip('```').lstrip('json')
        return  json.loads(answer)
    except Exception as e:
        print("Image validation error:", e)
        return False
    
def describe_image(image_data_base64: str) -> dict:
    """
    Recognizes the issue being reported in the image. 

    Args:
        image_data_base64 (str): Base64-encoded image.

    Returns:
        {
            category:recognised category from (pothole, garbage and streetlight)
            description:describe the given issues photo
            isIssue: True or False
        }
    """
    # Convert base64 to PIL image
    image_bytes = base64.b64decode(image_data_base64)
    image = Image.open(io.BytesIO(image_bytes))

    prompt = """Process this image and give the following output.
    Answer in given json format: 
    {
        category:recognised category from (pothole, garbage, streetlight or none if none of the above)
        description:describe the given issues photo
        isIssue:True or False
    }
    Remember this will be parsed directly as a json or dict in python."""

    try:
        response = model.generate_content([image, prompt], stream=False)
        answer = response.text.strip('```').lstrip('json')
        return  json.loads(answer)
    except Exception as e:
        print("Image recognition error:", e)
        return False

if __name__ == '__main__':
    s = ''
    with open("./images/pothole.png", "rb") as img:
        s = base64.b64encode(img.read())
    # answer = verify_image_matches_description(image_data_base64=s, description='pothole', category='pothole')
    answer = describe_image(s)
    print(answer)