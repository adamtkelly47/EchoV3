"""Permission classification (PROMPT.md Phase 3). A structured type rather
than a bare string, per CONSTITUTION.md's Magic Strings anti-pattern
("Behavior should not depend upon undocumented string literals. Named
constants or strongly typed representations are preferred.").

This is the type only — actual permission *evaluation* (does this user hold
this permission?) is deterministic application/Identity-domain logic added
in a later phase, never a language model decision (CONSTITUTION.md:
Authorization — "Language models shall never determine permissions.").
"""

from __future__ import annotations

from enum import Enum

from pydantic import BaseModel, ConfigDict


class PermissionAction(str, Enum):
    READ = "read"
    WRITE = "write"


class Permission(BaseModel):
    """A single permission requirement: the ability to take `action` on
    `resource` (e.g. resource="portfolio.positions", action=READ)."""

    model_config = ConfigDict(frozen=True)

    resource: str
    action: PermissionAction
