"""
InboxPilot — Centralized Configuration
Loads all API keys from .env and validates required ones at startup.
"""
import os
from dotenv import load_dotenv

load_dotenv()


class Config:
    """Application configuration loaded from environment variables."""

    # AgentMail
    AGENTMAIL_API_KEY: str = os.getenv("AGENTMAIL_API_KEY", "")

    # Firecrawl
    FIRECRAWL_API_KEY: str = os.getenv("FIRECRAWL_API_KEY", "")

    # Roboflow
    ROBOFLOW_API_KEY: str = os.getenv("ROBOFLOW_API_KEY", "")
    ROBOFLOW_PUBLISHABLE_KEY: str = os.getenv("ROBOFLOW_PUBLISHABLE_KEY", "")

    # OpenAI
    OPENAI_API_KEY: str = os.getenv("OPENAI_API_KEY", "")

    # Gumloop (optional)
    GUMLOOP_API_KEY: str = os.getenv("GUMLOOP_API_KEY", "")
    GUMLOOP_USER_ID: str = os.getenv("GUMLOOP_USER_ID", "")

    # Omium (optional — for bonus tracing)
    OMIUM_API_KEY: str = os.getenv("OMIUM_API_KEY", "")

    # Server
    HOST: str = os.getenv("HOST", "0.0.0.0")
    PORT: int = int(os.getenv("PORT", "8000"))

    # Database
    DATABASE_URL: str = "sqlite+aiosqlite:///./inbox_pilot.db"

    # Agent inbox name
    INBOX_USERNAME: str = os.getenv("INBOX_USERNAME", "inbox-pilot")

    @classmethod
    def validate(cls) -> list[str]:
        """Validate that required API keys are set. Returns list of missing keys."""
        required = {
            "AGENTMAIL_API_KEY": cls.AGENTMAIL_API_KEY,
            "FIRECRAWL_API_KEY": cls.FIRECRAWL_API_KEY,
            "ROBOFLOW_API_KEY": cls.ROBOFLOW_API_KEY,
            "OPENAI_API_KEY": cls.OPENAI_API_KEY,
        }
        missing = [k for k, v in required.items() if not v]
        return missing

    @classmethod
    def has_gumloop(cls) -> bool:
        return bool(cls.GUMLOOP_API_KEY and cls.GUMLOOP_USER_ID)

    @classmethod
    def has_omium(cls) -> bool:
        return bool(cls.OMIUM_API_KEY)


config = Config()
