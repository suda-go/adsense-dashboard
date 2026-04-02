"""AdSense Reporting API v2 wrapper."""

from datetime import date


def _parse_date(d: str | date) -> dict:
    """Convert date to API format dict {year, month, day}."""
    if isinstance(d, str):
        d = date.fromisoformat(d)
    return {"year": d.year, "month": d.month, "day": d.day}


def _parse_response(response: dict) -> list[dict]:
    """Parse AdSense API response into list of dicts.

    API returns: {headers: [{name, type}], rows: [{cells: [{value}]}]}
    We zip headers with cell values.
    """
    headers = [h["name"] for h in response.get("headers", [])]
    header_types = {h["name"]: h.get("type", "") for h in response.get("headers", [])}
    rows = []

    for row in response.get("rows", []):
        cells = row.get("cells", [])
        record = {}
        for i, header in enumerate(headers):
            val = cells[i]["value"] if i < len(cells) else ""
            # Convert numeric types
            htype = header_types.get(header, "")
            if htype in ("METRIC_CURRENCY", "METRIC_DECIMAL", "METRIC_RATIO"):
                try:
                    val = float(val)
                except (ValueError, TypeError):
                    val = 0.0
            elif htype == "METRIC_TALLY":
                try:
                    val = int(val)
                except (ValueError, TypeError):
                    val = 0
            record[header] = val
        rows.append(record)

    return rows


def fetch_report(
    service,
    account_id: str,
    start_date: str | date,
    end_date: str | date,
    dimensions: list[str],
    metrics: list[str],
) -> list[dict]:
    """Fetch an AdSense report with given dimensions and metrics."""
    start = _parse_date(start_date)
    end = _parse_date(end_date)

    response = (
        service.accounts()
        .reports()
        .generate(
            account=account_id,
            dateRange="CUSTOM",
            startDate_year=start["year"],
            startDate_month=start["month"],
            startDate_day=start["day"],
            endDate_year=end["year"],
            endDate_month=end["month"],
            endDate_day=end["day"],
            dimensions=dimensions,
            metrics=metrics,
        )
        .execute()
    )

    return _parse_response(response)


# --- Convenience wrappers ---

_DEFAULT_METRICS = [
    "ESTIMATED_EARNINGS",
    "PAGE_VIEWS",
    "CLICKS",
    "IMPRESSIONS",
    "PAGE_VIEWS_RPM",
]


def fetch_daily_revenue(service, account_id: str, start: str, end: str) -> list[dict]:
    """Fetch daily revenue breakdown."""
    return fetch_report(service, account_id, start, end, ["DATE"], _DEFAULT_METRICS)


def fetch_by_country(service, account_id: str, start: str, end: str) -> list[dict]:
    """Fetch revenue breakdown by country."""
    return fetch_report(
        service, account_id, start, end,
        ["COUNTRY_CODE"],
        ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "CLICKS", "IMPRESSIONS"],
    )


def fetch_by_ad_unit(service, account_id: str, start: str, end: str) -> list[dict]:
    """Fetch revenue breakdown by ad unit."""
    return fetch_report(
        service, account_id, start, end,
        ["AD_UNIT_NAME"],
        ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "CLICKS", "IMPRESSIONS", "PAGE_VIEWS_RPM"],
    )


def list_accounts(service) -> list[dict]:
    """List all AdSense accounts accessible to the authenticated user."""
    response = service.accounts().list().execute()
    accounts = []
    for acc in response.get("accounts", []):
        accounts.append({
            "name": acc.get("name", ""),
            "displayName": acc.get("displayName", ""),
            "reportingTimeZone": acc.get("reportingTimeZone", ""),
        })
    return accounts
