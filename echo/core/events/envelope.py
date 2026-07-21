"""The generic wrapper every domain event rides inside (CONSTITUTION.md:
Domain Events — "Events represent completed business facts... should remain
immutable... should remain versioned."). Domains define their own payload
shape (e.g. a future `PortfolioSnapshotCreatedPayload`) starting Phase 8+;
this envelope is the one stable contract every one of those payloads is
wrapped in, regardless of which domain published it.

Delivery is synchronous in-process for now (Docs/DOMAIN_EVENTS.md); this
envelope's shape does not assume any particular transport, so an async
transport can be introduced later without changing it.
"""

from __future__ import annotations

from datetime import datetime
from typing import Generic, TypeVar

from pydantic import BaseModel, ConfigDict, Field

from core.identifiers import new_id

PayloadT = TypeVar("PayloadT", bound=BaseModel)


class EventEnvelope(BaseModel, Generic[PayloadT]):
    model_config = ConfigDict(frozen=True)

    event_id: str = Field(default_factory=lambda: new_id("event"))
    event_type: str
    event_version: int = 1
    occurred_at: datetime
    correlation_id: str | None = None
    payload: PayloadT
