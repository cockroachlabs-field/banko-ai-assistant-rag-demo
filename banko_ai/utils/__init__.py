"""Utility modules for Banko AI Assistant."""

def get_database_manager():
    """Get DatabaseManager (lazy import)."""
    from .database import DatabaseManager
    return DatabaseManager

__all__ = ["get_database_manager"]
