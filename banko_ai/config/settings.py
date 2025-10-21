"""
Configuration management using environment variables.

This module provides a centralized configuration system that reads from environment
variables with sensible defaults, making the application easy to configure and deploy.
"""

import os
from typing import Optional, Dict, Any, List
from dataclasses import dataclass


@dataclass
class Config:
    """Application configuration loaded from environment variables."""
    
    # Database Configuration
    database_url: str
    database_host: str = "localhost"
    database_port: int = 26257
    database_name: str = "defaultdb"
    database_user: str = "root"
    database_password: str = ""
    ssl_mode: str = "disable"
    
    # AI Service Configuration
    ai_service: str = "watsonx"  # openai, aws, watsonx, gemini
    openai_api_key: Optional[str] = None
    openai_model: str = "gpt-4o-mini"  # gpt-4o-mini (default), gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o
    aws_access_key_id: Optional[str] = None
    aws_secret_access_key: Optional[str] = None
    aws_region: str = "us-east-1"
    aws_model: str = "us.anthropic.claude-3-5-sonnet-20241022-v2:0"  # Claude models
    watsonx_api_key: Optional[str] = None
    watsonx_project_id: Optional[str] = None
    watsonx_model: str = "openai/gpt-oss-120b"  # IBM models
    google_project_id: Optional[str] = None
    google_location: str = "us-central1"
    google_model: str = "gemini-1.5-pro"  # Gemini models
    
    # Application Configuration
    secret_key: str = "your-secret-key-change-in-production"
    debug: bool = False
    host: str = "0.0.0.0"
    port: int = 5000
    
    # Vector Search Configuration
    embedding_model: str = "all-MiniLM-L6-v2"
    vector_dimensions: int = 384
    similarity_threshold: float = 0.7
    
    # Cache Configuration
    cache_enabled: bool = True
    cache_ttl: int = 3600  # 1 hour
    
    # Data Generation Configuration
    default_record_count: int = 10000
    default_user_count: int = 100
    
    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        # Database configuration - match original app.py
        database_url = os.getenv("DATABASE_URL", "cockroachdb://root@localhost:26257/defaultdb?sslmode=disable")
        
        # Parse database URL for individual components
        db_host = os.getenv("DATABASE_HOST", "localhost")
        db_port = int(os.getenv("DATABASE_PORT", "26257"))
        db_name = os.getenv("DATABASE_NAME", "defaultdb")  # Match original
        db_user = os.getenv("DATABASE_USER", "root")
        db_password = os.getenv("DATABASE_PASSWORD", "")
        ssl_mode = os.getenv("DATABASE_SSL_MODE", "disable")
        
        # AI Service configuration - match original app.py
        ai_service = os.getenv("AI_SERVICE", "watsonx").lower()
        
        # Try to load from config.py like the original app.py does
        try:
            import sys
            # Add parent directory to path to import config.py
            parent_dir = os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
            if parent_dir not in sys.path:
                sys.path.insert(0, parent_dir)
            from config import WATSONX_API_KEY, WATSONX_PROJECT_ID, WATSONX_MODEL_ID
            watsonx_api_key = WATSONX_API_KEY
            watsonx_project_id = WATSONX_PROJECT_ID
            watsonx_model = WATSONX_MODEL_ID
        except ImportError:
            # Fall back to environment variables
            watsonx_api_key = os.getenv("WATSONX_API_KEY")
            watsonx_project_id = os.getenv("WATSONX_PROJECT_ID")
            watsonx_model = os.getenv("WATSONX_MODEL", "openai/gpt-oss-120b")
        
        return cls(
            # Database
            database_url=database_url,
            database_host=db_host,
            database_port=db_port,
            database_name=db_name,
            database_user=db_user,
            database_password=db_password,
            ssl_mode=ssl_mode,
            
            # AI Services
            ai_service=ai_service,
            openai_api_key=os.getenv("OPENAI_API_KEY"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_model=os.getenv("AWS_MODEL", "us.anthropic.claude-3-5-sonnet-20241022-v2:0"),
            watsonx_api_key=watsonx_api_key,
            watsonx_project_id=watsonx_project_id,
            watsonx_model=watsonx_model,
            google_project_id=os.getenv("GOOGLE_PROJECT_ID"),
            google_location=os.getenv("GOOGLE_LOCATION", "us-central1"),
            google_model=os.getenv("GOOGLE_MODEL", "gemini-1.5-pro"),
            
            # Application
            secret_key=os.getenv("SECRET_KEY", "your-secret-key-change-in-production"),
            debug=os.getenv("DEBUG", "false").lower() == "true",
            host=os.getenv("HOST", "0.0.0.0"),
            port=int(os.getenv("PORT", "5000")),
            
            # Vector Search
            embedding_model=os.getenv("EMBEDDING_MODEL", "all-MiniLM-L6-v2"),
            vector_dimensions=int(os.getenv("VECTOR_DIMENSIONS", "384")),
            similarity_threshold=float(os.getenv("SIMILARITY_THRESHOLD", "0.7")),
            
            # Cache
            cache_enabled=os.getenv("CACHE_ENABLED", "true").lower() == "true",
            cache_ttl=int(os.getenv("CACHE_TTL", "3600")),
            
            # Data Generation
            default_record_count=int(os.getenv("DEFAULT_RECORD_COUNT", "10000")),
            default_user_count=int(os.getenv("DEFAULT_USER_COUNT", "100")),
        )
    
    def get_ai_config(self) -> Dict[str, Any]:
        """Get AI service specific configuration."""
        config = {
            "service": self.ai_service,
            "openai": {
                "api_key": self.openai_api_key,
                "model": self.openai_model,
            },
            "aws": {
                "access_key_id": self.aws_access_key_id,
                "secret_access_key": self.aws_secret_access_key,
                "region": self.aws_region,
                "model": self.aws_model,
            },
            "watsonx": {
                "api_key": self.watsonx_api_key,
                "project_id": self.watsonx_project_id,
                "model": self.watsonx_model,
            },
            "gemini": {
                "project_id": self.google_project_id,
                "location": self.google_location,
                "model": self.google_model,
            }
        }
        return config
    
    def get_available_models(self) -> Dict[str, List[str]]:
        """Get available models for each AI provider."""
        return {
            "openai": [
                "gpt-3.5-turbo",
                "gpt-3.5-turbo-16k", 
                "gpt-4",
                "gpt-4-turbo",
                "gpt-4o",
                "gpt-4o-mini"
            ],
            "aws": [
                "us.anthropic.claude-3-5-sonnet-20241022-v2:0",
                "us.anthropic.claude-3-5-haiku-20241022-v1:0",
                "us.anthropic.claude-3-opus-20240229-v1:0",
                "us.anthropic.claude-3-sonnet-20240229-v1:0",
                "us.anthropic.claude-3-haiku-20240307-v1:0"
            ],
            "watsonx": [
                "openai/gpt-oss-120b",
                "ibm/granite-13b-chat-v2",
                "ibm/granite-13b-instruct-v2",
                "ibm/granite-8b-chat-v2",
                "ibm/granite-8b-instruct-v2",
                "meta-llama/llama-2-70b-chat",
                "meta-llama/llama-2-13b-chat"
            ],
            "gemini": [
                "gemini-1.5-pro",
                "gemini-1.5-flash",
                "gemini-1.0-pro"
            ]
        }
    
    def validate(self) -> None:
        """Validate configuration and raise errors for missing required values."""
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        
        # Validate AI service specific requirements
        if self.ai_service == "openai" and not self.openai_api_key:
            # For demo purposes, make OpenAI API key optional
            print("Warning: OPENAI_API_KEY not provided. AI features will be limited.")
        elif self.ai_service == "aws" and (not self.aws_access_key_id or not self.aws_secret_access_key):
            raise ValueError("AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY are required for AWS service")
        elif self.ai_service == "watsonx" and not self.watsonx_api_key:
            # For demo purposes, make Watsonx API key optional
            print("Warning: WATSONX_API_KEY not provided. AI features will be limited.")
        elif self.ai_service == "gemini" and not self.google_project_id:
            raise ValueError("GOOGLE_PROJECT_ID is required for Gemini service")


# Global configuration instance
_config: Optional[Config] = None


def get_config() -> Config:
    """Get the global configuration instance."""
    global _config
    if _config is None:
        _config = Config.from_env()
        _config.validate()
    return _config


def set_config(config: Config) -> None:
    """Set the global configuration instance (useful for testing)."""
    global _config
    _config = config
