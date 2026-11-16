"""
app/llm.py — Single wrapper around the LLM API

CORE RULE:
"The LLM talks. Rules decide. Humans act."
- LLM output is text only. It must never create flags, change prescriptions, give diagnoses, or advise on doses.
- Every other module calls `generate()`. If you change provider, only this file changes.
- C13 Resilience: LLM failures are logged and the system keeps working.
"""

import os
import logging
import concurrent.futures
from google import genai
from dotenv import load_dotenv

load_dotenv(os.path.join(os.path.dirname(__file__), "../.env"))
load_dotenv(".env")
logger = logging.getLogger(__name__)

_client = None


def get_client():
    global _client
    if _client is None:
        api_key = os.getenv("LLM_API_KEY") or os.getenv("GOOGLE_API_KEY")
        _client = genai.Client(api_key=api_key)
    return _client


def generate(system: str, user: str, timeout: int = 12) -> str:
    """Generate text using the configured LLM with strict 12s timeout.
    
    System prompt and user prompt are combined.
    Returns plain string output.
    """
    def _call():
        client = get_client()
        model_name = os.getenv("LLM_MODEL", "gemini-3.5-flash-lite")
        resp = client.models.generate_content(
            model=model_name,
            contents=f"{system}\n\n{user}",
        )
        return resp.text or ""

    try:
        with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
            future = executor.submit(_call)
            return future.result(timeout=timeout)
    except concurrent.futures.TimeoutError:
        logger.error(f"LLM generation timed out after {timeout}s")
        return "TIMEOUT"
    except Exception as e:
        logger.error(f"LLM generation failed: {e}")
        return "NOT_IN_DOCUMENTS"
