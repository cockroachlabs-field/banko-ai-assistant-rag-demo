"""
Test the TRANSIENT_ERRORS contract for the chat error handler.

This test verifies that TRANSIENT_ERRORS correctly identifies transient
database errors (like connection failures) that should show a friendly
reconnection message instead of the technical error text.
"""

import pytest
from sqlalchemy.exc import OperationalError

from banko_ai.utils.db_retry import TRANSIENT_ERRORS


def test_operational_error_in_transient_errors():
    """Assert that OperationalError is in TRANSIENT_ERRORS tuple."""
    # Create an OperationalError instance to verify isinstance check works
    op_error = OperationalError("stmt", {}, Exception("x"))
    assert isinstance(op_error, TRANSIENT_ERRORS)


def test_value_error_not_in_transient_errors():
    """Assert that a plain ValueError is not matched by TRANSIENT_ERRORS."""
    plain_error = ValueError("some plain value error")
    assert not isinstance(plain_error, TRANSIENT_ERRORS)


def test_transient_errors_usable_with_isinstance():
    """The contract callers rely on: the tuple works as an isinstance /
    except target and matches subclasses of its members, not just exact
    types. (Replaces a tautological is-it-a-tuple check.)"""

    class DerivedOperationalError(OperationalError):
        pass

    derived = DerivedOperationalError("stmt", {}, Exception("x"))
    assert isinstance(derived, TRANSIENT_ERRORS)
    try:
        raise derived
    except TRANSIENT_ERRORS:
        pass
