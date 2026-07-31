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


def test_transient_errors_is_tuple():
    """Verify TRANSIENT_ERRORS is a tuple of exception classes."""
    assert isinstance(TRANSIENT_ERRORS, tuple)
    assert len(TRANSIENT_ERRORS) > 0
    # All items should be exception classes
    for exc_class in TRANSIENT_ERRORS:
        assert issubclass(exc_class, BaseException)
