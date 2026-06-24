"""Application configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()


class Config:
    """Bot configuration pulled from the environment."""

    PORT = int(os.environ.get("PORT", 3978))

    # Microsoft Bot Framework
    APP_ID = os.environ.get("MICROSOFT_APP_ID", "")
    APP_PASSWORD = os.environ.get("MICROSOFT_APP_PASSWORD", "")
    APP_TYPE = os.environ.get("MICROSOFT_APP_TYPE", "MultiTenant")
    APP_TENANTID = os.environ.get("MICROSOFT_APP_TENANTID", "")

    # Google Gemini
    GEMINI_API_KEY = os.environ.get("GEMINI_API_KEY", "")
    GEMINI_MODEL = os.environ.get("GEMINI_MODEL", "gemini-2.5-flash")

    # Number of prior turns to keep for conversational context.
    HISTORY_LIMIT = 10

    SYSTEM_PROMPT = (
        "You are a helpful assistant for CivicSpace, a Thai NGO focused on "
        "civic engagement and public space. Reply in Thai language."
    )
