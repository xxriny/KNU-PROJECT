"""API 키 로딩 및 httpx 헤더 오류 재현 스크립트"""
import os, sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from dotenv import load_dotenv
load_dotenv(os.path.join(os.path.dirname(__file__), ".env"), encoding="utf-8")

key = os.environ.get("GEMINI_API_KEY", "")
print(f"Key loaded: {repr(key[:12])}...")
print(f"Key is ASCII: {key.isascii()}")
print(f"Key length: {len(key)}")
print(f"Key bytes (first 20): {key.encode('utf-8')[:20]}")

# 어떤 문자가 non-ASCII인지 찾기
for i, c in enumerate(key):
    if ord(c) > 127:
        print(f"  Non-ASCII char at pos {i}: {repr(c)} (ord={ord(c)})")

# google-genai SDK 클라이언트 생성 테스트
try:
    from google import genai
    client = genai.Client(api_key=key)
    print("Client created OK")
except Exception as e:
    print(f"Client creation FAILED: {e}")

# LangChain ChatGoogleGenerativeAI 테스트
try:
    from langchain_google_genai import ChatGoogleGenerativeAI
    llm = ChatGoogleGenerativeAI(model="gemini-2.5-flash", google_api_key=key)
    print("LangChain LLM created OK")
except Exception as e:
    print(f"LangChain LLM creation FAILED: {e}")
