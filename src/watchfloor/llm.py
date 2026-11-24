from __future__ import annotations

from typing import Protocol


class LLMProvider(Protocol):
    name: str

    def complete(self, prompt: str) -> str: ...


class StubProvider:
    """Offline template provider. Never leaves the process. Records every prompt for tests."""

    name = "stub"

    def __init__(self) -> None:
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        context = _extract_context(prompt)
        if not context.strip():
            return "No authorized documents were available for this request."
        return (
            "Authorized brief (offline stub; no external model was called):\n\n"
            f"{context.strip()}\n\n"
            "This answer uses only chunks the requester is allowed to retrieve."
        )


class AnthropicProvider:
    name = "anthropic"

    def __init__(self, model: str | None = None) -> None:
        import os

        import anthropic

        self._model = model or os.environ.get("WATCHFLOOR_ANTHROPIC_MODEL", "claude-sonnet-4-5")
        self._client = anthropic.Anthropic()
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = self._client.messages.create(
            model=self._model,
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        return "".join(block.text for block in response.content if getattr(block, "type", "") == "text")


class VertexProvider:
    name = "vertex"

    def __init__(self, model: str | None = None) -> None:
        import os

        from google import genai

        project = os.environ.get("GOOGLE_CLOUD_PROJECT")
        location = os.environ.get("GOOGLE_CLOUD_LOCATION", "us-central1")
        self._model = model or os.environ.get("WATCHFLOOR_VERTEX_MODEL", "gemini-2.5-flash")
        self._client = genai.Client(vertexai=True, project=project, location=location)
        self.prompts: list[str] = []

    def complete(self, prompt: str) -> str:
        self.prompts.append(prompt)
        response = self._client.models.generate_content(model=self._model, contents=prompt)
        return response.text or ""


def get_provider(name: str | None = None) -> LLMProvider:
    from watchfloor.config import llm_provider_name

    choice = (name or llm_provider_name()).strip().lower()
    if choice in {"stub", "template", "offline"}:
        return StubProvider()
    if choice == "anthropic":
        return AnthropicProvider()
    if choice in {"vertex", "gemini"}:
        return VertexProvider()
    raise ValueError(f"unknown LLM provider '{choice}'")


def _extract_context(prompt: str) -> str:
    marker = "Authorized documents:"
    if marker in prompt:
        return prompt.split(marker, 1)[1].strip()
    return prompt
