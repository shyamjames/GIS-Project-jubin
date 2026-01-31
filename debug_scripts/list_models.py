import google.generativeai as genai
import os
from dotenv import load_dotenv
import sys

# Add parent directory to path to find .env easily if running from here
sys.path.append(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Load .env from project root
dotenv_path = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), '.env')
load_dotenv(dotenv_path)

api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("API Key not found in .env")
    print(f"Checked path: {dotenv_path}")
else:
    print(f"API Key found: {api_key[:5]}...")
    genai.configure(api_key=api_key)
    try:
        print("Listing available models that support 'generateContent':")
        found = False
        for m in genai.list_models():
            if 'generateContent' in m.supported_generation_methods:
                print(f"- {m.name}")
                found = True
        
        if not found:
            print("No models found with 'generateContent' capability.")
            
    except Exception as e:
        print(f"Error listing models: {e}")
