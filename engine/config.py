"""Configuration loaded from environment variables."""

import os

from dotenv import load_dotenv

load_dotenv()

# Server
HOST = os.getenv("HOST", "0.0.0.0")
PORT = int(os.getenv("PORT", "8900"))

# API Keys
FIREFLIES_API_KEY = os.getenv("FIREFLIES_API_KEY", "")
LINEAR_API_KEY = os.getenv("LINEAR_API_KEY", "")
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY", "")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY", "")

# CORS — panel origin for Zoom iframe
PANEL_ORIGIN = os.getenv("PANEL_ORIGIN", "http://localhost:5173")

# Linear defaults
LINEAR_DEFAULT_TEAM_ID = os.getenv("LINEAR_DEFAULT_TEAM_ID", "9a9d11aa-c8a5-4dc5-855c-c1da260db615")

# Feature flags
DEBUG = os.getenv("DEBUG", "false").lower() == "true"
