"""Configuration management for the application."""

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    """Application settings."""

    # Azure OpenAI Configuration
    azure_openai_api_key: str
    azure_openai_endpoint: str
    azure_openai_deployment: str
    azure_openai_embedding_deployment: str
    azure_openai_api_version: str = "2024-02-15-preview"

    # ChromaDB Configuration
    chroma_url: str

    # Server Configuration
    host: str = "0.0.0.0"
    port: int = 8000
    log_level: str = "INFO"

    # MCP Configuration
    mcp_enabled: bool = False
    mcp_server_url: str = "http://localhost:8081/mcp"
    mcp_timeout: int = 30000  # milliseconds

    # Chat History Configuration
    # Options: "langchain" (in-memory), "chroma" (vector db with semantic search)
    chat_history_storage: str = "langchain"
    chat_history_window_size: int = 20  # Number of messages to keep in memory

    model_config = SettingsConfigDict(
        env_file=".env",
        env_file_encoding="utf-8",
        case_sensitive=False,
        extra='ignore',  # Allow extra env vars (e.g., NATS settings)
    )


# Global settings instance
settings = Settings()
