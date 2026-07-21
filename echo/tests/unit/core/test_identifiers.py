from core.identifiers import new_id


def test_ids_are_unique() -> None:
    ids = {new_id() for _ in range(1000)}
    assert len(ids) == 1000


def test_prefix_is_applied() -> None:
    identifier = new_id("proposal")
    assert identifier.startswith("proposal_")


def test_no_prefix_has_no_leading_underscore() -> None:
    identifier = new_id()
    assert not identifier.startswith("_")
