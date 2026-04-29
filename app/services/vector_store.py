"""
ChromaDB vector store wrapper.

Responsibilities
----------------
- Upsert a user's pattern notes as embeddings when they write them.
- Query similar past notes when the agent needs to tailor a hint
  based on the user's historical blind spots.

All documents are namespaced per user_id so one collection
serves every learner.
"""

import logging
from typing import Optional

import chromadb
from chromadb.config import Settings as ChromaSettings

from app.config import settings

logger = logging.getLogger(__name__)

# ── Singleton client + collection ─────────────────────────────────────────────
_client: Optional[chromadb.AsyncHttpClient] = None
_collection = None


async def _get_collection():
    global _client, _collection
    if _collection is None:
        _client = await chromadb.AsyncHttpClient(
            host=settings.chroma_host,
            port=settings.chroma_port,
            settings=ChromaSettings(anonymized_telemetry=False),
        )
        _collection = await _client.get_or_create_collection(
            name=settings.chroma_collection_name,
            # Use cosine similarity — better for semantic text matching
            metadata={"hnsw:space": "cosine"},
        )
        logger.info("ChromaDB collection '%s' ready.", settings.chroma_collection_name)
    return _collection


# ── Public API ────────────────────────────────────────────────────────────────

async def upsert_pattern_note(
    doc_id: str,
    user_id: str,
    topic_id: str,
    pattern_name: str,
    note_text: str,
    problem_name: Optional[str] = None,
) -> None:
    """
    Store (or update) a pattern note as an embedding in ChromaDB.

    doc_id is the PatternNote.id from PostgreSQL — used for idempotent upserts.
    """
    collection = await _get_collection()

    document = (
        f"Pattern: {pattern_name}\n"
        f"Topic: {topic_id}\n"
        f"Problem: {problem_name or 'unknown'}\n"
        f"Notes: {note_text}"
    )

    await collection.upsert(
        ids=[doc_id],
        documents=[document],
        metadatas=[{
            "user_id": user_id,
            "topic_id": topic_id,
            "pattern_name": pattern_name,
            "problem_name": problem_name or "",
        }],
    )
    logger.debug("Upserted note %s for user %s into ChromaDB.", doc_id, user_id)


async def query_similar_notes(
    user_id: str,
    query_text: str,
    topic_id: Optional[str] = None,
    n_results: int = 5,
) -> list[dict]:
    """
    Find the most semantically similar notes this user has written before.

    Returns a list of dicts with keys: document, pattern_name, topic_id, distance.
    Lower distance = more similar.
    """
    collection = await _get_collection()

    # Filter to this user (and optionally this topic)
    where: dict = {"user_id": {"$eq": user_id}}
    if topic_id:
        where = {
            "$and": [
                {"user_id": {"$eq": user_id}},
                {"topic_id": {"$eq": topic_id}},
            ]
        }

    try:
        results = await collection.query(
            query_texts=[query_text],
            n_results=n_results,
            where=where,
            include=["documents", "metadatas", "distances"],
        )
    except Exception as exc:
        # ChromaDB raises if the collection is empty — handle gracefully
        logger.warning("ChromaDB query failed (possibly empty): %s", exc)
        return []

    if not results["documents"] or not results["documents"][0]:
        return []

    combined = []
    for doc, meta, dist in zip(
        results["documents"][0],
        results["metadatas"][0],
        results["distances"][0],
    ):
        combined.append({
            "document": doc,
            "pattern_name": meta.get("pattern_name", ""),
            "topic_id": meta.get("topic_id", ""),
            "problem_name": meta.get("problem_name", ""),
            "distance": round(dist, 4),
        })

    return combined


async def delete_user_notes(user_id: str) -> None:
    """Hard-delete all notes for a user (e.g. account deletion)."""
    collection = await _get_collection()
    await collection.delete(where={"user_id": {"$eq": user_id}})
    logger.info("Deleted all ChromaDB documents for user %s.", user_id)
