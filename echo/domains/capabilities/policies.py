"""Policies decide; they never persist data or coordinate workflows
(CONSTITUTION.md: Policy). Identity (permission granting) doesn't exist as
a domain yet (Phase 8+), so the caller's granted permissions are passed in
explicitly by whoever invokes the executor — this policy only decides
whether what's granted satisfies what's required.
"""

from __future__ import annotations

from core.capabilities import CapabilityContract, ReadWriteClassification
from core.security import Permission


def has_required_permissions(required: list[Permission], granted: frozenset[Permission]) -> bool:
    return all(permission in granted for permission in required)


def is_executable_now(contract: CapabilityContract) -> bool:
    """Read capabilities are executable in Phase 5. Write capabilities are
    registrable but not executable until the Approval Engine exists
    (Phase 6) — see domains/capabilities/errors.WriteCapabilityNotExecutableError.
    """
    return contract.read_write_classification == ReadWriteClassification.READ
