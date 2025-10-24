"""
Database retry utilities for handling transient connection failures.

This module provides decorators and utilities to automatically retry database
operations that fail due to transient errors like connection blips, HAProxy
resets, or network issues.
"""

import time
import functools
from typing import Callable, Type, Tuple, Optional
from sqlalchemy.exc import OperationalError, DBAPIError
import psycopg2


# Transient errors that should trigger a retry
TRANSIENT_ERRORS = (
    OperationalError,
    psycopg2.OperationalError,
    psycopg2.InterfaceError,
    DBAPIError,
)

# Error messages that indicate transient failures
TRANSIENT_ERROR_MESSAGES = (
    "server closed the connection unexpectedly",
    "connection already closed",
    "SSL connection has been closed unexpectedly",
    "could not receive data from server",
    "connection timed out",
    "Connection refused",
    "connection reset by peer",
    "broken pipe",
    "restart transaction",
    "TransactionRetryError",
    "SerializationFailure",
    "40001",  # PostgreSQL/CockroachDB serialization failure code
)


def is_transient_error(error: Exception) -> bool:
    """
    Check if an error is transient and should be retried.
    
    Args:
        error: The exception to check
        
    Returns:
        True if the error is transient and retryable
    """
    if not isinstance(error, TRANSIENT_ERRORS):
        return False
    
    error_msg = str(error).lower()
    return any(msg.lower() in error_msg for msg in TRANSIENT_ERROR_MESSAGES)


def db_retry(
    max_attempts: int = 3,
    initial_delay: float = 0.5,
    backoff_factor: float = 2.0,
    max_delay: float = 10.0,
    exceptions: Tuple[Type[Exception], ...] = TRANSIENT_ERRORS
):
    """
    Decorator to retry database operations on transient failures.
    
    Uses exponential backoff with configurable parameters:
    - Retry delay: initial_delay * (backoff_factor ** attempt)
    - Capped at max_delay
    
    Args:
        max_attempts: Maximum number of retry attempts (default: 3)
        initial_delay: Initial retry delay in seconds (default: 0.5)
        backoff_factor: Multiplier for exponential backoff (default: 2.0)
        max_delay: Maximum delay between retries (default: 10.0)
        exceptions: Tuple of exception types to catch and retry
        
    Example:
        @db_retry(max_attempts=5, initial_delay=1.0)
        def query_database():
            # Your database operation here
            pass
    """
    def decorator(func: Callable) -> Callable:
        @functools.wraps(func)
        def wrapper(*args, **kwargs):
            attempt = 0
            delay = initial_delay
            
            while attempt < max_attempts:
                try:
                    return func(*args, **kwargs)
                    
                except exceptions as e:
                    attempt += 1
                    
                    # Check if error is truly transient
                    if not is_transient_error(e):
                        print(f"❌ Non-transient error in {func.__name__}: {e}")
                        raise
                    
                    if attempt >= max_attempts:
                        print(f"❌ Max retry attempts ({max_attempts}) reached for {func.__name__}")
                        raise
                    
                    # Calculate next delay with exponential backoff
                    current_delay = min(delay * (backoff_factor ** (attempt - 1)), max_delay)
                    
                    print(f"⚠️  Transient DB error in {func.__name__} (attempt {attempt}/{max_attempts}): {e}")
                    print(f"🔄 Retrying in {current_delay:.2f}s...")
                    
                    time.sleep(current_delay)
                    
            # This should never be reached, but just in case
            raise Exception(f"Unexpected state in retry logic for {func.__name__}")
        
        return wrapper
    return decorator


def db_retry_context(max_attempts: int = 3, initial_delay: float = 0.5):
    """
    Context manager for database retry logic.
    
    Usage:
        with db_retry_context(max_attempts=5):
            # Your database operations here
            conn.execute(query)
    """
    class RetryContext:
        def __init__(self, max_attempts, initial_delay):
            self.max_attempts = max_attempts
            self.initial_delay = initial_delay
            self.attempt = 0
            
        def __enter__(self):
            return self
            
        def __exit__(self, exc_type, exc_val, exc_tb):
            if exc_type and issubclass(exc_type, TRANSIENT_ERRORS):
                if is_transient_error(exc_val):
                    self.attempt += 1
                    if self.attempt < self.max_attempts:
                        delay = self.initial_delay * (2 ** (self.attempt - 1))
                        print(f"⚠️  Transient DB error (attempt {self.attempt}/{self.max_attempts}): {exc_val}")
                        print(f"🔄 Retrying in {delay:.2f}s...")
                        time.sleep(delay)
                        return True  # Suppress exception and retry
            return False  # Don't suppress exception
    
    return RetryContext(max_attempts, initial_delay)


def create_resilient_engine(database_url: str, **kwargs):
    """
    Create a SQLAlchemy engine with resilience settings for CockroachDB/HAProxy.
    
    Configures connection pooling and health checks to handle transient failures:
    - pool_pre_ping: Test connections before use
    - pool_recycle: Recycle connections periodically
    - pool_size: Larger pool for better availability
    - max_overflow: Allow temporary connections during spikes
    
    Args:
        database_url: Database connection URL
        **kwargs: Additional engine parameters
        
    Returns:
        Configured SQLAlchemy engine
    """
    from sqlalchemy import create_engine
    
    # Default resilience settings
    default_config = {
        "pool_pre_ping": True,  # Test connection before using
        "pool_recycle": 300,     # Recycle connections every 5 minutes
        "pool_size": 10,         # Maintain 10 connections
        "max_overflow": 20,      # Allow 20 additional connections during spikes
        "pool_timeout": 30,      # Wait up to 30s for a connection
        "echo_pool": False,      # Disable pool debug logging
        "connect_args": {
            "connect_timeout": 10,  # Connection timeout
            "options": "-c default_transaction_isolation=serializable"
        }
    }
    
    # Merge with user-provided config
    config = {**default_config, **kwargs}
    
    # Merge connect_args separately to avoid overwriting
    if "connect_args" in kwargs:
        config["connect_args"] = {**default_config["connect_args"], **kwargs["connect_args"]}
    
    return create_engine(database_url, **config)
