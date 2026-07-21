import pytest

from domains.capabilities.errors import CapabilityAlreadyRegisteredError, CapabilityNotFoundError
from domains.capabilities.service import CapabilityRegistry
from tests.unit.domains.capabilities.fakes import make_echo_capability


def test_register_and_get() -> None:
    registry = CapabilityRegistry()
    capability = make_echo_capability()
    registry.register(capability)

    assert registry.get("test.echo") is capability


def test_get_unregistered_capability_raises() -> None:
    registry = CapabilityRegistry()
    with pytest.raises(CapabilityNotFoundError):
        registry.get("does.not.exist")


def test_duplicate_registration_raises() -> None:
    registry = CapabilityRegistry()
    registry.register(make_echo_capability())
    with pytest.raises(CapabilityAlreadyRegisteredError):
        registry.register(make_echo_capability())


def test_list_contracts_reflects_registered_capabilities() -> None:
    registry = CapabilityRegistry()
    registry.register(make_echo_capability("a"))
    registry.register(make_echo_capability("b"))

    ids = {contract.capability_id for contract in registry.list_contracts()}
    assert ids == {"a", "b"}


def test_discovery_requires_no_keyword_list() -> None:
    """CONSTITUTION.md: capabilities are discovered through registration,
    never keyword lists — proven by the fact that listing capabilities
    requires nothing but calling list_contracts(), no name matching."""
    registry = CapabilityRegistry()
    registry.register(make_echo_capability("anything.at.all"))
    assert len(registry.list_contracts()) == 1
