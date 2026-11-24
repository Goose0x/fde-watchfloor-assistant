from __future__ import annotations

from watchfloor.audit import AuditLog
from watchfloor.llm import LLMProvider, StubProvider
from watchfloor.models import AskResult, User
from watchfloor.pii import PiiVault, contains_raw_pii, mask_text, unmask_text
from watchfloor.store import VectorStore

SYSTEM_INSTRUCTIONS = (
    "Answer only from the authorized documents below. "
    "If the documents are insufficient, say so. "
    "Do not invent identifiers. Leave any [PII:...] tokens intact."
)


class SecureRag:
    def __init__(
        self,
        store: VectorStore,
        llm: LLMProvider | None = None,
        vault: PiiVault | None = None,
        audit: AuditLog | None = None,
        k: int = 5,
    ) -> None:
        self.store = store
        self.llm = llm or StubProvider()
        self.vault = vault or PiiVault()
        self.audit = audit or AuditLog()
        self.k = k

    def ask(self, user: User, query: str) -> AskResult:
        masked_query = mask_text(query, self.vault)
        self.audit.append(
            "mask_query",
            user.id,
            {"tokens": [span.token for span in masked_query.spans], "span_count": len(masked_query.spans)},
        )

        hits = self.store.search(masked_query.text, compartments=user.compartments, k=self.k)
        # Also search the raw query in case masking changed nothing material. The store
        # still pre-filters by the caller's compartments.
        if not hits:
            hits = self.store.search(query, compartments=user.compartments, k=self.k)

        authorized_ids = [hit.chunk.doc_id for hit in hits]
        masked_chunks: list[str] = []
        for hit in hits:
            masked_chunk = mask_text(f"{hit.chunk.title}\n{hit.chunk.text}", self.vault)
            if contains_raw_pii(masked_chunk.text):
                raise RuntimeError("PII mask failed; refusing to send context to the model")
            masked_chunks.append(f"[{hit.chunk.doc_id} / {hit.chunk.compartment}]\n{masked_chunk.text}")
            self.audit.append(
                "mask_chunk",
                user.id,
                {"doc_id": hit.chunk.doc_id, "tokens": [span.token for span in masked_chunk.spans]},
            )

        prompt = _build_prompt(masked_query.text, masked_chunks)
        if contains_raw_pii(prompt):
            raise RuntimeError("PII mask failed; refusing to send the prompt to the model")

        self.audit.append("infer", user.id, {"provider": getattr(self.llm, "name", "unknown"), "citations": authorized_ids})
        raw = self.llm.complete(prompt)
        if contains_raw_pii(raw):
            # A well-behaved stub or model should only echo tokens. If raw PII appears, drop it.
            raw = mask_text(raw, self.vault).text

        if user.can_reveal_pii:
            answer = unmask_text(raw, self.vault)
            pii_revealed = answer != raw
            self.audit.append("unmask_response", user.id, {"revealed": pii_revealed, "citations": authorized_ids})
        else:
            answer = raw
            pii_revealed = False
            self.audit.append("skip_unmask", user.id, {"citations": authorized_ids})

        return AskResult(
            user_id=user.id,
            query=query,
            answer=answer,
            citations=authorized_ids,
            masked_query=masked_query.text,
            model_prompt=prompt,
            model_raw=raw,
            pii_revealed=pii_revealed,
        )


def _build_prompt(masked_query: str, masked_chunks: list[str]) -> str:
    if masked_chunks:
        documents = "\n\n".join(masked_chunks)
    else:
        documents = "(none)"
    return f"{SYSTEM_INSTRUCTIONS}\n\nAuthorized documents:\n{documents}\n\nRequest:\n{masked_query}\n"
