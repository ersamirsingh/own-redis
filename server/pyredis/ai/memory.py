"""In-memory Semantic Memory and Vector Cosine Similarity Search."""

import math
import time
import uuid
from dataclasses import dataclass, field
from typing import Any, Dict, List, Optional
from pyredis.ai.provider import gemini_provider


@dataclass
class VectorEntry:
    """Represents an embedded text vector record."""
    id: str
    text: str
    embedding: List[float]
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)

    def to_dict(self, include_embedding: bool = False) -> Dict[str, Any]:
        data: Dict[str, Any] = {
            "id": self.id,
            "text": self.text,
            "metadata": self.metadata,
            "created_at": self.created_at,
        }
        if include_embedding:
            data["embedding"] = self.embedding
        return data


def cosine_similarity(v1: List[float], v2: List[float]) -> float:
    """Compute cosine similarity between two numeric vectors."""
    if not v1 or not v2 or len(v1) != len(v2):
        return 0.0

    dot = sum(a * b for a, b in zip(v1, v2))
    norm_a = math.sqrt(sum(a * a for a in v1))
    norm_b = math.sqrt(sum(b * b for b in v2))

    if norm_a == 0.0 or norm_b == 0.0:
        return 0.0

    return round(dot / (norm_a * norm_b), 4)


class SemanticMemoryStore:
    """Vector database index for semantic retrieval and context augmentation."""

    def __init__(self) -> None:
        self._entries: Dict[str, VectorEntry] = {}

    def add(
        self,
        text: str,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """Embed text and synchronously insert record into vector memory."""
        entry_id = id or f"mem-{uuid.uuid4().hex[:8]}"
        vec = embedding if embedding is not None else gemini_provider.embed_text(text)

        entry = VectorEntry(
            id=entry_id,
            text=text,
            embedding=vec,
            metadata=metadata or {},
        )
        self._entries[entry_id] = entry
        return entry_id

    async def add_async(
        self,
        text: str,
        id: Optional[str] = None,
        metadata: Optional[Dict[str, Any]] = None,
        embedding: Optional[List[float]] = None,
    ) -> str:
        """Embed text and asynchronously insert record into vector memory."""
        entry_id = id or f"mem-{uuid.uuid4().hex[:8]}"
        vec = embedding if embedding is not None else await gemini_provider.embed_text_async(text)

        entry = VectorEntry(
            id=entry_id,
            text=text,
            embedding=vec,
            metadata=metadata or {},
        )
        self._entries[entry_id] = entry
        return entry_id

    def search(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search entries by semantic cosine similarity against query text synchronously."""
        if not self._entries:
            return []

        query_vec = gemini_provider.embed_text(query)
        scored: List[Dict[str, Any]] = []

        for entry in self._entries.values():
            score = cosine_similarity(query_vec, entry.embedding)
            if score >= min_score:
                item = entry.to_dict(include_embedding=False)
                item["score"] = score
                scored.append(item)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    async def search_async(
        self,
        query: str,
        top_k: int = 5,
        min_score: float = 0.0,
    ) -> List[Dict[str, Any]]:
        """Search entries by semantic cosine similarity against query text asynchronously."""
        if not self._entries:
            return []

        query_vec = await gemini_provider.embed_text_async(query)
        scored: List[Dict[str, Any]] = []

        for entry in self._entries.values():
            score = cosine_similarity(query_vec, entry.embedding)
            if score >= min_score:
                item = entry.to_dict(include_embedding=False)
                item["score"] = score
                scored.append(item)

        scored.sort(key=lambda x: x["score"], reverse=True)
        return scored[:top_k]

    def delete(self, id: str) -> bool:
        """Delete vector record by id."""
        if id in self._entries:
            del self._entries[id]
            return True
        return False

    def list_entries(self, limit: int = 50) -> List[Dict[str, Any]]:
        """List stored memories in reverse chronological order."""
        entries = sorted(self._entries.values(), key=lambda e: e.created_at, reverse=True)
        return [e.to_dict(include_embedding=False) for e in entries[:limit]]

    def count(self) -> int:
        """Return total count of memory vectors."""
        return len(self._entries)

    def clear(self) -> None:
        """Clear all stored vectors (for testing)."""
        self._entries.clear()


# Global SemanticMemory singleton
semantic_memory = SemanticMemoryStore()
