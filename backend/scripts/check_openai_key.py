"""
Simple script to validate an OpenAI API key.
Usage: python check_openai_key.py [API_KEY]
       Or set OPENAI_API_KEY in your .env file and run without arguments.
"""
import sys
import os

# Load .env from backend directory
env_path = os.path.join(os.path.dirname(__file__), "..", ".env")
if os.path.exists(env_path):
    from dotenv import load_dotenv
    load_dotenv(env_path)

try:
    from openai import OpenAI
except ImportError:
    print("[ERROR] 'openai' package not installed. Run: pip install openai")
    sys.exit(1)


def check_key(api_key: str) -> bool:
    client = OpenAI(api_key=api_key)
    try:
        client.models.list()
        return True
    except Exception as e:
        print(f"[INVALID] {e}")
        return False


if __name__ == "__main__":
    api_key = sys.argv[1] if len(sys.argv) > 1 else os.getenv("OPENAI_API_KEY", "")

    if not api_key:
        print("[ERROR] No API key provided. Pass it as an argument or set OPENAI_API_KEY in .env")
        sys.exit(1)

    masked = api_key[:8] + "..." + api_key[-4:]
    print(f"Checking key: {masked}")

    if check_key(api_key):
        print("[VALID] API key is active and working.")
    else:
        print("[INVALID] API key check failed.")
