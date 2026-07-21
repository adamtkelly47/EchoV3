"""The generic capability contract shape (PROMPT.md Section 10;
Docs/CAPABILITY_REGISTRY.md). Lives in core/, not domains/capabilities/,
because it is the shape every domain's capability must conform to —
platform-wide, not owned by any one domain. The Capabilities domain (from
Phase 5 onward) owns the *registry*: cataloging, discovering, and versioning
concrete instances of this contract. It does not own the contract's shape,
which is why this module exists here rather than there.

A capability without every one of these fields is not registrable
(CONSTITUTION.md: "Capabilities without complete contracts shall not be
registered.").
"""

from __future__ import annotations

from enum import Enum
from typing import Any

from pydantic import BaseModel, ConfigDict

from core.jobs.envelope import RetryPolicy
from core.security.permissions import Permission


class ReadWriteClassification(str, Enum):
    """Every capability belongs to exactly one category (CONSTITUTION.md:
    Read and Write Classification — "Mixed capabilities are prohibited.")."""

    READ = "read"
    WRITE = "write"


class ExecutionEnvironment(str, Enum):
    REQUEST = "request"
    JOB = "job"


class CapabilityContract(BaseModel):
    model_config = ConfigDict(frozen=True)

    capability_id: str
    version: int
    display_name: str
    description: str
    owner: str
    """The owning domain, matching Docs/DOMAIN_OWNERSHIP.md's catalog."""

    input_schema: dict[str, Any]
    output_schema: dict[str, Any]
    permission_requirements: list[Permission]
    execution_environment: ExecutionEnvironment
    read_write_classification: ReadWriteClassification
    approval_requirement: str | None = None
    """None for read capabilities. For write capabilities, identifies the
    Approval Model proposal type this capability's writes must go through."""

    timeout_seconds: int
    retry_policy: RetryPolicy = RetryPolicy()
    idempotency_behavior: str
    provenance_requirements: str
    supported_interfaces: list[str]
    expected_errors: list[str]
    """Error `code` values (core.errors) this capability may raise."""
