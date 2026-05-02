"""
LLM factory — automatically picks the right provider:
  - If GROQ_API_KEY is set in environment -> use Groq (cloud deployment)
  - Otherwise -> use Ollama (local development)

This means:
  Railway/cloud = Groq (free, fast, no GPU needed)
  Your laptop   = Ollama (free, local, no API key needed)
"""

import logging
logger = logging.getLogger(__name__)


def get_llm():
    """Main LLM for coach conversations."""
    from app.config import settings
    
    logger.info(f"[DEBUG] groq_api_key: '{settings.groq_api_key}' | truthy: {bool(settings.groq_api_key)}")
    
    if settings.groq_api_key and settings.groq_api_key.strip():
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=settings.groq_api_key,
            temperature=0.7,
            max_tokens=1024,
        )
    else:
        logger.warning("[LLM] GROQ_API_KEY not set or empty, falling back to Ollama")
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.7,
            num_predict=1024,
        )


def get_structured_llm():
    """Lower temperature for JSON outputs (notes validation, daily assignments)."""
    from app.config import settings
    
    logger.info(f"[DEBUG] groq_api_key: '{settings.groq_api_key}' | truthy: {bool(settings.groq_api_key)}")
    
    if settings.groq_api_key and settings.groq_api_key.strip():
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=settings.groq_api_key,
            temperature=0.1,
            max_tokens=512,
        )
    else:
        logger.warning("[LLM] GROQ_API_KEY not set or empty, falling back to Ollama")
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
            num_predict=512,
            format="json",
        )
