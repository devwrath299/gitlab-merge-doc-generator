"""
LLM Client Service
==================
Provides a shared LLM client and a generic call helper.
Uses the OpenAI-compatible API with configurable base URL and model.
"""

import logging

from openai import OpenAI

from config import LLM_API_KEY, LLM_BASE_URL, LLM_MODEL

logger = logging.getLogger(__name__)

# Shared client instance
_client: OpenAI | None = None


def get_llm_client() -> OpenAI:
    """Return a singleton OpenAI client instance."""
    global _client
    if _client is None:
        _client = OpenAI(
            api_key=LLM_API_KEY,
            base_url=LLM_BASE_URL,
        )
    return _client


def call_llm(
    system_prompt: str,
    user_prompt: str,
    max_tokens: int = 16000,
    temperature: float = 0.2,
) -> str:
    """
    Make a single LLM call with the given system and user prompts.
    Returns the assistant's response text.
    Raises on API errors.
    """
    client = get_llm_client()

    logger.info(
        "🤖 Calling LLM (model=%s, max_tokens=%d, temp=%.1f) ...",
        LLM_MODEL, max_tokens, temperature,
    )
    logger.debug(
        "System prompt length: %d chars, User prompt length: %d chars",
        len(system_prompt), len(user_prompt),
    )

    try:
        response = client.chat.completions.create(
            model=LLM_MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=temperature,
            max_tokens=max_tokens,
        )
        result = response.choices[0].message.content
        logger.info("✅ LLM response received (%d chars).", len(result))
        return result

    except Exception as e:
        logger.error("❌ LLM API error: %s", e)
        raise


def load_skill(skill_path: str) -> str:
    """Load a skill SKILL.md file and return its content as a system prompt."""
    with open(skill_path, "r", encoding="utf-8") as f:
        return f.read()
