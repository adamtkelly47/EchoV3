#!/usr/bin/env python
"""Enforces the dependency rules in Docs/ARCHITECTURE.md.

Most of these rules are currently vacuous — `domains/` and `providers/`
don't exist yet (Phase 1/2 only has `apps/`). That is expected: this script
is CI infrastructure set up ahead of the code it will govern, so the rules
are already enforced the moment Phase 3+ adds real domain/provider modules,
rather than being bolted on retroactively. See echo/tests/architecture/ for
proof the detection logic itself works, using synthetic fixtures.

Usage: python scripts/check_architecture.py [root]
Defaults to scanning the parent of this scripts/ directory (i.e. echo/).
"""

from __future__ import annotations

import ast
import sys
from dataclasses import dataclass
from pathlib import Path

EXCLUDED_DIR_NAMES = {
    "__pycache__",
    ".venv",
    "venv",
    ".git",
    "node_modules",
    "tests",
    "scripts",
    ".mypy_cache",
    ".ruff_cache",
    ".pytest_cache",
    "build",
    "echo.egg-info",
}
FORBIDDEN_UTILITY_DIR_NAMES = {"shared", "common", "utils", "helpers", "misc"}


@dataclass(frozen=True)
class Rule:
    name: str
    source_prefix: str
    forbidden_import_prefixes: tuple[str, ...]
    exempt_filenames: frozenset[str] = frozenset()
    message: str = ""


RULES: tuple[Rule, ...] = (
    Rule(
        name="apps-must-not-import-providers",
        source_prefix="apps.",
        forbidden_import_prefixes=("providers.",),
        message="apps/ must not import providers/ directly — go through the domain layer",
    ),
    Rule(
        name="domains-must-not-import-web-framework",
        source_prefix="domains.",
        forbidden_import_prefixes=("fastapi", "starlette"),
        message="domain modules must not import FastAPI/Starlette route objects",
    ),
    Rule(
        name="domains-must-not-import-providers",
        source_prefix="domains.",
        forbidden_import_prefixes=("providers.",),
        message=(
            "domains must not import providers — providers implement domain "
            "interfaces, not vice versa"
        ),
    ),
    Rule(
        name="domains-must-not-import-db-driver-outside-repository",
        source_prefix="domains.",
        forbidden_import_prefixes=("asyncpg", "sqlalchemy"),
        exempt_filenames=frozenset({"repository.py"}),
        message="only a domain's repository.py may import a database driver directly",
    ),
)


def _imports_from_source(source: str) -> list[str]:
    """Returns the dotted module names referenced by import/from-import statements."""
    tree = ast.parse(source)
    names: list[str] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.Import):
            names.extend(alias.name for alias in node.names)
        elif isinstance(node, ast.ImportFrom) and node.module:
            names.append(node.module)
    return names


def check_module(
    module_name: str, file_name: str, imported_names: list[str], rules: tuple[Rule, ...] = RULES
) -> list[str]:
    """Pure function: given a module's identity and its imports, return violation messages."""
    violations: list[str] = []

    for rule in rules:
        if not module_name.startswith(rule.source_prefix):
            continue
        if file_name in rule.exempt_filenames:
            continue
        for imported in imported_names:
            if imported.startswith(rule.forbidden_import_prefixes):
                violations.append(
                    f"{module_name} ({file_name}) imports '{imported}': "
                    f"{rule.message} [{rule.name}]"
                )

    violations.extend(_check_domain_isolation(module_name, imported_names))
    return violations


def _check_domain_isolation(module_name: str, imported_names: list[str]) -> list[str]:
    """domains.X.* must not import domains.Y.* for any Y != X (no domain-to-domain imports)."""
    if not module_name.startswith("domains."):
        return []
    own_domain = module_name.split(".")[1]
    violations = []
    for imported in imported_names:
        if imported.startswith("domains."):
            other_domain = imported.split(".")[1]
            if other_domain != own_domain:
                violations.append(
                    f"{module_name} imports '{imported}': domain-to-domain imports are prohibited "
                    f"— coordinate through the Application layer or domain events "
                    f"[no-domain-to-domain-imports]"
                )
    return violations


def _module_name_for_path(path: Path, root: Path) -> str:
    relative = path.relative_to(root).with_suffix("")
    parts = relative.parts
    if parts[-1] == "__init__":
        parts = parts[:-1]
    return ".".join(parts)


def _check_forbidden_utility_dirs(root: Path) -> list[str]:
    violations = []
    for path in root.rglob("*"):
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        if path.is_dir() and path.name in FORBIDDEN_UTILITY_DIR_NAMES:
            violations.append(
                f"{path}: generic '{path.name}/' directories require an approved ADR "
                f"[no-generic-utility-modules]"
            )
    return violations


def main(argv: list[str]) -> int:
    root = Path(argv[0]) if argv else Path(__file__).resolve().parent.parent
    if not root.exists():
        print(f"{root} does not exist — nothing to check.")
        return 0

    violations: list[str] = []
    for path in sorted(root.rglob("*.py")):
        if any(part in EXCLUDED_DIR_NAMES for part in path.relative_to(root).parts):
            continue
        module_name = _module_name_for_path(path, root)
        imported_names = _imports_from_source(path.read_text(encoding="utf-8"))
        violations.extend(check_module(module_name, path.name, imported_names))

    violations.extend(_check_forbidden_utility_dirs(root))

    if violations:
        for v in violations:
            print(v)
        return 1

    print("No architecture violations found.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
