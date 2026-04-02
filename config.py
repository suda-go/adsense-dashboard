import os
import json
from pathlib import Path
from dotenv import load_dotenv

load_dotenv()

BASE_DIR = Path(__file__).parent

# App URL (set via env for deployed environments)
APP_URL = os.getenv("APP_URL", "http://localhost:8000").rstrip("/")
PORT = int(os.getenv("PORT", "8000"))

# Google OAuth
OAUTH_SCOPES = ["https://www.googleapis.com/auth/adsense.readonly"]
OAUTH_REDIRECT_URI = f"{APP_URL}/oauth/callback"
# Use /tmp for writable paths on serverless (Vercel filesystem is read-only)
_is_serverless = os.getenv("VERCEL", "") != ""
_writable_base = Path("/tmp") if _is_serverless else BASE_DIR

CREDENTIALS_DIR = _writable_base / "credentials"
CLIENT_SECRETS_PATH = CREDENTIALS_DIR / "client_secret.json"
TOKEN_PATH = CREDENTIALS_DIR / "token.json"

# Support client secrets from env var (for Render deployment)
GOOGLE_CLIENT_ID = os.getenv("GOOGLE_CLIENT_ID", "")
GOOGLE_CLIENT_SECRET = os.getenv("GOOGLE_CLIENT_SECRET", "")

def ensure_client_secrets():
    """Create client_secret.json from env vars if it doesn't exist."""
    if CLIENT_SECRETS_PATH.exists():
        return
    if not GOOGLE_CLIENT_ID or not GOOGLE_CLIENT_SECRET:
        return
    CREDENTIALS_DIR.mkdir(parents=True, exist_ok=True)
    secrets = {
        "web": {
            "client_id": GOOGLE_CLIENT_ID,
            "client_secret": GOOGLE_CLIENT_SECRET,
            "auth_uri": "https://accounts.google.com/o/oauth2/auth",
            "token_uri": "https://oauth2.googleapis.com/token",
            "redirect_uris": [OAUTH_REDIRECT_URI],
        }
    }
    with open(CLIENT_SECRETS_PATH, "w") as f:
        json.dump(secrets, f)

# AdSense
ADSENSE_ACCOUNT_ID = os.getenv("ADSENSE_ACCOUNT_ID", "")

# Anthropic
ANTHROPIC_API_KEY = os.getenv("ANTHROPIC_API_KEY", "")
ANTHROPIC_BASE_URL = os.getenv("ANTHROPIC_BASE_URL", "")

# Cache
DB_PATH = _writable_base / "adsense_cache.db"
REPORT_CACHE_TTL_SECONDS = 3600       # 1 hour
ANALYSIS_CACHE_TTL_SECONDS = 21600    # 6 hours
