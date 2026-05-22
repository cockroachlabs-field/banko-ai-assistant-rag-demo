"""Regression test for agent_schema drop_agent_schema identifier safety."""
import pytest

from banko_ai.utils.agent_schema import _ALLOWED_DROP_TABLES, drop_agent_schema


def test_allowed_drop_tables_is_a_frozenset_of_known_names():
    """Whitelist must be immutable and contain the five agent tables."""
    assert isinstance(_ALLOWED_DROP_TABLES, frozenset)
    assert _ALLOWED_DROP_TABLES == frozenset({
        "documents",
        "agent_decisions",
        "agent_tasks",
        "agent_memory",
        "agent_state",
    })


def test_drop_agent_schema_requires_confirm():
    """Calling without confirm=True must be a no-op returning False."""
    assert drop_agent_schema("postgresql://nowhere/db", confirm=False) is False


def test_drop_agent_schema_rejects_unknown_table(monkeypatch):
    """If someone monkey-patches the table list with a hostile value, the call
    must refuse rather than interpolating arbitrary strings into DDL."""
    hostile = ["documents; DROP DATABASE defaultdb;--"]
    monkeypatch.setattr(
        "banko_ai.utils.agent_schema._tables_to_drop",
        lambda: hostile,
    )
    # We deliberately do not pass a real DB URL — the safety check should
    # fire before any connect attempt. Using a clearly-invalid URL would
    # raise on connect; the function must raise ValueError first.
    with pytest.raises(ValueError, match="not in the allowed drop set"):
        drop_agent_schema("postgresql://invalid/db", confirm=True)
