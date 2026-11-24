from __future__ import annotations

from watchfloor.llm import StubProvider
from watchfloor.pii import contains_raw_pii, mask_text, token_for, unmask_text
from watchfloor.rag import SecureRag
from watchfloor.rbac import get_user

PLANTED_SSN = "999-00-1111"
PLANTED_CARD = "4111-1111-1111-1111"
PLANTED_EMAIL = "alex.rivera@northbridge.example"


def test_mask_is_deterministic_and_reversible(vault) -> None:
    text = f"Pay with {PLANTED_CARD} and file {PLANTED_SSN} to {PLANTED_EMAIL}."
    first = mask_text(text, vault)
    second = mask_text(text, vault)
    assert first.text == second.text
    assert PLANTED_SSN not in first.text
    assert PLANTED_CARD not in first.text
    assert PLANTED_EMAIL not in first.text
    assert token_for("ssn", PLANTED_SSN) in first.text
    assert unmask_text(first.text, vault) == text


def test_pii_never_reaches_the_model_stub(rag: SecureRag, llm: StubProvider) -> None:
    finance = get_user("finance")
    result = rag.ask(finance, "What is the Harborline Carriers payment memo and contractor stipend?")

    assert llm.prompts, "the stub should have received a prompt"
    for prompt in llm.prompts:
        assert PLANTED_SSN not in prompt
        assert "999-00-2222" not in prompt
        assert PLANTED_CARD not in prompt
        assert PLANTED_EMAIL not in prompt
        assert "sam.patel@northbridge.example" not in prompt
        assert not contains_raw_pii(prompt)

    assert not contains_raw_pii(result.model_prompt)
    assert not contains_raw_pii(result.model_raw)
    # Finance is allowed to see restored identifiers in the caller-facing answer only.
    assert PLANTED_SSN in result.answer
    assert PLANTED_CARD in result.answer
    assert result.pii_revealed is True


def test_ops_lead_answer_does_not_reveal_finance_pii(rag: SecureRag, llm: StubProvider) -> None:
    ops = get_user("ops-lead")
    result = rag.ask(ops, "What is the Harborline Carriers payment memo and the planted tax identifier?")

    assert "finance-vendor-memo" not in result.citations
    assert "finance-payroll-note" not in result.citations
    assert PLANTED_SSN not in result.answer
    assert PLANTED_CARD not in result.answer
    for prompt in llm.prompts:
        assert not contains_raw_pii(prompt)


def test_ops_lead_does_not_unmask_emails_from_ops_docs(rag: SecureRag) -> None:
    ops = get_user("ops-lead")
    result = rag.ask(ops, "Who is the dock contact in the weekly site brief?")
    assert "sam.patel@northbridge.example" not in result.model_prompt
    assert "sam.patel@northbridge.example" not in result.answer
    assert result.pii_revealed is False
