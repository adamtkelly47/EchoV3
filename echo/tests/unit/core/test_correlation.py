from core.observability.correlation import correlation_scope, get_correlation_id


def test_no_correlation_id_outside_a_scope() -> None:
    assert get_correlation_id() is None


def test_scope_generates_an_id_when_none_supplied() -> None:
    with correlation_scope() as correlation_id:
        assert correlation_id is not None
        assert get_correlation_id() == correlation_id


def test_scope_uses_supplied_id() -> None:
    with correlation_scope("corr_fixed"):
        assert get_correlation_id() == "corr_fixed"


def test_id_is_cleared_after_scope_exits() -> None:
    with correlation_scope("corr_fixed"):
        pass
    assert get_correlation_id() is None


def test_nested_scopes_restore_outer_id_on_exit() -> None:
    with correlation_scope("outer"):
        with correlation_scope("inner"):
            assert get_correlation_id() == "inner"
        assert get_correlation_id() == "outer"
