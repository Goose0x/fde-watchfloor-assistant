from __future__ import annotations

import re

import pytest

from watchfloor.llm import get_provider
from watchfloor.seed import load_fixture_chunks
from watchfloor.store import InMemoryStore, get_store


def test_fixtures_are_unclassified_and_labeled() -> None:
    chunks = load_fixture_chunks()
    ids = {chunk.doc_id for chunk in chunks}
    assert ids == {
        "ops-site-brief",
        "ops-yard-log",
        "finance-vendor-memo",
        "finance-payroll-note",
        "shared-hours",
    }
    assert {chunk.compartment for chunk in chunks} == {"ops", "finance", "shared"}
    blob = "\n".join(chunk.text for chunk in chunks).lower()
    for banned in ("classified", "secret", "cui", "indo-pacific", "indopacom"):
        assert re.search(rf"\b{re.escape(banned)}\b", blob) is None


def test_default_store_and_provider_are_offline() -> None:
    store = get_store(None)
    assert isinstance(store, InMemoryStore)
    provider = get_provider("stub")
    assert provider.name == "stub"
    assert get_provider("template").name == "stub"


def test_unknown_provider_rejected() -> None:
    with pytest.raises(ValueError, match="unknown LLM provider"):
        get_provider("not-a-provider")
