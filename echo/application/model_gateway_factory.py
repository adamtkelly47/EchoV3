"""Constructs the ModelGateway from settings, and defines the port
(`ModelGatewayPort`) apps/api/dependencies.py types against instead of the
concrete `providers.models.gateway.ModelGateway` — apps/ must not import
providers/ directly (scripts/check_architecture.py's
apps-must-not-import-providers rule, Phase 2), including for a bare return
type annotation, so the composition root needs an application-layer port to
depend on. Construction of concrete provider adapters happens at the
Application layer, which sits between API and Providers in the dependency
direction (CONSTITUTION.md: "No layer may bypass intermediate ownership.").
"""

from __future__ import annotations

from collections.abc import AsyncIterator
from typing import Protocol, TypeVar

from pydantic import BaseModel

from core.config import Settings
from core.time import SystemClock
from providers.models.claude.adapter import ClaudeAdapter
from providers.models.contracts import ModelRequest, ModelResponse, Provider
from providers.models.gateway import ModelGateway
from providers.models.ollama.adapter import OllamaAdapter

OutputT = TypeVar("OutputT", bound=BaseModel)


class ModelGatewayPort(Protocol):
    async def generate(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> ModelResponse: ...

    def generate_stream(
        self, request: ModelRequest, *, provider: Provider | None = None
    ) -> AsyncIterator[str]: ...

    async def generate_structured(
        self,
        request: ModelRequest,
        output_model: type[OutputT],
        *,
        provider: Provider | None = None,
    ) -> OutputT: ...


def build_model_gateway(settings: Settings) -> ModelGatewayPort:
    clock = SystemClock()
    claude = ClaudeAdapter(
        api_key=settings.anthropic_api_key or "",
        model_name=settings.claude_model_name,
        clock=clock,
    )
    ollama = OllamaAdapter(settings.ollama_base_url, settings.ollama_model_name, clock)
    return ModelGateway(
        claude=claude, ollama=ollama, default_provider=Provider(settings.default_model_provider)
    )
