"""
LLM provider abstraction for the RAG Investigation Copilot.

The generation step of RAG (turning retrieved evidence into a natural-
language answer) genuinely requires calling an external LLM. This
sandbox has network access to api.anthropic.com but no credentialed
API key configured for the application to use — the same category of
constraint as Kaggle (Phase 4) and Neo4j (Phase 8): a real external
dependency this environment cannot provide, not something to fake
around.

`AnthropicProvider` is a complete, real implementation — if a
deployment sets ANTHROPIC_API_KEY, this actually calls the API and
returns a real model response. `NoProviderAvailable` is the honest
default when no key is configured, and CopilotService (copilot_service.py)
falls back to a deterministic evidence digest rather than fabricating
what an LLM would have said.
"""
import logging
from abc import ABC, abstractmethod

from app.core.config import settings

logger = logging.getLogger("quantumfinguard.copilot")


class LlmProviderUnavailableError(Exception):
    pass


class LlmProviderCallError(Exception):
    """Raised when a provider IS configured but the call itself failed
    (network error, auth error, rate limit) — distinct from
    'unavailable' so callers can report the real failure honestly
    rather than silently falling back as if no provider existed."""


class LlmProvider(ABC):
    @abstractmethod
    def generate(self, system_prompt: str, user_prompt: str) -> str: ...

    @abstractmethod
    def is_configured(self) -> bool: ...

    @property
    @abstractmethod
    def provider_name(self) -> str: ...


class NoProviderAvailable(LlmProvider):
    def is_configured(self) -> bool:
        return False

    @property
    def provider_name(self) -> str:
        return "none"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        raise LlmProviderUnavailableError(
            "No LLM provider is configured (ANTHROPIC_API_KEY is not set). "
            "The copilot falls back to a deterministic evidence digest — "
            "see CopilotService.ask() — rather than fabricating a "
            "generated response."
        )


class AnthropicProvider(LlmProvider):
    """Real implementation. Untested in this environment for lack of a
    credentialed key (see module docstring) — the code path is genuine,
    not a stub, and will actually call the API if ANTHROPIC_API_KEY is
    set in a deployment that has one."""

    MODEL = "claude-sonnet-4-5"

    def __init__(self, api_key: str):
        import anthropic
        self._client = anthropic.Anthropic(api_key=api_key)

    def is_configured(self) -> bool:
        return True

    @property
    def provider_name(self) -> str:
        return f"anthropic:{self.MODEL}"

    def generate(self, system_prompt: str, user_prompt: str) -> str:
        import anthropic

        try:
            response = self._client.messages.create(
                model=self.MODEL,
                max_tokens=1024,
                system=system_prompt,
                messages=[{"role": "user", "content": user_prompt}],
            )
            return "".join(block.text for block in response.content if hasattr(block, "text"))
        except anthropic.APIError as exc:
            logger.error("Anthropic API call failed: %s", exc)
            raise LlmProviderCallError(f"LLM provider call failed: {exc}") from exc


def get_llm_provider() -> LlmProvider:
    if settings.ANTHROPIC_API_KEY:
        return AnthropicProvider(settings.ANTHROPIC_API_KEY)
    return NoProviderAvailable()
