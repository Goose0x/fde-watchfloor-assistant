from __future__ import annotations

from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from watchfloor.api import create_app
from watchfloor.approvals import ApprovalService, InProcessBackend, StubNotifier
from watchfloor.audit import AuditLog
from watchfloor.llm import StubProvider
from watchfloor.pii import PiiVault
from watchfloor.rag import SecureRag
from watchfloor.runtime import App
from watchfloor.seed import seed_store
from watchfloor.store import InMemoryStore


@pytest.fixture
def store() -> InMemoryStore:
    memory = InMemoryStore()
    seed_store(memory)
    return memory


@pytest.fixture
def llm() -> StubProvider:
    return StubProvider()


@pytest.fixture
def vault() -> PiiVault:
    return PiiVault()


@pytest.fixture
def audit() -> AuditLog:
    return AuditLog()


@pytest.fixture
def rag(store: InMemoryStore, llm: StubProvider, vault: PiiVault, audit: AuditLog) -> SecureRag:
    return SecureRag(store=store, llm=llm, vault=vault, audit=audit)


@pytest.fixture
def approvals(audit: AuditLog, tmp_path: Path) -> ApprovalService:
    backend = InProcessBackend(tmp_path / "approvals.sqlite")
    return ApprovalService(backend=backend, audit=audit, notifier=StubNotifier())


@pytest.fixture
def app(rag: SecureRag, approvals: ApprovalService, audit: AuditLog, vault: PiiVault, llm: StubProvider, store: InMemoryStore) -> App:
    return App(store=store, rag=rag, approvals=approvals, audit=audit, vault=vault, llm=llm)


@pytest.fixture
def client(app: App) -> TestClient:
    return TestClient(create_app(runtime=app))
