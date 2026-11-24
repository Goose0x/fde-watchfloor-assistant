from __future__ import annotations

from pathlib import Path

import pytest

from watchfloor.approvals import ApprovalService, InProcessBackend, StubNotifier
from watchfloor.audit import AuditLog
from watchfloor.models import ApprovalStatus
from watchfloor.rbac import get_user


def test_share_pauses_until_approval() -> None:
    service = ApprovalService(backend=InProcessBackend(), audit=AuditLog(), notifier=StubNotifier())
    pending = service.request_share(get_user("ops-lead"), "Share the weekly site brief with Harborline Carriers")
    assert pending.status is ApprovalStatus.PENDING
    assert service.get(pending.id) is not None
    assert len(service.pending()) == 1

    with pytest.raises(PermissionError):
        service.decide(get_user("ops-lead"), pending.id, True, "not allowed")

    denied = service.decide(get_user("approver"), pending.id, False, "Need a redacted packet first")
    assert denied.status is ApprovalStatus.DENIED
    assert denied.decided_by == "approver"
    assert service.pending() == []


def test_pending_approval_survives_process_restart(tmp_path: Path) -> None:
    path = tmp_path / "approvals.sqlite"
    first = ApprovalService(backend=InProcessBackend(path), audit=AuditLog(), notifier=StubNotifier())
    started = first.request_share(get_user("ops-lead"), "Share the yard log with the overflow hostler desk")
    approval_id = started.id
    first.backend.close()

    # A new service opening the same file is the stand-in for a crashed worker coming back.
    second = ApprovalService(backend=InProcessBackend(path), audit=AuditLog(), notifier=StubNotifier())
    reloaded = second.get(approval_id)
    assert reloaded is not None
    assert reloaded.status is ApprovalStatus.PENDING
    assert reloaded.summary == started.summary

    approved = second.decide(get_user("approver"), approval_id, True, "Approved for Harborline")
    assert approved.status is ApprovalStatus.APPROVED
    second.backend.close()

    third = ApprovalService(backend=InProcessBackend(path), audit=AuditLog())
    assert third.get(approval_id).status is ApprovalStatus.APPROVED
    third.backend.close()
