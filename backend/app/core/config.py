import os
from pathlib import Path
from typing import List, Optional
from pydantic_settings import BaseSettings

class Settings(BaseSettings):
    APP_NAME: str = "Autonomous Engineering Agent"
    APP_VERSION: str = "1.0.0"
    DEBUG: bool = True
    API_V1_PREFIX: str = "/api"

    # Host & Port
    HOST: str = "0.0.0.0"
    PORT: int = 8000

    # LLM Settings: "mock", "gemini", "openai", "anthropic"
    LLM_PROVIDER: str = "mock"
    LLM_API_KEY: Optional[str] = None
    OPENAI_API_KEY: Optional[str] = None
    GEMINI_API_KEY: Optional[str] = None
    ANTHROPIC_API_KEY: Optional[str] = None
    LLM_MODEL: str = "gemini-1.5-pro"

    # Database
    DATABASE_URL: str = "sqlite:///./agent.db"
    REDIS_URL: str = "redis://localhost:6379"

    # GitHub Integration
    GITHUB_TOKEN: Optional[str] = None
    GITHUB_CLIENT_ID: Optional[str] = None
    GITHUB_CLIENT_SECRET: Optional[str] = None

    # Agent Engine
    MAX_AGENT_ITERATIONS: int = 5
    SANDBOX_TIMEOUT: int = 120
    SANDBOX_MEMORY_LIMIT: str = "1g"
    REQUIRE_HUMAN_APPROVAL_FOR_PR: bool = False

    # Workspaces directory for cloning repositories
    WORKSPACE_DIR: Path = Path(__file__).resolve().parent.parent.parent.parent / "workspaces"

    model_config = {
        "env_file": ".env",
        "env_file_encoding": "utf-8",
        "extra": "ignore"
    }

settings = Settings()

# Ensure workspaces dir exists
settings.WORKSPACE_DIR.mkdir(parents=True, exist_ok=True)
