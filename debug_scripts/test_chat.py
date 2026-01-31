import google.generativeai as genai
import os
from dotenv import load_dotenv
import sys

# Load .env
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

api_key = os.getenv("GEMINI_API_KEY")
genai.configure(api_key=api_key)

# MODEL TO TEST
MODEL_NAME = 'gemini-flash-latest'

print(f"Testing model: {MODEL_NAME}...")

try:
    model = genai.GenerativeModel(MODEL_NAME)
    response = model.generate_content("Hello, are you online? Reply with 'Yes, I am functioning'.")
    print(f"Response: {response.text}")
    print("SUCCESS!")
except Exception as e:
    print(f"FAILURE: {e}")
