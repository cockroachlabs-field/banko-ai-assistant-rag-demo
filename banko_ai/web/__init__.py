"""Web application module for Banko AI Assistant."""

def create_app():
    """Create Flask application (lazy import)."""
    from .app import create_app as _create_app
    return _create_app()

def get_user_manager():
    """Get UserManager (lazy import)."""
    from .auth import UserManager
    return UserManager

__all__ = ["create_app", "get_user_manager"]
