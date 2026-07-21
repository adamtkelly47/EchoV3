"""Proves the architecture checker (scripts/check_architecture.py) actually
catches forbidden imports — the concrete Phase 2 verification criterion
"a deliberate forbidden import fails the architecture test". Uses synthetic
module names/imports rather than real files under domains/, since domains/
does not exist yet (Phase 3+).
"""

from scripts.check_architecture import (
    _check_domain_isolation,
    _imports_from_source,
    check_module,
)


def test_imports_from_source_captures_both_import_forms() -> None:
    source = "import fastapi\nfrom domains.portfolio import service\n"
    assert _imports_from_source(source) == ["fastapi", "domains.portfolio"]


def test_apps_importing_providers_is_flagged() -> None:
    violations = check_module(
        module_name="apps.api.main",
        file_name="main.py",
        imported_names=["providers.brokerage.schwab"],
    )
    assert any("apps-must-not-import-providers" in v for v in violations)


def test_domain_importing_fastapi_is_flagged() -> None:
    violations = check_module(
        module_name="domains.portfolio.service",
        file_name="service.py",
        imported_names=["fastapi"],
    )
    assert any("domains-must-not-import-web-framework" in v for v in violations)


def test_domain_importing_db_driver_outside_repository_is_flagged() -> None:
    violations = check_module(
        module_name="domains.portfolio.service",
        file_name="service.py",
        imported_names=["asyncpg"],
    )
    assert any("domains-must-not-import-db-driver-outside-repository" in v for v in violations)


def test_repository_py_is_exempt_from_db_driver_rule() -> None:
    violations = check_module(
        module_name="domains.portfolio.repository",
        file_name="repository.py",
        imported_names=["asyncpg"],
    )
    assert not any("db-driver" in v for v in violations)


def test_compliant_module_has_no_violations() -> None:
    violations = check_module(
        module_name="domains.portfolio.service",
        file_name="service.py",
        imported_names=["domains.portfolio.models", "domains.portfolio.repository"],
    )
    assert violations == []


def test_domain_to_domain_import_is_flagged() -> None:
    violations = _check_domain_isolation(
        module_name="domains.portfolio.service",
        imported_names=["domains.email.repository"],
    )
    assert len(violations) == 1
    assert "no-domain-to-domain-imports" in violations[0]


def test_domain_importing_its_own_submodule_is_not_flagged() -> None:
    violations = _check_domain_isolation(
        module_name="domains.portfolio.service",
        imported_names=["domains.portfolio.models"],
    )
    assert violations == []
