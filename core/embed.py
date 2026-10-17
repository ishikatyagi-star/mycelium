"""Local sentence embeddings (no API key needed): BAAI/bge-small-en-v1.5, 384 dims."""
from __future__ import annotations

from functools import lru_cache

DIM = 384


@lru_cache(maxsize=1)
def _model():
    from fastembed import TextEmbedding
    return TextEmbedding("BAAI/bge-small-en-v1.5")


@lru_cache(maxsize=4096)
def _embed_one(text: str) -> tuple[float, ...]:
    return tuple(float(x) for x in next(iter(_model().embed([text]))))


def embed(text: str) -> list[float]:
    return list(_embed_one(" ".join(text.split())[:2000]))


def embed_many(texts: list[str]) -> list[list[float]]:
    return [embed(t) for t in texts]
