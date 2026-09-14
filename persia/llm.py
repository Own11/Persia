import os
from google import genai
from google.genai import types
from dotenv import load_dotenv

load_dotenv()

# We will use gemini-2.5-flash-lite as the default model
MODEL = "gemini-3.5-flash-lite"

def get_client() -> genai.Client:
    api_key = os.getenv("GEMINI_API_KEY")
    if not api_key:
        raise ValueError("GEMINI_API_KEY environment variable is not set. Please set it in a .env file or environment.")
    return genai.Client(api_key=api_key)
