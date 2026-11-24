from __future__ import annotations

from datetime import UTC, datetime
from enum import StrEnum
from typing import Any

from pydantic import BaseModel, Field


class ApprovalStatus(StrEnum):
    PENDING = "pending"
    APPROVED = "approved"
    DENIED = "denied"


class User(BaseModel):
    id: str
    name: str
    role: str
    compartments: frozenset[str]
    can_reveal_pii: bool = False
    can_approve: bool = False

    model_config = {"frozen": True}


class Chunk(BaseModel):
    id: str
    doc_id: str
    title: str
    text: str
    compartment: str
    metadata: dict[str, Any] = Field(default_factory=dict)


class MaskedSpan(BaseModel):
    token: str
    kind: str
    original: str


class MaskResult(BaseModel):
    text: str
    spans: list[MaskedSpan] = Field(default_factory=list)


class RetrievalHit(BaseModel):
    chunk: Chunk
    score: float


class AskResult(BaseModel):
    user_id: str
    query: str
    answer: str
    citations: list[str]
    masked_query: str
    model_prompt: str
    model_raw: str
    pii_revealed: bool


class Approval(BaseModel):
    id: str
    action: str
    requester_id: str
    summary: str
    payload: dict[str, Any] = Field(default_factory=dict)
    status: ApprovalStatus = ApprovalStatus.PENDING
    created_at: datetime = Field(default_factory=lambda: datetime.now(UTC))
    decided_at: datetime | None = None
    decided_by: str | None = None
    reason: str | None = None


class AuditEntry(BaseModel):
    seq: int
    timestamp: datetime
    action: str
    actor: str
    details: dict[str, Any] = Field(default_factory=dict)
    prev_hash: str
    entry_hash: str
