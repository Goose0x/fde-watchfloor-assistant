from __future__ import annotations

import json
from pathlib import Path

import pytest

from watchfloor.cli import main
from watchfloor.rbac import get_user


@pytest.fixture(autouse=True)
def isolated_data(tmp_path: Path, monkeypatch: pytest.MonkeyPatch) -> Path:
    monkeypatch.setenv("WATCHFLOOR_DATA_DIR", str(tmp_path))
    monkeypatch.setenv("WATCHFLOOR_LLM_PROVIDER", "stub")
    monkeypatch.delenv("WATCHFLOOR_DATABASE_URL", raising=False)
    return tmp_path


def test_cli_ask_hides_finance_docs_from_ops_lead(capsys: pytest.CaptureFixture[str]) -> None:
    code = main(["ask", "--user", "ops-lead", "--query", "Harborline Carriers payment memo", "--json"])
    assert code == 0
    payload = json.loads(capsys.readouterr().out)
    assert "finance-vendor-memo" not in payload["citations"]
    assert "999-00-1111" not in payload["answer"]
    assert "4111-1111-1111-1111" not in payload["model_prompt"]


def test_cli_share_then_approve_roundtrip(capsys: pytest.CaptureFixture[str]) -> None:
    assert main(["share", "--user", "ops-lead", "--summary", "Share the weekly site brief with Harborline"]) == 0
    started = json.loads(capsys.readouterr().out)
    approval_id = started["id"]
    assert started["status"] == "pending"

    assert main(["pending"]) == 0
    assert approval_id in capsys.readouterr().out

    assert main(["approve", "--user", "approver", "--id", approval_id, "--reason", "ok"]) == 0
    decided = json.loads(capsys.readouterr().out)
    assert decided["status"] == "approved"
    assert get_user("approver").can_approve


def test_cli_unknown_user_fails() -> None:
    assert main(["ask", "--user", "not-a-user", "--query", "hello"]) == 1
