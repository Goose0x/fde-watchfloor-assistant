from __future__ import annotations

from pathlib import Path

from watchfloor.config import TESTDATA
from watchfloor.models import Chunk
from watchfloor.store import VectorStore

FRONT_MATTER = "---"


def load_fixture_chunks(testdata: Path | None = None) -> list[Chunk]:
    root = testdata or TESTDATA
    chunks: list[Chunk] = []
    for path in sorted(root.glob("*.md")):
        chunks.append(_parse_document(path))
    if not chunks:
        raise FileNotFoundError(f"no fixture documents found in {root}")
    return chunks


def seed_store(store: VectorStore, testdata: Path | None = None) -> list[Chunk]:
    chunks = load_fixture_chunks(testdata)
    store.upsert(chunks)
    return chunks


def _parse_document(path: Path) -> Chunk:
    text = path.read_text(encoding="utf-8")
    meta: dict[str, str] = {}
    body = text
    if text.startswith(FRONT_MATTER):
        rest = text[len(FRONT_MATTER) :].lstrip("\n")
        header, sep, remainder = rest.partition(f"\n{FRONT_MATTER}")
        if not sep:
            raise ValueError(f"{path} has an opening front matter fence but no closing fence")
        for line in header.splitlines():
            if not line.strip() or ":" not in line:
                continue
            key, value = line.split(":", 1)
            meta[key.strip()] = value.strip()
        body = remainder.lstrip("\n")
    doc_id = meta.get("id") or path.stem
    title = meta.get("title") or doc_id
    compartment = meta.get("compartment")
    if not compartment:
        raise ValueError(f"{path} is missing a compartment in front matter")
    return Chunk(id=doc_id, doc_id=doc_id, title=title, text=body.strip(), compartment=compartment, metadata=meta)
