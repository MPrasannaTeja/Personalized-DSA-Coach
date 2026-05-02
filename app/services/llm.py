"""
LLM factory — automatically picks the right provider:
  - If GROQ_API_KEY is set in environment -> use Groq (cloud deployment)
  - Otherwise -> use Ollama (local development)

This means:
  Railway/cloud = Groq (free, fast, no GPU needed)
  Your laptop   = Ollama (free, local, no API key needed)
"""

import os


def get_llm():
    """Main LLM for coach conversations."""
    if os.environ.get("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        from app.config import settings
        return ChatGroq(
            model="llama3-70b-8192",
            api_key=settings.groq_api_key,
            temperature=0.7,
            max_tokens=1024,
        )
    else:
        from langchain_ollama import ChatOllama
        from app.config import settings
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.7,
            num_predict=1024,
        )


def get_structured_llm():
    """Lower temperature for JSON outputs (notes validation, daily assignments)."""
    if os.environ.get("GROQ_API_KEY"):
        from langchain_groq import ChatGroq
        from app.config import settings
        return ChatGroq(
            model="llama3-70b-8192",
            api_key=settings.groq_api_key,
            temperature=0.1,
            max_tokens=512,
        )
    else:
        from langchain_ollama import ChatOllama
        from app.config import settings
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
            num_predict=512,
            format="json",
        )
