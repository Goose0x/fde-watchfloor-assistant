from __future__ import annotations

import math
import re
from collections import Counter
from typing import Protocol

from watchfloor.models import Chunk, RetrievalHit

_TOKEN = re.compile(r"[a-z0-9]+", re.IGNORECASE)


def tokenize(text: str) -> list[str]:
    return [part.lower() for part in _TOKEN.findall(text)]


def lexical_score(query: str, text: str) -> float:
    """Deterministic bag-of-words cosine over hashed term counts. No network, no model."""
    q = Counter(tokenize(query))
    d = Counter(tokenize(text))
    if not q or not d:
        return 0.0
    dot = sum(weight * d[term] for term, weight in q.items())
    qn = math.sqrt(sum(weight * weight for weight in q.values()))
    dn = math.sqrt(sum(weight * weight for weight in d.values()))
    if qn == 0 or dn == 0:
        return 0.0
    return dot / (qn * dn)


class VectorStore(Protocol):
    def upsert(self, chunks: list[Chunk]) -> None: ...

    def search(self, query: str, *, compartments: frozenset[str], k: int = 5) -> list[RetrievalHit]: ...

    def get(self, chunk_id: str) -> Chunk | None: ...

    def all_chunks(self) -> list[Chunk]: ...


class InMemoryStore:
    """ACL-aware store. Compartment pre-filter happens before ranking, never after."""

    def __init__(self) -> None:
        self._chunks: dict[str, Chunk] = {}

    def upsert(self, chunks: list[Chunk]) -> None:
        for chunk in chunks:
            self._chunks[chunk.id] = chunk

    def search(self, query: str, *, compartments: frozenset[str], k: int = 5) -> list[RetrievalHit]:
        # Pre-filter by compartment labels, then rank the authorized set only.
        allowed = [chunk for chunk in self._chunks.values() if chunk.compartment in compartments]
        scored = [RetrievalHit(chunk=chunk, score=lexical_score(query, f"{chunk.title}\n{chunk.text}")) for chunk in allowed]
        scored.sort(key=lambda hit: hit.score, reverse=True)
        return [hit for hit in scored if hit.score > 0][:k]

    def get(self, chunk_id: str) -> Chunk | None:
        return self._chunks.get(chunk_id)

    def all_chunks(self) -> list[Chunk]:
        return list(self._chunks.values())


class PostgresStore:
    """Optional pgvector-backed store. Import and connection are deferred so tests stay offline."""

    def __init__(self, dsn: str) -> None:
        self._dsn = dsn
        self._ensure_schema()

    def _connect(self):
        import psycopg

        return psycopg.connect(self._dsn)

    def _ensure_schema(self) -> None:
        with self._connect() as conn:
            conn.execute("CREATE EXTENSION IF NOT EXISTS vector")
            conn.execute(
                """
                CREATE TABLE IF NOT EXISTS chunks (
                    id TEXT PRIMARY KEY,
                    doc_id TEXT NOT NULL,
                    title TEXT NOT NULL,
                    text TEXT NOT NULL,
                    compartment TEXT NOT NULL,
                    metadata JSONB NOT NULL DEFAULT '{}'::jsonb
                )
                """
            )
            conn.execute("CREATE INDEX IF NOT EXISTS chunks_compartment_idx ON chunks (compartment)")
            conn.commit()

    def upsert(self, chunks: list[Chunk]) -> None:
        import json

        with self._connect() as conn:
            for chunk in chunks:
                conn.execute(
                    """
                    INSERT INTO chunks (id, doc_id, title, text, compartment, metadata)
                    VALUES (%s, %s, %s, %s, %s, %s::jsonb)
                    ON CONFLICT (id) DO UPDATE SET
                        doc_id = EXCLUDED.doc_id,
                        title = EXCLUDED.title,
                        text = EXCLUDED.text,
                        compartment = EXCLUDED.compartment,
                        metadata = EXCLUDED.metadata
                    """,
                    (chunk.id, chunk.doc_id, chunk.title, chunk.text, chunk.compartment, json.dumps(chunk.metadata)),
                )
            conn.commit()

    def search(self, query: str, *, compartments: frozenset[str], k: int = 5) -> list[RetrievalHit]:
        # Pre-filter in SQL so unauthorized rows are never scored or returned.
        labels = list(compartments)
        with self._connect() as conn:
            rows = conn.execute(
                """
                SELECT id, doc_id, title, text, compartment, metadata
                FROM chunks
                WHERE compartment = ANY(%s)
                """,
                (labels,),
            ).fetchall()
        hits: list[RetrievalHit] = []
        for row in rows:
            chunk = Chunk(
                id=row[0],
                doc_id=row[1],
                title=row[2],
                text=row[3],
                compartment=row[4],
                metadata=row[5] or {},
            )
            score = lexical_score(query, f"{chunk.title}\n{chunk.text}")
            if score > 0:
                hits.append(RetrievalHit(chunk=chunk, score=score))
        hits.sort(key=lambda hit: hit.score, reverse=True)
        return hits[:k]

    def get(self, chunk_id: str) -> Chunk | None:
        with self._connect() as conn:
            row = conn.execute(
                "SELECT id, doc_id, title, text, compartment, metadata FROM chunks WHERE id = %s",
                (chunk_id,),
            ).fetchone()
        if row is None:
            return None
        return Chunk(id=row[0], doc_id=row[1], title=row[2], text=row[3], compartment=row[4], metadata=row[5] or {})

    def all_chunks(self) -> list[Chunk]:
        with self._connect() as conn:
            rows = conn.execute("SELECT id, doc_id, title, text, compartment, metadata FROM chunks").fetchall()
        return [
            Chunk(id=row[0], doc_id=row[1], title=row[2], text=row[3], compartment=row[4], metadata=row[5] or {})
            for row in rows
        ]


def get_store(dsn: str | None = None) -> InMemoryStore | PostgresStore:
    if dsn:
        return PostgresStore(dsn)
    return InMemoryStore()
