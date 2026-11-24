from __future__ import annotations

import sqlite3
import threading
import uuid
from datetime import UTC, datetime
from pathlib import Path
from typing import Any, Protocol

from watchfloor.audit import AuditLog
from watchfloor.models import Approval, ApprovalStatus, User


class Notifier(Protocol):
    def notify(self, approval: Approval) -> None: ...


class StubNotifier:
    """Stand-in for a Slack (or other chat) notifier. Records calls; never sends a network request."""

    def __init__(self) -> None:
        self.sent: list[Approval] = []

    def notify(self, approval: Approval) -> None:
        self.sent.append(approval)


class WorkflowBackend(Protocol):
    def start(self, approval: Approval) -> Approval: ...

    def get(self, approval_id: str) -> Approval | None: ...

    def list_pending(self) -> list[Approval]: ...

    def decide(self, approval_id: str, status: ApprovalStatus, actor: str, reason: str | None) -> Approval: ...


class InProcessBackend:
    """Sqlite-backed durable workflow store. A new process that opens the same file still sees pending work."""

    def __init__(self, path: Path | str | None = None) -> None:
        self._path = Path(path) if path else None
        self._lock = threading.Lock()
        self._memory: dict[str, Approval] = {}
        self._conn: sqlite3.Connection | None = None
        if self._path is not None:
            self._path.parent.mkdir(parents=True, exist_ok=True)
            self._conn = sqlite3.connect(self._path, check_same_thread=False)
            self._conn.row_factory = sqlite3.Row
            self._conn.execute(
                """
                CREATE TABLE IF NOT EXISTS approvals (
                    id TEXT PRIMARY KEY,
                    record TEXT NOT NULL
                )
                """
            )
            self._conn.commit()

    def close(self) -> None:
        if self._conn is not None:
            self._conn.close()
            self._conn = None

    def start(self, approval: Approval) -> Approval:
        self._save(approval)
        return approval

    def get(self, approval_id: str) -> Approval | None:
        with self._lock:
            if self._conn is None:
                return self._memory.get(approval_id)
            row = self._conn.execute("SELECT record FROM approvals WHERE id = ?", (approval_id,)).fetchone()
            return Approval.model_validate_json(row["record"]) if row else None

    def list_pending(self) -> list[Approval]:
        return [item for item in self._all() if item.status == ApprovalStatus.PENDING]

    def decide(self, approval_id: str, status: ApprovalStatus, actor: str, reason: str | None) -> Approval:
        approval = self.get(approval_id)
        if approval is None:
            raise KeyError(f"unknown approval '{approval_id}'")
        if approval.status is not ApprovalStatus.PENDING:
            raise ValueError(f"approval '{approval_id}' is already {approval.status}")
        if status not in {ApprovalStatus.APPROVED, ApprovalStatus.DENIED}:
            raise ValueError("decision must be approved or denied")
        updated = approval.model_copy(
            update={
                "status": status,
                "decided_at": datetime.now(UTC),
                "decided_by": actor,
                "reason": reason,
            }
        )
        self._save(updated)
        return updated

    def _all(self) -> list[Approval]:
        with self._lock:
            if self._conn is None:
                return list(self._memory.values())
            rows = self._conn.execute("SELECT record FROM approvals").fetchall()
            return [Approval.model_validate_json(row["record"]) for row in rows]

    def _save(self, approval: Approval) -> None:
        with self._lock:
            if self._conn is None:
                self._memory[approval.id] = approval
                return
            self._conn.execute(
                "INSERT INTO approvals (id, record) VALUES (?, ?) ON CONFLICT (id) DO UPDATE SET record = EXCLUDED.record",
                (approval.id, approval.model_dump_json()),
            )
            self._conn.commit()


class TemporalBackend:
    """Optional Temporal client wrapper. Imported only when explicitly selected."""

    def __init__(self, address: str, namespace: str = "default") -> None:
        self.address = address
        self.namespace = namespace
        raise NotImplementedError(
            "The Temporal backend is a deploy-time option. Use WATCHFLOOR_WORKFLOW_BACKEND=inprocess "
            "for tests and the laptop demo, or wire this client once a Temporal cluster is running."
        )


class ApprovalService:
    def __init__(
        self,
        backend: WorkflowBackend | None = None,
        audit: AuditLog | None = None,
        notifier: Notifier | None = None,
    ) -> None:
        self.backend = backend or InProcessBackend()
        self.audit = audit or AuditLog()
        self.notifier = notifier or StubNotifier()

    def request_share(self, requester: User, summary: str, payload: dict[str, Any] | None = None) -> Approval:
        approval = Approval(
            id=str(uuid.uuid4()),
            action="share_brief",
            requester_id=requester.id,
            summary=summary,
            payload=payload or {},
        )
        stored = self.backend.start(approval)
        self.audit.append(
            "approval_requested",
            requester.id,
            {"approval_id": stored.id, "action": stored.action, "summary": summary},
        )
        self.notifier.notify(stored)
        return stored

    def get(self, approval_id: str) -> Approval | None:
        return self.backend.get(approval_id)

    def pending(self) -> list[Approval]:
        return self.backend.list_pending()

    def decide(self, actor: User, approval_id: str, approve: bool, reason: str | None = None) -> Approval:
        if not actor.can_approve:
            raise PermissionError(f"user '{actor.id}' is not allowed to decide approvals")
        status = ApprovalStatus.APPROVED if approve else ApprovalStatus.DENIED
        updated = self.backend.decide(approval_id, status, actor.id, reason)
        self.audit.append(
            "approval_decided",
            actor.id,
            {"approval_id": updated.id, "status": updated.status, "reason": reason},
        )
        return updated


def get_backend(name: str | None = None, path: Path | str | None = None) -> WorkflowBackend:
    import os

    from watchfloor.config import workflow_backend_name

    choice = (name or workflow_backend_name()).strip().lower()
    if choice in {"inprocess", "local", "sqlite"}:
        return InProcessBackend(path)
    if choice == "temporal":
        address = os.environ.get("TEMPORAL_ADDRESS", "127.0.0.1:7233")
        namespace = os.environ.get("TEMPORAL_NAMESPACE", "default")
        return TemporalBackend(address, namespace)
    raise ValueError(f"unknown workflow backend '{choice}'")
