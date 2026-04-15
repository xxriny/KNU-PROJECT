import os
from google import genai
from dotenv import load_dotenv

load_dotenv()

def list_models():
    api_key = os.environ.get("GEMINI_API_KEY")
    client = genai.Client(api_key=api_key)
    print("\nAvailable Models:")
    # genai SDK (v0.x) uses a different structure
    for model in client.models.list():
        print(f"- Name: {model.name}")
        # print(f"  DisplayName: {model.display_name}")

if __name__ == "__main__":
    list_models()
