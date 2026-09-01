import os
from langchain_google_genai import ChatGoogleGenerativeAI
from backend.config import settings


def get_gemini_llm(timeout: float = 6.0, max_output_tokens: int = 512) -> ChatGoogleGenerativeAI:
    """
    Returns an instance of ChatGoogleGenerativeAI configured with Gemini model
    and settings from application configuration.
    """
    api_key = settings.GEMINI_API_KEY or os.getenv("GEMINI_API_KEY", "")
    if not api_key:
        api_key = "MOCK_GEMINI_API_KEY"

    return ChatGoogleGenerativeAI(
        model="gemini-2.5-flash",
        google_api_key=api_key,
        temperature=0.2,
        timeout=timeout,
        max_retries=1,
        max_output_tokens=max_output_tokens,
    )


