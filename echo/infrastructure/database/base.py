"""Declarative base for every ORM table. Domain modules (Phase 5+) define
their own tables against this same base — one migration history, one
metadata object, per CONSTITUTION.md's Single Source of Truth principle.
"""

from sqlalchemy.orm import DeclarativeBase


class Base(DeclarativeBase):
    pass
