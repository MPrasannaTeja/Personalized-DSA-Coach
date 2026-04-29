"""
LLM singleton using Ollama (local, free, no API key needed).

Make sure Ollama is running before starting the server:
    ollama serve

And you have a model pulled:
    ollama pull llama3.1       (recommended, ~4GB)
    ollama pull llama3         (older, also fine)
    ollama pull mistral        (lighter, ~4GB)
    ollama pull phi3           (lightest, ~2GB, good for low RAM)

Change OLLAMA_MODEL in .env to switch models without touching code.
"""

from functools import lru_cache

from langchain_ollama import ChatOllama

from app.config import settings


@lru_cache(maxsize=1)
def get_llm() -> ChatOllama:
    """Main LLM — used for all coach conversations."""
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.7,
        num_predict=1024,
    )


@lru_cache(maxsize=1)
def get_structured_llm() -> ChatOllama:
    """Lower temperature for JSON outputs (notes validation, daily assignments)."""
    return ChatOllama(
        model=settings.ollama_model,
        base_url=settings.ollama_base_url,
        temperature=0.1,
        num_predict=512,
        format="json",
    )
