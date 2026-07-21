"""Every significant entity gets a stable, immutable identifier
(CONSTITUTION.md: "Human readable names are not identifiers."). This is the
single place identifiers are generated — domains call `new_id()` rather than
each inventing their own scheme.
"""

from __future__ import annotations

import uuid


def new_id(prefix: str | None = None) -> str:
    """Returns a UUID4-based identifier, optionally namespaced with a prefix
    (e.g. `new_id("proposal")` -> "proposal_3fae...") for readability in logs
    and audit trails. The prefix is cosmetic only — uniqueness comes from the
    UUID, not the prefix.
    """
    raw = uuid.uuid4().hex
    return f"{prefix}_{raw}" if prefix else raw
