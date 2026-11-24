from __future__ import annotations

from functools import lru_cache
from typing import Any

from fastapi import FastAPI, Header, HTTPException
from pydantic import BaseModel, Field

from watchfloor.rbac import get_user
from watchfloor.runtime import App, build_app


class AskRequest(BaseModel):
    query: str = Field(min_length=1)


class ShareRequest(BaseModel):
    summary: str = Field(min_length=1)
    payload: dict[str, Any] = Field(default_factory=dict)


class DecideRequest(BaseModel):
    reason: str | None = None


def create_app(runtime: App | None = None) -> FastAPI:
    api = FastAPI(title="Watchfloor Assistant", version="0.1.0")

    def _runtime() -> App:
        return runtime or _default_runtime()

    def _actor(user_id: str | None):
        if not user_id:
            raise HTTPException(status_code=401, detail="X-User-Id header is required")
        try:
            return get_user(user_id)
        except KeyError as exc:
            raise HTTPException(status_code=401, detail=str(exc)) from exc

    @api.get("/health")
    def health() -> dict[str, str]:
        return {"status": "ok"}

    @api.post("/ask")
    def ask(body: AskRequest, x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        result = _runtime().rag.ask(_actor(x_user_id), body.query)
        return result.model_dump()

    @api.post("/actions/share")
    def share(body: ShareRequest, x_user_id: str | None = Header(default=None)) -> dict[str, Any]:
        approval = _runtime().approvals.request_share(_actor(x_user_id), body.summary, body.payload)
        return approval.model_dump(mode="json")

    @api.get("/approvals")
    def list_approvals() -> list[dict[str, Any]]:
        return [item.model_dump(mode="json") for item in _runtime().approvals.pending()]

    @api.get("/approvals/{approval_id}")
    def get_approval(approval_id: str) -> dict[str, Any]:
        approval = _runtime().approvals.get(approval_id)
        if approval is None:
            raise HTTPException(status_code=404, detail="unknown approval")
        return approval.model_dump(mode="json")

    @api.post("/approvals/{approval_id}/approve")
    def approve(approval_id: str, body: DecideRequest | None = None, x_user_id: str | None = Header(default=None)):
        return _decide(approval_id, True, body, x_user_id, _runtime())

    @api.post("/approvals/{approval_id}/deny")
    def deny(approval_id: str, body: DecideRequest | None = None, x_user_id: str | None = Header(default=None)):
        return _decide(approval_id, False, body, x_user_id, _runtime())

    @api.get("/audit")
    def audit(limit: int = 50) -> list[dict[str, Any]]:
        entries = _runtime().audit.entries()[-limit:]
        return [entry.model_dump(mode="json") for entry in entries]

    def _decide(approval_id: str, approve_flag: bool, body: DecideRequest | None, user_id: str | None, app: App):
        actor = _actor(user_id)
        try:
            updated = app.approvals.decide(actor, approval_id, approve_flag, body.reason if body else None)
        except KeyError as exc:
            raise HTTPException(status_code=404, detail=str(exc)) from exc
        except PermissionError as exc:
            raise HTTPException(status_code=403, detail=str(exc)) from exc
        except ValueError as exc:
            raise HTTPException(status_code=409, detail=str(exc)) from exc
        return updated.model_dump(mode="json")

    return api


@lru_cache(maxsize=1)
def _default_runtime() -> App:
    return build_app()


app = create_app()
