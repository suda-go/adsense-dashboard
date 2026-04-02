"""Google OAuth 2.0 flow for AdSense API access.

Supports two storage modes for tokens:
1. File-based (TOKEN_PATH) - for local development
2. Env var (GOOGLE_REFRESH_TOKEN) - for serverless deployments (Vercel)
"""

import json
import os
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config

# In-memory token cache for serverless (survives within a single instance)
_token_cache: dict | None = None


def _flow_from_secrets() -> Flow:
    """Create OAuth flow from client_secret.json."""
    config.ensure_client_secrets()
    return Flow.from_client_secrets_file(
        str(config.CLIENT_SECRETS_PATH),
        scopes=config.OAUTH_SCOPES,
        redirect_uri=config.OAUTH_REDIRECT_URI,
    )


def get_authorization_url() -> tuple[str, str]:
    """Generate Google OAuth authorization URL."""
    flow = _flow_from_secrets()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return auth_url, state


def exchange_code(code: str) -> Credentials:
    """Exchange authorization code for credentials and save token."""
    global _token_cache
    flow = _flow_from_secrets()
    flow.fetch_token(code=code)
    creds = flow.credentials

    token_data = {
        "token": creds.token,
        "refresh_token": creds.refresh_token,
        "token_uri": creds.token_uri,
        "client_id": creds.client_id,
        "client_secret": creds.client_secret,
        "scopes": list(creds.scopes or []),
    }

    # Save to file (works locally)
    try:
        config.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
        with open(config.TOKEN_PATH, "w") as f:
            json.dump(token_data, f)
    except OSError:
        pass

    # Cache in memory (works on serverless)
    _token_cache = token_data

    return creds


def load_credentials() -> Credentials | None:
    """Load saved credentials from file, env var, or memory cache.

    Priority: memory cache > file > env var (GOOGLE_REFRESH_TOKEN)
    """
    global _token_cache
    token_data = None

    # 1. Memory cache
    if _token_cache:
        token_data = _token_cache

    # 2. File
    if not token_data and config.TOKEN_PATH.exists():
        try:
            with open(config.TOKEN_PATH) as f:
                token_data = json.load(f)
        except (json.JSONDecodeError, OSError):
            pass

    # 3. Env var (refresh token only - for serverless)
    if not token_data:
        refresh_token = os.getenv("GOOGLE_REFRESH_TOKEN", "")
        if refresh_token:
            token_data = {
                "token": None,
                "refresh_token": refresh_token,
                "token_uri": "https://oauth2.googleapis.com/token",
                "client_id": config.GOOGLE_CLIENT_ID,
                "client_secret": config.GOOGLE_CLIENT_SECRET,
            }

    if not token_data:
        return None

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id") or config.GOOGLE_CLIENT_ID,
        client_secret=token_data.get("client_secret") or config.GOOGLE_CLIENT_SECRET,
        scopes=token_data.get("scopes"),
    )

    # Refresh if expired
    if (not creds.valid or creds.expired) and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Update cache
            _token_cache = {
                "token": creds.token,
                "refresh_token": creds.refresh_token,
                "token_uri": creds.token_uri,
                "client_id": creds.client_id,
                "client_secret": creds.client_secret,
                "scopes": list(creds.scopes or []),
            }
            # Try to save to file
            try:
                with open(config.TOKEN_PATH, "w") as f:
                    json.dump(_token_cache, f)
            except OSError:
                pass
        except Exception:
            return None

    if not creds.valid:
        return None

    return creds


def build_adsense_service(credentials: Credentials):
    """Build the AdSense Management API v2 service."""
    return build("adsense", "v2", credentials=credentials)
