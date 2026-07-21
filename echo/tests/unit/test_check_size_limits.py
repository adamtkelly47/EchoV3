"""Proves the size-limit checker (scripts/check_size_limits.py) enforces
Docs/CONSTITUTION.md's thresholds — the Phase 2 verification criterion
"a deliberate function over 500 lines fails the build".
"""

from pathlib import Path

from scripts.check_size_limits import check_file


def _write(tmp_path: Path, name: str, content: str) -> Path:
    path = tmp_path / name
    path.write_text(content, encoding="utf-8")
    return path


def test_short_function_has_no_hard_failure(tmp_path: Path) -> None:
    path = _write(tmp_path, "ok.py", "def small():\n    return 1\n")
    messages, hard_failure = check_file(path)
    assert hard_failure is False
    assert messages == []


def test_function_over_500_lines_is_a_hard_failure(tmp_path: Path) -> None:
    body = "\n".join(f"    x{i} = {i}" for i in range(501))
    source = f"def huge():\n{body}\n    return x0\n"
    path = _write(tmp_path, "huge.py", source)
    messages, hard_failure = check_file(path)
    assert hard_failure is True
    assert any("BUILD FAILURE" in m for m in messages)


def test_function_over_100_lines_warns_but_does_not_fail(tmp_path: Path) -> None:
    # 120 body lines + def/return = 122 total: crosses the 100-line tier
    # without also crossing the 150-line tier, to isolate which label fires.
    body = "\n".join(f"    x{i} = {i}" for i in range(120))
    source = f"def medium():\n{body}\n    return x0\n"
    path = _write(tmp_path, "medium.py", source)
    messages, hard_failure = check_file(path)
    assert hard_failure is False
    assert any("review warning" in m for m in messages)
