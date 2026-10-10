"""Environment-based configuration for InfoKun."""

import os


BOT_TOKEN = os.getenv("BOT_TOKEN", "").strip()
OPENWEATHER_KEY = os.getenv("OPENWEATHER_KEY", "").strip()
NEWSAPI_KEY = os.getenv("NEWSAPI_KEY", "").strip()

try:
    ADMINS = [int(value.strip()) for value in os.getenv("ADMINS", "").split(",") if value.strip()]
except ValueError as exc:
    raise RuntimeError("ADMINS must be a comma-separated list of Telegram user IDs") from exc


def validate_config() -> None:
    """Fail early when required credentials are missing."""
    missing = [name for name, value in (("BOT_TOKEN", BOT_TOKEN), ("OPENWEATHER_KEY", OPENWEATHER_KEY), ("NEWSAPI_KEY", NEWSAPI_KEY)) if not value]
    if missing:
        raise RuntimeError("Missing required environment variables: " + ", ".join(missing))
