from core.capabilities import ReadWriteClassification
from core.security import Permission, PermissionAction
from domains.capabilities.policies import has_required_permissions, is_executable_now
from tests.unit.domains.capabilities.fakes import make_echo_capability, make_write_capability


def test_no_required_permissions_always_passes() -> None:
    assert has_required_permissions([], frozenset()) is True


def test_missing_required_permission_fails() -> None:
    required = [Permission(resource="portfolio", action=PermissionAction.READ)]
    assert has_required_permissions(required, frozenset()) is False


def test_granted_matching_permission_passes() -> None:
    permission = Permission(resource="portfolio", action=PermissionAction.READ)
    assert has_required_permissions([permission], frozenset({permission})) is True


def test_read_capability_is_executable_now() -> None:
    assert is_executable_now(make_echo_capability().contract) is True


def test_write_capability_is_not_executable_now() -> None:
    contract = make_write_capability().contract
    assert contract.read_write_classification == ReadWriteClassification.WRITE
    assert is_executable_now(contract) is False
