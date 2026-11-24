from __future__ import annotations

import os
from pathlib import Path

from dotenv import load_dotenv

load_dotenv()

ROOT = Path(__file__).resolve().parents[2]
TESTDATA = ROOT / "testdata"


def data_dir() -> Path:
    raw = os.environ.get("WATCHFLOOR_DATA_DIR")
    path = Path(raw) if raw else ROOT / "data"
    path.mkdir(parents=True, exist_ok=True)
    return path


def llm_provider_name() -> str:
    return os.environ.get("WATCHFLOOR_LLM_PROVIDER", "stub").strip().lower()


def database_url() -> str | None:
    value = os.environ.get("WATCHFLOOR_DATABASE_URL", "").strip()
    return value or None


def workflow_backend_name() -> str:
    return os.environ.get("WATCHFLOOR_WORKFLOW_BACKEND", "inprocess").strip().lower()
