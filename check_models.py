# check_models.py
import os
import google.generativeai as genai
from dotenv import load_dotenv

# .env file se key load karo
load_dotenv()
api_key = os.getenv("GEMINI_API_KEY")

if not api_key:
    print("GEMINI_API_KEY not found in .env file!")
else:
    try:
        genai.configure(api_key=api_key)
        print("Fetching available models for your API key...\n")
        
        # Google se pucho ki kaunse models available hain
        for model in genai.list_models():
            # Hum sirf un models ko dekhenge jo 'generateContent' support karte hain
            if 'generateContent' in model.supported_generation_methods:
                print(f"Model Name: {model.name}")
                print("-" * 20)

    except Exception as e:
        print(f"An error occurred: {e}")