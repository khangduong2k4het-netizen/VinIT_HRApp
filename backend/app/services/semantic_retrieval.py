"""Merge lexical and BGE/pgvector candidate chunks for LLM fallback.

Semantic similarity is a *retrieval* signal only.  It may add candidate
chunks for the adjudicating LLM, but it never creates a rule finding and
never changes a deterministic outcome.
"""

from __future__ import annotations

from typing import Any

from app.services.embedding import cosine_similarity


def retrieve_semantic_candidates(
    query_vector: list[float],
    chunks: list[dict[str, Any]],
    chunk_vectors: list[list[float]],
    *,
    min_similarity: float = 0.0,
    top_k: int = 5,
) -> list[dict[str, Any]]:
    """Rank in-memory chunk vectors; used when pgvector is unavailable."""
    scored: list[dict[str, Any]] = []
    for chunk, vector in zip(chunks, chunk_vectors, strict=True):
        similarity = cosine_similarity(query_vector, vector)
        if similarity < min_similarity:
            continue
        scored.append({
            **chunk,
            "semantic_similarity": round(float(similarity), 6),
            "retrieval_source": "SEMANTIC",
        })
    scored.sort(key=lambda item: (-float(item["semantic_similarity"]), str(item.get("chunk_id") or "")))
    return scored[:top_k]


def merge_candidate_chunks(
    lexical_chunks: list[dict[str, Any]],
    semantic_chunks: list[dict[str, Any]],
    *,
    limit: int = 5,
) -> list[dict[str, Any]]:
    """Merge lexical and semantic candidates into at most ``limit`` chunks.

    Chunks found by both retrievers come first (strongest corroboration),
    then semantic-only chunks by similarity, then lexical-only chunks in
    their existing deterministic order.
    """
    lexical_by_id = {
        str(chunk.get("chunk_id")): chunk
        for chunk in lexical_chunks if chunk.get("chunk_id")
    }
    semantic_by_id = {
        str(chunk.get("chunk_id")): chunk
        for chunk in semantic_chunks if chunk.get("chunk_id")
    }

    both: list[dict[str, Any]] = []
    semantic_only: list[dict[str, Any]] = []
    for chunk_id, semantic in semantic_by_id.items():
        if chunk_id in lexical_by_id:
            both.append({
                **lexical_by_id[chunk_id],
                "semantic_similarity": semantic.get("semantic_similarity"),
                "retrieval_source": "LEXICAL+SEMANTIC",
            })
        else:
            semantic_only.append({**semantic, "retrieval_source": "SEMANTIC"})
    both.sort(key=lambda item: (-float(item.get("semantic_similarity") or 0), str(item.get("chunk_id") or "")))
    semantic_only.sort(key=lambda item: (-float(item.get("semantic_similarity") or 0), str(item.get("chunk_id") or "")))
    lexical_only = [
        {**chunk, "retrieval_source": chunk.get("retrieval_source") or "LEXICAL"}
        for chunk_id, chunk in lexical_by_id.items()
        if chunk_id not in semantic_by_id
    ]
    return (both + semantic_only + lexical_only)[:limit]
