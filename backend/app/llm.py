"""LLM configuration: OpenAI-compatible API with retry logic."""

from __future__ import annotations

import os
from dotenv import load_dotenv
from langchain_openai import ChatOpenAI
from langchain_core.language_models.chat_models import BaseChatModel

load_dotenv()

_OPENAI_BASE_URL = os.getenv("OPENAI_BASE_URL", "https://ai-gateway.ab-inbev.cn/model/cn397/v1")
_OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
_MODEL_NAME = os.getenv("MODEL_NAME", "gpt-4o")
# OpenAI SDK built-in retry: handles 429, 5xx with exponential backoff
_MAX_RETRIES = int(os.getenv("LLM_MAX_RETRIES", "3"))


def get_chat_model(temperature: float = 0.1, streaming: bool = False) -> BaseChatModel:
    """Return a chat model instance.

    The OpenAI SDK handles 429 rate-limit retries automatically via max_retries.
    For non-standard error formats from custom gateways, supervisor-level retry
    logic provides additional coverage.
    """
    print(f"[LLM] Using OpenAI-compatible API: {_MODEL_NAME} at {_OPENAI_BASE_URL}")
    return ChatOpenAI(
        model=_MODEL_NAME,
        openai_api_key=_OPENAI_API_KEY,
        openai_api_base=_OPENAI_BASE_URL,
        temperature=temperature,
        streaming=streaming,
        max_retries=_MAX_RETRIES,
    )