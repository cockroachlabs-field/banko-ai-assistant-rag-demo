"""
User authentication and management.

This module provides simple user authentication for the Banko AI Assistant.
"""

import uuid
from typing import Optional, Dict, Any
from flask import session


class UserManager:
    """Simple user management for the application."""
    
    def __init__(self):
        """Initialize the user manager."""
        self.users = {}  # In production, this would be a database
    
    def create_user(self, username: str, email: str = None) -> str:
        """
        Create a new user.
        
        Args:
            username: Username for the user
            email: Optional email address
            
        Returns:
            User ID
        """
        user_id = str(uuid.uuid4())
        self.users[user_id] = {
            "id": user_id,
            "username": username,
            "email": email,
            "created_at": None  # Would be datetime in production
        }
        return user_id
    
    def get_user(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Get user by ID."""
        return self.users.get(user_id)
    
    def get_current_user(self) -> Optional[Dict[str, Any]]:
        """Get current user from session."""
        user_id = session.get('user_id')
        if user_id:
            return self.get_user(user_id)
        return None
    
    def login_user(self, user_id: str) -> bool:
        """Login user by setting session."""
        if user_id in self.users:
            session['user_id'] = user_id
            return True
        return False
    
    def logout_user(self) -> None:
        """Logout current user."""
        session.pop('user_id', None)
    
    def is_logged_in(self) -> bool:
        """Check if user is logged in."""
        return 'user_id' in session and session['user_id'] in self.users
    
    def get_or_create_current_user(self) -> str:
        """Get or create current user."""
        if self.is_logged_in():
            return session['user_id']
        
        # Create a default user
        user_id = self.create_user("Default User")
        self.login_user(user_id)
        return user_id
