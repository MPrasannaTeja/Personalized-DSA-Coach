import logging

from app.config import settings

logger = logging.getLogger(__name__)


def get_llm():
    groq_key = settings.groq_api_key.strip()
    logger.info("[LLM] groq_key present: %s, length: %s", bool(groq_key), len(groq_key))
    if groq_key:
        logger.info("[LLM] Using Groq")
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            temperature=0.7,
            max_tokens=1024,
        )
    else:
        logger.warning("[LLM] No GROQ_API_KEY — using Ollama")
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.7,
            num_predict=1024,
        )


def get_structured_llm():
    groq_key = settings.groq_api_key.strip()
    if groq_key:
        from langchain_groq import ChatGroq
        return ChatGroq(
            model="llama-3.3-70b-versatile",
            api_key=groq_key,
            temperature=0.1,
            max_tokens=512,
        )
    else:
        from langchain_ollama import ChatOllama
        return ChatOllama(
            model=settings.ollama_model,
            base_url=settings.ollama_base_url,
            temperature=0.1,
            num_predict=512,
            format="json",
        )
