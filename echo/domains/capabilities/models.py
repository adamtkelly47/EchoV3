"""A registered capability pairs the platform-wide contract (core.capabilities
.CapabilityContract — the metadata every capability must declare) with the
concrete typed input/output models and the handler that actually runs it.
The contract alone is metadata; this is what the registry actually holds.
"""

from __future__ import annotations

from collections.abc import Awaitable, Callable
from dataclasses import dataclass

from pydantic import BaseModel

from core.capabilities import CapabilityContract

Handler = Callable[[BaseModel], Awaitable[BaseModel]]


@dataclass(frozen=True)
class RegisteredCapability:
    contract: CapabilityContract
    input_model: type[BaseModel]
    output_model: type[BaseModel]
    handler: Handler
