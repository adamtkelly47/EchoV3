#!/usr/bin/env python
"""Enforces Docs/CONSTITUTION.md's File and Function Discipline thresholds.

Function length has an explicit "build failure" tier (500 lines) in the
Constitution; file length only has a "soft ceiling" (10,000 lines), which
the Constitution says requires justification rather than being mechanically
impossible. So: functions over 500 lines fail this script (exit 1); files
over any threshold only warn (exit 0) — matching that distinction exactly.

Usage: python scripts/check_size_limits.py [root...]
Defaults to scanning ./apps if no root is given.
"""

from __future__ import annotations

import ast
import sys
from pathlib import Path

FUNCTION_THRESHOLDS = [
    (500, "BUILD FAILURE"),
    (300, "architecture review required"),
    (150, "strong refactor warning"),
    (100, "review warning"),
]
FILE_THRESHOLDS = [
    (10_000, "soft ceiling — requires extraordinary justification"),
    (3_000, "architecture review required"),
    (1_500, "strong refactor warning"),
    (800, "review warning"),
]

EXCLUDED_DIR_NAMES = {"__pycache__", ".venv", "venv", ".git", "node_modules"}


def _iter_python_files(roots: list[Path]) -> list[Path]:
    files: list[Path] = []
    for root in roots:
        for path in root.rglob("*.py"):
            if any(part in EXCLUDED_DIR_NAMES for part in path.parts):
                continue
            files.append(path)
    return files


def _function_spans(tree: ast.AST) -> list[tuple[str, int, int]]:
    spans: list[tuple[str, int, int]] = []
    for node in ast.walk(tree):
        if isinstance(node, ast.FunctionDef | ast.AsyncFunctionDef):
            end = node.end_lineno or node.lineno
            spans.append((node.name, node.lineno, end - node.lineno + 1))
    return spans


def check_file(path: Path) -> tuple[list[str], bool]:
    """Returns (messages, has_hard_failure)."""
    messages: list[str] = []
    hard_failure = False

    text = path.read_text(encoding="utf-8")
    line_count = text.count("\n") + 1

    for threshold, label in FILE_THRESHOLDS:
        if line_count > threshold:
            messages.append(f"{path}: {line_count} lines — {label} (>{threshold})")
            break  # only report the highest tier crossed

    tree = ast.parse(text, filename=str(path))
    for name, lineno, length in _function_spans(tree):
        for threshold, label in FUNCTION_THRESHOLDS:
            if length > threshold:
                is_failure = threshold == 500
                messages.append(
                    f"{path}:{lineno}: function '{name}' is {length} lines — {label} (>{threshold})"
                )
                hard_failure = hard_failure or is_failure
                break

    return messages, hard_failure


def main(argv: list[str]) -> int:
    roots = [Path(a) for a in argv] or [Path("apps")]
    roots = [r for r in roots if r.exists()]
    if not roots:
        print("No roots to scan (nothing exists yet) — nothing to check.")
        return 0

    any_hard_failure = False
    any_message = False
    for path in sorted(_iter_python_files(roots)):
        messages, hard_failure = check_file(path)
        for message in messages:
            print(message)
            any_message = True
        any_hard_failure = any_hard_failure or hard_failure

    if not any_message:
        print("All files within size limits.")

    return 1 if any_hard_failure else 0


if __name__ == "__main__":
    raise SystemExit(main(sys.argv[1:]))
