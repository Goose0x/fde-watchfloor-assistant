from __future__ import annotations

import hashlib
import json
import sqlite3
import threading
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from watchfloor.models import AuditEntry

GENESIS_HASH = "0" * 64


def canonical_payload(action: str, actor: str, details: dict[str, Any], timestamp: datetime) -> str:
    body = {
        "action": action,
        "actor": actor,
        "details": details,
        "timestamp": timestamp.isoformat(),
    }
    return json.dumps(body, sort_keys=True, separators=(",", ":"), default=str)


def chain_hash(prev_hash: str, payload: str) -> str:
    return hashlib.sha256(f"{prev_hash}|{payload}".encode()).hexdigest()


class AuditLog:
    """Append-only, hash-chained audit log. Entries are stored in SQLite or kept in memory."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else None
        self._lock = threading.Lock()
        self._memory: list[AuditEntry] = []
        self._conn: sqlite3.Connection | None = None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS audit_entries (
                    seq INTEGER PRIMARY KEY,
                    timestamp TEXT NOT NULL,
                    action TEXT NOT NULL,
                    actor TEXT NOT NULL,
                    details TEXT NOT NULL,
                    prev_hash TEXT NOT NULL,
                    entry_hash TEXT NOT NULL UNIQUE
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def last_hash(self) -> str:
        entries = self.entries()
        return entries[-1].entry_hash if entries else GENESIS_HASH

    def append(self, action: str, actor: str, details: dict[str, Any] | None = None) -> AuditEntry:
        safe_details = _redact(details or {})
        timestamp = datetime.now(UTC)
        prev = self.last_hash()
        payload = canonical_payload(action, actor, safe_details, timestamp)
        entry_hash = chain_hash(prev, payload)
        seq = (self.entries()[-1].seq + 1) if self.entries() else 1
        entry = AuditEntry(
            seq=seq,
            timestamp=timestamp,
            action=action,
            actor=actor,
            details=safe_details,
            prev_hash=prev,
            entry_hash=entry_hash,
        )
        self._persist(entry)
        return entry

    def entries(self) -> list[AuditEntry]:
        with self._lock:
            if self._conn is None:
                return list(self._memory)
            rows = self._conn.execute("SELECT * FROM audit_entries ORDER BY seq ASC").fetchall()
            return [_row_to_entry(row) for row in rows]

    def verify(self) -> None:
        prev = GENESIS_HASH
        for entry in self.entries():
            if entry.prev_hash != prev:
                raise ValueError(f"broken prev_hash at seq {entry.seq}")
            payload = canonical_payload(entry.action, entry.actor, entry.details, entry.timestamp)
            expected = chain_hash(entry.prev_hash, payload)
            if entry.entry_hash != expected:
                raise ValueError(f"hash mismatch at seq {entry.seq}")
            prev = entry.entry_hash

    def _persist(self, entry: AuditEntry) -> None:
        with self._lock:
            self._persist_locked(entry)

    def _persist_locked(self, entry: AuditEntry) -> None:
        if self._conn is None:
            self._memory.append(entry)
            return
        self._conn.execute(
            """
            INSERT INTO audit_entries (seq, timestamp, action, actor, details, prev_hash, entry_hash)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (
                entry.seq,
                entry.timestamp.isoformat(),
                entry.action,
                entry.actor,
                json.dumps(entry.details, sort_keys=True),
                entry.prev_hash,
                entry.entry_hash,
            ),
        )
        self._conn.commit()


def _row_to_entry(row: sqlite3.Row) -> AuditEntry:
    return AuditEntry(
        seq=row["seq"],
        timestamp=datetime.fromisoformat(row["timestamp"]),
        action=row["action"],
        actor=row["actor"],
        details=json.loads(row["details"]),
        prev_hash=row["prev_hash"],
        entry_hash=row["entry_hash"],
    )


_SENSITIVE_KEYS = frozenset({"original", "ssn", "card", "email", "raw", "secret", "password"})


def _redact(details: dict[str, Any]) -> dict[str, Any]:
    """Drop raw sensitive fields so the audit log records tokens and actions, not planted identifiers."""
    cleaned: dict[str, Any] = {}
    for key, value in details.items():
        if key.lower() in _SENSITIVE_KEYS:
            cleaned[key] = "[redacted]"
        elif isinstance(value, dict):
            cleaned[key] = _redact(value)
        else:
            cleaned[key] = value
    return cleaned
