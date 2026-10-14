"""Original reciprocal-rank-fusion adapter for externally retrieved documents."""
from __future__ import annotations
from typing import Any


def reciprocal_rank_fusion(
    rankings: list[list[dict[str, Any]]], *, k: int = 60, limit: int = 10
) -> list[dict[str, Any]]:
    if k < 1 or limit < 1:
        raise ValueError("k and limit must be positive")
    scores: dict[str, float] = {}
    docs: dict[str, dict[str, Any]] = {}
    for ranking in rankings:
        seen: set[str] = set()
        for position, document in enumerate(ranking, start=1):
            identifier = document.get("id")
            if not isinstance(identifier, str) or not identifier:
                raise ValueError("Every document requires a stable id")
            if identifier in seen:
                continue
            seen.add(identifier)
            docs.setdefault(identifier, document)
            scores[identifier] = scores.get(identifier, 0.0) + 1.0 / (k + position)
    return [
        {"document": docs[identifier], "score": scores[identifier]}
        for identifier in sorted(scores, key=lambda key: (-scores[key], key))[:limit]
    ]
