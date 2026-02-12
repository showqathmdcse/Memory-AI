"""
Kafka configuration and settings.
"""
import os
from pydantic_settings import BaseSettings


class KafkaSettings(BaseSettings):
    """Kafka configuration settings."""
    
    # Enable/disable streaming
    streaming_enabled: bool = os.getenv("KAFKA_STREAMING_ENABLED", "false").lower() == "true"
    
    # Kafka connection
    kafka_bootstrap_servers: str = os.getenv("KAFKA_BOOTSTRAP_SERVERS", "localhost:9092")
    kafka_topic_messages: str = os.getenv("KAFKA_TOPIC_MESSAGES", "agent-messages")
    kafka_topic_code_changes: str = os.getenv("KAFKA_TOPIC_CODE_CHANGES", "code-changes")
    
    # Producer settings
    kafka_producer_compression: str = os.getenv("KAFKA_PRODUCER_COMPRESSION", "gzip")
    kafka_producer_max_request_size: int = int(os.getenv("KAFKA_PRODUCER_MAX_REQUEST_SIZE", "1048576"))
    
    class Config:
        env_file = ".env"
        case_sensitive = False


kafka_settings = KafkaSettings()
