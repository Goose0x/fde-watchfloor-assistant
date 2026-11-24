from __future__ import annotations

from watchfloor.rbac import get_user
from watchfloor.store import InMemoryStore


def test_low_clearance_user_cannot_retrieve_high_compartment_chunks(store: InMemoryStore) -> None:
    ops = get_user("ops-lead")
    hits = store.search("Harborline Carriers payment memo", compartments=ops.compartments, k=10)
    doc_ids = {hit.chunk.doc_id for hit in hits}
    compartments = {hit.chunk.compartment for hit in hits}

    assert "finance-vendor-memo" not in doc_ids
    assert "finance-payroll-note" not in doc_ids
    assert "finance" not in compartments
    assert compartments <= ops.compartments


def test_exact_finance_title_is_still_hidden_from_ops(store: InMemoryStore) -> None:
    finance_chunk = store.get("finance-vendor-memo")
    assert finance_chunk is not None
    ops = get_user("ops-lead")
    # Without a compartment pre-filter the finance memo is the top hit for its own title.
    unfiltered = store.search(
        finance_chunk.title,
        compartments=frozenset({"ops", "finance", "shared"}),
        k=10,
    )
    assert unfiltered[0].chunk.doc_id == "finance-vendor-memo"
    hits = store.search(finance_chunk.title, compartments=ops.compartments, k=10)
    assert all(hit.chunk.doc_id != "finance-vendor-memo" for hit in hits)


def test_finance_user_retrieves_finance_chunks_not_ops_briefs(store: InMemoryStore) -> None:
    finance = get_user("finance")
    hits = store.search("Harborline Carriers payment memo contractor stipend", compartments=finance.compartments, k=10)
    doc_ids = {hit.chunk.doc_id for hit in hits}
    compartments = {hit.chunk.compartment for hit in hits}

    assert "finance-vendor-memo" in doc_ids
    assert "ops-site-brief" not in doc_ids
    assert "ops-yard-log" not in doc_ids
    assert compartments <= finance.compartments


def test_shared_hours_are_visible_to_every_fixture_user(store: InMemoryStore) -> None:
    for user_id in ("ops-lead", "finance", "approver"):
        user = get_user(user_id)
        hits = store.search("visitor desk cafeteria hours", compartments=user.compartments, k=10)
        assert any(hit.chunk.doc_id == "shared-hours" for hit in hits), user_id


def test_approver_cannot_read_ops_or_finance_compartments(store: InMemoryStore) -> None:
    approver = get_user("approver")
    hits = store.search("Harborline payment yard log stipend", compartments=approver.compartments, k=10)
    assert all(hit.chunk.compartment == "shared" for hit in hits)
