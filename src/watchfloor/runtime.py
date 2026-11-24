from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

from watchfloor.approvals import ApprovalService, InProcessBackend, get_backend
from watchfloor.audit import AuditLog
from watchfloor.config import data_dir, database_url
from watchfloor.llm import LLMProvider, get_provider
from watchfloor.pii import PiiVault
from watchfloor.rag import SecureRag
from watchfloor.seed import seed_store
from watchfloor.store import VectorStore, get_store


@dataclass
class App:
    store: VectorStore
    rag: SecureRag
    approvals: ApprovalService
    audit: AuditLog
    vault: PiiVault
    llm: LLMProvider


def build_app(
    *,
    data_path: Path | None = None,
    store: VectorStore | None = None,
    llm: LLMProvider | None = None,
    persist: bool = True,
    seed: bool = True,
) -> App:
    root = data_path or data_dir()
    audit = AuditLog(root / "audit.sqlite" if persist else None)
    vault = PiiVault()
    llm = llm or get_provider()
    if store is None:
        store = get_store(database_url())
    if seed and not store.all_chunks():
        seed_store(store)
    rag = SecureRag(store=store, llm=llm, vault=vault, audit=audit)
    backend = get_backend(path=root / "approvals.sqlite") if persist else InProcessBackend()
    approvals = ApprovalService(backend=backend, audit=audit)
    return App(store=store, rag=rag, approvals=approvals, audit=audit, vault=vault, llm=llm)
