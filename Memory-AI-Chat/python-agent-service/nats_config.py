"""
NATS JetStream configuration and settings.
"""
import os
from pydantic_settings import BaseSettings
from pydantic import Field


class NATSSettings(BaseSettings):
    """NATS JetStream configuration settings."""
    
    # Enable/disable streaming
    streaming_enabled: bool = Field(default=False, alias="NATS_STREAMING_ENABLED")
    
    # NATS connection
    nats_url: str = Field(default="nats://localhost:4222", alias="NATS_URL")
    
    # Streams and subjects
    nats_stream_name: str = Field(default="AGENT_STREAM", alias="NATS_STREAM_NAME")
    nats_subject_messages: str = Field(default="agent.messages", alias="NATS_SUBJECT_MESSAGES")
    nats_subject_code_changes: str = Field(default="agent.code", alias="NATS_SUBJECT_CODE_CHANGES")
    
    # JetStream settings
    nats_max_age_seconds: int = Field(default=86400, alias="NATS_MAX_AGE_SECONDS")  # 24 hours
    nats_max_msgs: int = Field(default=10000, alias="NATS_MAX_MSGS")
    nats_max_bytes: int = Field(default=10485760, alias="NATS_MAX_BYTES")  # 10MB
    
    model_config = {
        "env_file": ".env",
        "case_sensitive": False,
        "extra": "ignore",
        "populate_by_name": True
    }


nats_settings = NATSSettings()
