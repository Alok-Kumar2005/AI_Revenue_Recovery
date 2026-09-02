from __future__ import annotations

import os
from typing import Any, TYPE_CHECKING
from backend.config import settings

if TYPE_CHECKING:
    from langchain_google_genai import ChatGoogleGenerativeAI


def get_gemini_llm(timeout: float = 6.0, max_output_tokens: int = 512) -> Any:
    """
    Returns an instance of ChatGoogleGenerativeAI configured with Gemini model
    and settings from application configuration.
    Lazily imports langchain_google_genai only when called.
    """
    from langchain_google_genai import ChatGoogleGenerativeAI

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
