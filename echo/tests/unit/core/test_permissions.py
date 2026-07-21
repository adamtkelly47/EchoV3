from core.security.permissions import Permission, PermissionAction


def test_permission_is_structured_not_a_bare_string() -> None:
    permission = Permission(resource="portfolio.positions", action=PermissionAction.READ)
    assert permission.resource == "portfolio.positions"
    assert permission.action == PermissionAction.READ


def test_permission_round_trips_through_json() -> None:
    permission = Permission(resource="calendar.events", action=PermissionAction.WRITE)
    restored = Permission.model_validate_json(permission.model_dump_json())
    assert restored == permission
