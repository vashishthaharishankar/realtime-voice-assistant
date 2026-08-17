"""Qdrant-backed knowledge search for Kotak Prime documents."""

from __future__ import annotations

import logging
from pathlib import Path
from typing import Any

from openai import OpenAI
from qdrant_client import QdrantClient
from qdrant_client.http import models as qmodels

from app.config import get_settings

logger = logging.getLogger("kotak-prime-voice")

ROOT = Path(__file__).resolve().parent.parent.parent
KNOWLEDGE_DIR = ROOT / "knowledge_base"


def _client() -> QdrantClient | None:
    settings = get_settings()
    if not settings.qdrant_api_key or not settings.qdrant_url:
        return None
    return QdrantClient(url=settings.qdrant_url, api_key=settings.qdrant_api_key)


def search_knowledge(query: str, limit: int = 4) -> dict[str, Any]:
    settings = get_settings()
    client = _client()
    if not client:
        return {
            "found": False,
            "message": "Knowledge base not configured. Set QDRANT_URL and QDRANT_API_KEY.",
            "results": [],
        }

    try:
        openai = OpenAI(api_key=settings.openai_api_key)
        embedding = openai.embeddings.create(
            model=settings.embedding_model,
            input=query,
        ).data[0].embedding

        if hasattr(client, "query_points"):
            response = client.query_points(
                collection_name=settings.qdrant_collection,
                query=embedding,
                limit=limit,
                with_payload=True,
            )
            hits = getattr(response, "points", response)
        else:
            hits = client.search(
                collection_name=settings.qdrant_collection,
                query_vector=embedding,
                limit=limit,
                with_payload=True,
            )
    except Exception as exc:  # noqa: BLE001
        logger.exception("Knowledge search failed")
        return {"found": False, "error": str(exc), "results": []}

    results: list[dict[str, str]] = []
    for hit in hits:
        payload = hit.payload or {}
        text = str(payload.get("text", "")).strip()
        if not text:
            continue
        results.append(
            {
                "source": str(payload.get("source", "")),
                "text": text[:1200],
                "score": round(float(hit.score or 0), 4),
            }
        )

    if not results:
        return {
            "found": False,
            "message": "No matching information in knowledge base. Do not guess beyond available data.",
            "results": [],
        }

    return {
        "found": True,
        "query": query,
        "results": results,
        "note": "Answer only from these excerpts. If insufficient, say information is not available.",
    }
