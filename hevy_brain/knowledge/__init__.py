"""Read-only bridge into the atlas-pipeline knowledge layer.

Exposes the knowledge base that grounds coach guidance in cited claims.
This package is read-only by construction and never touches `sources/`.
"""

from __future__ import annotations

from .reader import (
    Claim,
    KnowledgeAccessError,
    KnowledgeBase,
    RetrievalResult,
    TopicPage,
)

__all__ = [
    "Claim",
    "KnowledgeAccessError",
    "KnowledgeBase",
    "RetrievalResult",
    "TopicPage",
]
