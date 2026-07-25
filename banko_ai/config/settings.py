"""
Configuration management using environment variables.

This module provides a centralized configuration system that reads from environment
variables with sensible defaults, making the application easy to configure and deploy.
"""

import os
import secrets
from dataclasses import dataclass
from typing import Any

from ..utils.db_retry import get_database_url


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
    openai_api_key: str | None = None
    openai_base_url: str = ""
    ollama_host: str = "http://localhost:11434"
    ollama_model: str = "granite3.3:8b"
    openai_model: str = "gpt-4o-mini"  # gpt-4o-mini (default), gpt-3.5-turbo, gpt-4, gpt-4-turbo, gpt-4o
    aws_access_key_id: str | None = None
    aws_secret_access_key: str | None = None
    
    # Fraud Detection Configuration
    fraud_duplicate_window_days: int = 60  # Days to look back for duplicates (60 for demo)
    aws_profile: str | None = None
    aws_region: str = "us-east-1"
    aws_model: str = "us.anthropic.claude-haiku-4-5-20251001-v1:0"  # Claude inference profile (Haiku 4.5; Claude 3.x is Legacy on Bedrock after 30 days idle)
    watsonx_api_key: str | None = None
    watsonx_project_id: str | None = None
    watsonx_model: str = "openai/gpt-oss-120b"  # IBM models
    google_project_id: str | None = None
    google_location: str = "us-central1"
    google_model: str = "gemini-1.5-pro"  # Gemini models
    
    # Application Configuration
    secret_key: str = ""
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
    
    # Agent Configuration
    monthly_budget_default: float = 10000.0  # Default monthly budget for budget agent
    
    # Checkpointer Configuration
    checkpoint_ttl_days: int = 7  # Auto-expire LangGraph checkpoints after N days (0 = disabled)

    # Coach Configuration (added 2026-05-22)
    cdc_webhook_hmac_secret: str = ""
    coach_rate_limit_per_5min: int = 30
    coach_agent_max_steps: int = 5
    coach_socketio_room_prefix: str = "coach:"
    coach_default_user_id: str = "00000000-0000-0000-0000-0000000000a1"
    coach_kafka_enabled: bool = False
    coach_tx_default_limit: int = 25
    coach_agg_lookback_days: int = 30
    coach_velocity_horizon_days: int = 90
    coach_top_merchants_k: int = 5
    coach_subscription_min_occurrences: int = 3

    @classmethod
    def from_env(cls) -> "Config":
        """Create configuration from environment variables."""
        # Database configuration
        database_url = get_database_url()
        
        # Parse database URL for individual components
        db_host = os.getenv("DATABASE_HOST", "localhost")
        db_port = int(os.getenv("DATABASE_PORT", "26257"))
        db_name = os.getenv("DATABASE_NAME", "defaultdb")  # Match original
        db_user = os.getenv("DATABASE_USER", "root")
        db_password = os.getenv("DATABASE_PASSWORD", "")
        ssl_mode = os.getenv("DATABASE_SSL_MODE", "disable")
        
        # AI Service configuration - match original app.py
        ai_service = os.getenv("AI_SERVICE", "watsonx").lower()
        
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
            openai_base_url=os.getenv("OPENAI_BASE_URL", ""),
            ollama_host=os.getenv("OLLAMA_HOST", "http://localhost:11434"),
            ollama_model=os.getenv("OLLAMA_MODEL", "granite3.3:8b"),
            openai_model=os.getenv("OPENAI_MODEL", "gpt-4o-mini"),
            aws_access_key_id=os.getenv("AWS_ACCESS_KEY_ID"),
            aws_secret_access_key=os.getenv("AWS_SECRET_ACCESS_KEY"),
            aws_profile=os.getenv("AWS_PROFILE"),
            aws_region=os.getenv("AWS_REGION", "us-east-1"),
            aws_model=os.getenv("AWS_MODEL", "us.anthropic.claude-haiku-4-5-20251001-v1:0"),
            watsonx_api_key=watsonx_api_key,
            watsonx_project_id=watsonx_project_id,
            watsonx_model=watsonx_model,
            google_project_id=os.getenv("GOOGLE_PROJECT_ID"),
            
            # Fraud Detection
            fraud_duplicate_window_days=int(os.getenv("FRAUD_DUPLICATE_WINDOW_DAYS", "60")),
            google_location=os.getenv("GOOGLE_LOCATION", "us-central1"),
            google_model=os.getenv("GOOGLE_MODEL", "gemini-1.5-pro"),
            
            # Application
            secret_key=os.getenv("SECRET_KEY", ""),
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
            
            # Agent configuration
            monthly_budget_default=float(os.getenv("MONTHLY_BUDGET_DEFAULT", "10000.0")),
            
            # Checkpointer
            checkpoint_ttl_days=int(os.getenv("CHECKPOINT_TTL_DAYS", "7")),

            # Coach
            cdc_webhook_hmac_secret=os.getenv("CDC_WEBHOOK_HMAC_SECRET", ""),
            coach_rate_limit_per_5min=int(os.getenv("COACH_RATE_LIMIT_PER_5MIN", "30")),
            coach_agent_max_steps=int(os.getenv("COACH_AGENT_MAX_STEPS", "5")),
            coach_socketio_room_prefix=os.getenv("COACH_SOCKETIO_ROOM_PREFIX", "coach:"),
            coach_default_user_id=os.getenv(
                "COACH_DEFAULT_USER_ID",
                "00000000-0000-0000-0000-0000000000a1",
            ),
            coach_kafka_enabled=os.getenv("COACH_KAFKA_ENABLED", "false").lower() == "true",
            coach_tx_default_limit=int(os.getenv("COACH_TX_DEFAULT_LIMIT", "25")),
            coach_agg_lookback_days=int(os.getenv("COACH_AGG_LOOKBACK_DAYS", "30")),
            coach_velocity_horizon_days=int(os.getenv("COACH_VELOCITY_HORIZON_DAYS", "90")),
            coach_top_merchants_k=int(os.getenv("COACH_TOP_MERCHANTS_K", "5")),
            coach_subscription_min_occurrences=int(os.getenv("COACH_SUBSCRIPTION_MIN_OCCURRENCES", "3")),
        )
    
    def get_ai_config(self) -> dict[str, Any]:
        """Get AI service specific configuration."""
        config = {
            "service": self.ai_service,
            "openai": {
                "api_key": self.openai_api_key,
                "base_url": self.openai_base_url,
                "model": self.openai_model,
            },
            "aws": {
                "access_key_id": self.aws_access_key_id,
                "secret_access_key": self.aws_secret_access_key,
                "profile_name": self.aws_profile,
                "region": self.aws_region,
                "model": self.aws_model,
            },
            "ollama": {
                "host": self.ollama_host,
                "model": self.ollama_model,
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
    
    # NOTE: The hardcoded `get_available_models()` dict that used to live here
    # was removed in May 2026. Source of truth is `ai_provider.get_available_models()`
    # on each concrete provider — they discover from the live SDK/API and fall
    # back to a known-good stub. The Flask route at `/api/models` already reads
    # from the provider; nothing in-tree consumed the Config version.


    def validate(self) -> None:
        """Validate configuration and raise errors for missing required values."""
        if not self.database_url:
            raise ValueError("DATABASE_URL is required")
        
        if not self.secret_key:
            flask_env = os.getenv("FLASK_ENV", "development").lower()
            running_under_gunicorn = "gunicorn" in os.getenv("SERVER_SOFTWARE", "").lower()
            if flask_env == "production" or running_under_gunicorn:
                raise RuntimeError(
                    "SECRET_KEY must be set in production. Multi-worker "
                    "deployments require a stable secret so Flask session "
                    "cookies validate across workers. Set SECRET_KEY in the "
                    "environment (e.g., `export SECRET_KEY=$(python -c "
                    "'import secrets; print(secrets.token_hex(32))')`)."
                )
            self.secret_key = secrets.token_hex(32)
            print("Warning: SECRET_KEY not set. Generated a random key for this session.")
        
        # Validate AI service specific requirements
        if self.ai_service == "openai" and not self.openai_api_key:
            # For demo purposes, make OpenAI API key optional
            print("Warning: OPENAI_API_KEY not provided. AI features will be limited.")
        elif self.ai_service == "aws":
            # Allow either credentials OR profile for AWS
            has_credentials = self.aws_access_key_id and self.aws_secret_access_key
            has_profile = self.aws_profile
            if not has_credentials and not has_profile:
                raise ValueError("AWS requires either (AWS_ACCESS_KEY_ID and AWS_SECRET_ACCESS_KEY) or AWS_PROFILE")
        elif self.ai_service == "watsonx" and not self.watsonx_api_key:
            # For demo purposes, make Watsonx API key optional
            print("Warning: WATSONX_API_KEY not provided. AI features will be limited.")
        elif self.ai_service == "gemini" and not self.google_project_id:
            raise ValueError("GOOGLE_PROJECT_ID is required for Gemini service")


# Global configuration instance
_config: Config | None = None


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
