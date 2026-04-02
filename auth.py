"""Google OAuth 2.0 flow for AdSense API access."""

import json
from google_auth_oauthlib.flow import Flow
from google.auth.transport.requests import Request
from google.oauth2.credentials import Credentials
from googleapiclient.discovery import build

import config


def _flow_from_secrets() -> Flow:
    """Create OAuth flow from client_secret.json."""
    return Flow.from_client_secrets_file(
        str(config.CLIENT_SECRETS_PATH),
        scopes=config.OAUTH_SCOPES,
        redirect_uri=config.OAUTH_REDIRECT_URI,
    )


def get_authorization_url() -> tuple[str, str]:
    """Generate Google OAuth authorization URL.

    Returns (auth_url, state) tuple.
    """
    flow = _flow_from_secrets()
    auth_url, state = flow.authorization_url(
        access_type="offline",
        prompt="consent",
        include_granted_scopes="true",
    )
    return auth_url, state


def exchange_code(code: str) -> Credentials:
    """Exchange authorization code for credentials and save token."""
    flow = _flow_from_secrets()
    flow.fetch_token(code=code)
    creds = flow.credentials

    # Persist token for future sessions
    config.TOKEN_PATH.parent.mkdir(parents=True, exist_ok=True)
    with open(config.TOKEN_PATH, "w") as f:
        json.dump({
            "token": creds.token,
            "refresh_token": creds.refresh_token,
            "token_uri": creds.token_uri,
            "client_id": creds.client_id,
            "client_secret": creds.client_secret,
            "scopes": list(creds.scopes or []),
        }, f)

    return creds


def load_credentials() -> Credentials | None:
    """Load saved credentials, refreshing if expired.

    Returns None if no valid credentials exist.
    """
    if not config.TOKEN_PATH.exists():
        return None

    try:
        with open(config.TOKEN_PATH) as f:
            token_data = json.load(f)
    except (json.JSONDecodeError, OSError):
        return None

    creds = Credentials(
        token=token_data.get("token"),
        refresh_token=token_data.get("refresh_token"),
        token_uri=token_data.get("token_uri", "https://oauth2.googleapis.com/token"),
        client_id=token_data.get("client_id"),
        client_secret=token_data.get("client_secret"),
        scopes=token_data.get("scopes"),
    )

    if creds.expired and creds.refresh_token:
        try:
            creds.refresh(Request())
            # Save refreshed token
            with open(config.TOKEN_PATH, "w") as f:
                json.dump({
                    "token": creds.token,
                    "refresh_token": creds.refresh_token,
                    "token_uri": creds.token_uri,
                    "client_id": creds.client_id,
                    "client_secret": creds.client_secret,
                    "scopes": list(creds.scopes or []),
                }, f)
        except Exception:
            return None

    if not creds.valid:
        return None

    return creds


def build_adsense_service(credentials: Credentials):
    """Build the AdSense Management API v2 service."""
    return build("adsense", "v2", credentials=credentials)
