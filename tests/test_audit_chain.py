from __future__ import annotations

from pathlib import Path

from watchfloor.audit import GENESIS_HASH, AuditLog
from watchfloor.rag import SecureRag
from watchfloor.rbac import get_user


def test_hash_chain_verifies_and_survives_reload(tmp_path: Path) -> None:
    path = tmp_path / "audit.sqlite"
    log = AuditLog(path)
    log.append("mask_chunk", "finance", {"doc_id": "finance-vendor-memo", "tokens": ["[PII:SSN:abcd1234]"]})
    log.append("infer", "finance", {"provider": "stub"})
    log.verify()
    first_hash = log.entries()[0].entry_hash
    assert log.entries()[0].prev_hash == GENESIS_HASH
    log.close()

    reloaded = AuditLog(path)
    reloaded.verify()
    assert reloaded.entries()[0].entry_hash == first_hash
    assert len(reloaded.entries()) == 2
    reloaded.close()


def test_tampered_entry_fails_verification(tmp_path: Path) -> None:
    path = tmp_path / "audit.sqlite"
    log = AuditLog(path)
    log.append("infer", "finance", {"provider": "stub"})
    log._conn.execute("UPDATE audit_entries SET action = 'tampered' WHERE seq = 1")
    log._conn.commit()
    try:
        log.verify()
        raise AssertionError("expected hash mismatch")
    except ValueError as exc:
        assert "hash mismatch" in str(exc)
    finally:
        log.close()


def test_audit_log_does_not_store_raw_pii(rag: SecureRag) -> None:
    finance = get_user("finance")
    rag.ask(finance, "Summarize the Harborline Carriers payment memo")
    blob = " ".join(str(entry.details) for entry in rag.audit.entries())
    assert "999-00-1111" not in blob
    assert "4111-1111-1111-1111" not in blob
    assert "original" not in blob.lower() or "[redacted]" in blob
