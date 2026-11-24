from __future__ import annotations

import re
import uuid
from collections.abc import Iterable

from watchfloor.models import MaskedSpan, MaskResult

# Deterministic namespace so the same original value always maps to the same token.
_TOKEN_NAMESPACE = uuid.UUID("6ba7b810-9dad-11d1-80b2-00c04fd430c8")

_PATTERNS: tuple[tuple[str, re.Pattern[str]], ...] = (
    ("ssn", re.compile(r"\b\d{3}-\d{2}-\d{4}\b")),
    ("card", re.compile(r"\b(?:\d{4}[ -]?){3}\d{4}\b")),
    ("email", re.compile(r"\b[A-Z0-9._%+-]+@[A-Z0-9.-]+\.[A-Z]{2,}\b", re.IGNORECASE)),
)

TOKEN_RE = re.compile(r"\[PII:([A-Z]+):([0-9a-f]{8})\]")


def token_for(kind: str, original: str) -> str:
    digest = uuid.uuid5(_TOKEN_NAMESPACE, f"{kind}:{original}").hex[:8]
    return f"[PII:{kind.upper()}:{digest}]"


class PiiVault:
    """In-memory vault of masked spans. Tokens are deterministic; originals never leave the vault toward the model."""

    def __init__(self, initial: Iterable[MaskedSpan] | None = None) -> None:
        self._by_token: dict[str, MaskedSpan] = {}
        if initial:
            for span in initial:
                self._by_token[span.token] = span

    def remember(self, span: MaskedSpan) -> None:
        existing = self._by_token.get(span.token)
        if existing and existing.original != span.original:
            raise ValueError(f"token collision for {span.token}")
        self._by_token[span.token] = span

    def get(self, token: str) -> MaskedSpan | None:
        return self._by_token.get(token)

    def __len__(self) -> int:
        return len(self._by_token)

    def items(self) -> list[MaskedSpan]:
        return list(self._by_token.values())


def mask_text(text: str, vault: PiiVault) -> MaskResult:
    """Replace SSN-like, card-like, and email-like spans with deterministic tokens."""
    spans: list[MaskedSpan] = []
    # Walk patterns in definition order. Later patterns run on already-masked text so
    # a card pattern cannot eat a token, and overlaps are applied left-to-right per pattern.
    masked = text
    for kind, pattern in _PATTERNS:
        pieces: list[str] = []
        last = 0
        for match in pattern.finditer(masked):
            original = match.group(0)
            if TOKEN_RE.fullmatch(original):
                pieces.append(masked[last : match.end()])
                last = match.end()
                continue
            token = token_for(kind, original)
            span = MaskedSpan(token=token, kind=kind, original=original)
            vault.remember(span)
            spans.append(span)
            pieces.append(masked[last : match.start()])
            pieces.append(token)
            last = match.end()
        pieces.append(masked[last:])
        masked = "".join(pieces)
    return MaskResult(text=masked, spans=spans)


def unmask_text(text: str, vault: PiiVault) -> str:
    def _replace(match: re.Match[str]) -> str:
        token = match.group(0)
        span = vault.get(token)
        return span.original if span else token

    return TOKEN_RE.sub(_replace, text)


def contains_raw_pii(text: str) -> bool:
    """True if the text still has a raw SSN-like, card-like, or email-like span."""
    # Ignore already-masked tokens by stripping them first.
    stripped = TOKEN_RE.sub("", text)
    return any(pattern.search(stripped) for _, pattern in _PATTERNS)
