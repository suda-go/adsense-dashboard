"""FastAPI application for AdSense Analytics Dashboard."""

import os
from datetime import date, timedelta
from fastapi import FastAPI, Query, HTTPException
from fastapi.responses import FileResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles

import config
import db
import auth
import adsense_client
import analysis
import llm_report

app = FastAPI(title="AdSense Dashboard")

# Serve static files
app.mount("/static", StaticFiles(directory=str(config.BASE_DIR / "static")), name="static")


@app.on_event("startup")
def startup():
    config.ensure_client_secrets()
    db.init_db()


# --- Pages ---

@app.get("/")
def index():
    return FileResponse(str(config.BASE_DIR / "static" / "index.html"))


# --- Auth ---

@app.get("/api/auth/status")
def auth_status():
    """Check if user is authenticated with Google AdSense."""
    creds = auth.load_credentials()
    if not creds:
        return {"authenticated": False, "account_id": None}

    # Try to discover account ID if not configured
    account_id = config.ADSENSE_ACCOUNT_ID
    if not account_id:
        try:
            service = auth.build_adsense_service(creds)
            accounts = adsense_client.list_accounts(service)
            if accounts:
                account_id = accounts[0]["name"]
        except Exception:
            pass

    return {"authenticated": True, "account_id": account_id}


@app.get("/api/auth/debug")
def auth_debug():
    """Debug: show OAuth config (remove after testing)."""
    return {
        "APP_URL": config.APP_URL,
        "OAUTH_REDIRECT_URI": config.OAUTH_REDIRECT_URI,
        "CLIENT_ID_PREFIX": config.GOOGLE_CLIENT_ID[:20] + "..." if config.GOOGLE_CLIENT_ID else "",
        "HAS_CLIENT_SECRET": bool(config.GOOGLE_CLIENT_SECRET),
        "CLIENT_SECRETS_PATH": str(config.CLIENT_SECRETS_PATH),
        "SECRETS_FILE_EXISTS": config.CLIENT_SECRETS_PATH.exists(),
        "VERCEL_ENV": os.getenv("VERCEL", ""),
    }


@app.get("/api/auth/login")
def auth_login():
    """Start Google OAuth flow."""
    if not config.GOOGLE_CLIENT_ID or not config.GOOGLE_CLIENT_SECRET:
        raise HTTPException(
            status_code=400,
            detail="请先配置 GOOGLE_CLIENT_ID 和 GOOGLE_CLIENT_SECRET 环境变量",
        )
    auth_url, state = auth.get_authorization_url()
    return {"auth_url": auth_url}


@app.get("/oauth/callback")
def oauth_callback(code: str, state: str = ""):
    """Handle Google OAuth callback."""
    try:
        creds = auth.exchange_code(code)
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"OAuth 认证失败: {e}")
    # On serverless, redirect with refresh_token hint so user can save it as env var
    refresh_token = creds.refresh_token or ""
    if refresh_token:
        return RedirectResponse(url=f"/?auth=ok&refresh_token={refresh_token}")
    return RedirectResponse(url="/")


# --- Accounts ---

@app.get("/api/accounts")
def list_accounts():
    """List available AdSense accounts."""
    creds = auth.load_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="未认证")
    service = auth.build_adsense_service(creds)
    return adsense_client.list_accounts(service)


# --- Dashboard ---

def _get_account_id(creds) -> str:
    """Resolve AdSense account ID."""
    if config.ADSENSE_ACCOUNT_ID:
        return config.ADSENSE_ACCOUNT_ID
    service = auth.build_adsense_service(creds)
    accounts = adsense_client.list_accounts(service)
    if not accounts:
        raise HTTPException(status_code=404, detail="未找到 AdSense 账户")
    return accounts[0]["name"]


def _fetch_with_cache(service, account_id, start, end, fetch_fn, cache_tag):
    """Fetch data with caching."""
    key = db.make_cache_key(cache_tag, account_id, start, end)
    cached = db.get_cached_report(key)
    if cached is not None:
        return cached
    data = fetch_fn(service, account_id, start, end)
    db.set_cached_report(key, data)
    return data


@app.get("/api/dashboard")
def dashboard(
    start: str = Query(default="", description="Start date YYYY-MM-DD"),
    end: str = Query(default="", description="End date YYYY-MM-DD"),
    compare: bool = Query(default=True, description="Include period comparison"),
):
    """Main dashboard endpoint - returns all data for the dashboard."""
    import traceback
    try:
        return _dashboard_inner(start, end, compare)
    except HTTPException:
        raise
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"{type(e).__name__}: {e}\n{traceback.format_exc()}")


def _dashboard_inner(start, end, compare):
    creds = auth.load_credentials()
    if not creds:
        raise HTTPException(status_code=401, detail="未认证，请先连接 Google AdSense")

    service = auth.build_adsense_service(creds)
    account_id = _get_account_id(creds)

    # Default: last 30 days
    today = date.today()
    end_date = date.fromisoformat(end) if end else today - timedelta(days=1)
    start_date = date.fromisoformat(start) if start else end_date - timedelta(days=29)
    period_days = (end_date - start_date).days + 1

    start_str = start_date.isoformat()
    end_str = end_date.isoformat()

    # Fetch current period data
    daily = _fetch_with_cache(
        service, account_id, start_str, end_str,
        adsense_client.fetch_daily_revenue, "daily",
    )
    by_country = _fetch_with_cache(
        service, account_id, start_str, end_str,
        adsense_client.fetch_by_country, "country",
    )
    by_ad_unit = _fetch_with_cache(
        service, account_id, start_str, end_str,
        adsense_client.fetch_by_ad_unit, "ad_unit",
    )

    result = {
        "period": {"start": start_str, "end": end_str, "days": period_days},
        "daily": daily,
        "by_country": by_country,
        "by_ad_unit": by_ad_unit,
    }

    # Comparison period (same length, immediately before)
    if compare:
        prev_end = start_date - timedelta(days=1)
        prev_start = prev_end - timedelta(days=period_days - 1)
        prev_start_str = prev_start.isoformat()
        prev_end_str = prev_end.isoformat()

        prev_daily = _fetch_with_cache(
            service, account_id, prev_start_str, prev_end_str,
            adsense_client.fetch_daily_revenue, "daily",
        )
        prev_by_country = _fetch_with_cache(
            service, account_id, prev_start_str, prev_end_str,
            adsense_client.fetch_by_country, "country",
        )
        prev_by_ad_unit = _fetch_with_cache(
            service, account_id, prev_start_str, prev_end_str,
            adsense_client.fetch_by_ad_unit, "ad_unit",
        )

        result["previous_period"] = {
            "start": prev_start_str,
            "end": prev_end_str,
            "daily": prev_daily,
        }

        # Run analysis
        bundle = analysis.build_analysis_bundle(
            daily, prev_daily,
            by_country, prev_by_country,
            by_ad_unit, prev_by_ad_unit,
        )
        result["analysis"] = bundle

        # LLM report
        try:
            report = llm_report.generate_insight_report_cached(bundle)
        except Exception as e:
            report = f"报告生成出错: {e}"
        result["llm_report"] = report

    return result


# --- Entry point ---

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("main:app", host="0.0.0.0", port=config.PORT, reload=True)
