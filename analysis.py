"""Rule-based statistical analysis engine for AdSense data."""

from collections import defaultdict
import statistics


def compare_periods(current: list[dict], previous: list[dict]) -> dict:
    """Compare aggregated metrics between two periods."""
    def _sum_metric(data, key):
        return sum(float(r.get(key, 0)) for r in data)

    metrics = ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "CLICKS", "IMPRESSIONS"]
    result = {}

    for m in metrics:
        cur_val = _sum_metric(current, m)
        prev_val = _sum_metric(previous, m)
        delta = cur_val - prev_val
        pct = (delta / prev_val * 100) if prev_val else 0.0
        result[m] = {
            "current": round(cur_val, 4),
            "previous": round(prev_val, 4),
            "delta": round(delta, 4),
            "change_pct": round(pct, 2),
        }

    # RPM
    cur_pv = _sum_metric(current, "PAGE_VIEWS")
    prev_pv = _sum_metric(previous, "PAGE_VIEWS")
    cur_rpm = (_sum_metric(current, "ESTIMATED_EARNINGS") / cur_pv * 1000) if cur_pv else 0
    prev_rpm = (_sum_metric(previous, "ESTIMATED_EARNINGS") / prev_pv * 1000) if prev_pv else 0
    rpm_delta = cur_rpm - prev_rpm
    rpm_pct = (rpm_delta / prev_rpm * 100) if prev_rpm else 0
    result["RPM"] = {
        "current": round(cur_rpm, 4),
        "previous": round(prev_rpm, 4),
        "delta": round(rpm_delta, 4),
        "change_pct": round(rpm_pct, 2),
    }

    # CTR
    cur_clicks = _sum_metric(current, "CLICKS")
    prev_clicks = _sum_metric(previous, "CLICKS")
    cur_ctr = (cur_clicks / cur_pv * 100) if cur_pv else 0
    prev_ctr = (prev_clicks / prev_pv * 100) if prev_pv else 0
    ctr_delta = cur_ctr - prev_ctr
    ctr_pct = (ctr_delta / prev_ctr * 100) if prev_ctr else 0
    result["CTR"] = {
        "current": round(cur_ctr, 4),
        "previous": round(prev_ctr, 4),
        "delta": round(ctr_delta, 4),
        "change_pct": round(ctr_pct, 2),
    }

    # CPC
    cur_cpc = (_sum_metric(current, "ESTIMATED_EARNINGS") / cur_clicks) if cur_clicks else 0
    prev_cpc = (_sum_metric(previous, "ESTIMATED_EARNINGS") / prev_clicks) if prev_clicks else 0
    cpc_delta = cur_cpc - prev_cpc
    cpc_pct = (cpc_delta / prev_cpc * 100) if prev_cpc else 0
    result["CPC"] = {
        "current": round(cur_cpc, 4),
        "previous": round(prev_cpc, 4),
        "delta": round(cpc_delta, 4),
        "change_pct": round(cpc_pct, 2),
    }

    return result


def rank_contributors(
    current_data: list[dict],
    previous_data: list[dict],
    group_key: str,
    metric: str = "ESTIMATED_EARNINGS",
    top_n: int = 10,
) -> list[dict]:
    """Rank groups by their contribution to the overall metric change."""
    def _group_sum(data, key, metric_key):
        groups = defaultdict(float)
        for r in data:
            groups[r.get(key, "unknown")] += float(r.get(metric_key, 0))
        return groups

    cur_groups = _group_sum(current_data, group_key, metric)
    prev_groups = _group_sum(previous_data, group_key, metric)

    all_keys = set(cur_groups.keys()) | set(prev_groups.keys())
    total_cur = sum(cur_groups.values())

    contributors = []
    for k in all_keys:
        cur_val = cur_groups.get(k, 0)
        prev_val = prev_groups.get(k, 0)
        delta = cur_val - prev_val
        pct_change = (delta / prev_val * 100) if prev_val else (100.0 if cur_val > 0 else 0.0)
        share = (cur_val / total_cur * 100) if total_cur else 0
        contributors.append({
            "name": k,
            "current": round(cur_val, 4),
            "previous": round(prev_val, 4),
            "delta": round(delta, 4),
            "change_pct": round(pct_change, 2),
            "share_pct": round(share, 2),
        })

    contributors.sort(key=lambda x: abs(x["delta"]), reverse=True)
    return contributors[:top_n]


def detect_anomalies(
    daily_data: list[dict],
    metric: str = "ESTIMATED_EARNINGS",
    window: int = 7,
    threshold: float = 2.0,
) -> list[dict]:
    """Detect days with anomalous metric values."""
    values = [(r.get("DATE", ""), float(r.get(metric, 0))) for r in daily_data]
    if len(values) < window + 1:
        return []

    anomalies = []
    for i in range(window, len(values)):
        window_vals = [v[1] for v in values[i - window : i]]
        mean = statistics.mean(window_vals)
        stdev = statistics.stdev(window_vals) if len(window_vals) > 1 else 0

        if stdev == 0:
            continue

        current_val = values[i][1]
        deviation = (current_val - mean) / stdev

        if abs(deviation) >= threshold:
            anomalies.append({
                "date": values[i][0],
                "value": round(current_val, 4),
                "rolling_mean": round(mean, 4),
                "rolling_stdev": round(stdev, 4),
                "deviation": round(deviation, 2),
                "direction": "spike" if deviation > 0 else "drop",
            })

    return anomalies


def build_analysis_bundle(
    daily_current: list[dict],
    daily_previous: list[dict],
    by_country_current: list[dict],
    by_country_previous: list[dict],
    by_ad_unit_current: list[dict],
    by_ad_unit_previous: list[dict],
    by_platform: list[dict] = None,
    by_ad_format: list[dict] = None,
) -> dict:
    """Build complete analysis bundle from all data sources."""
    bundle = {
        "period_comparison": compare_periods(daily_current, daily_previous),
        "country_contributors": rank_contributors(
            by_country_current, by_country_previous, "COUNTRY_CODE"
        ),
        "ad_unit_contributors": rank_contributors(
            by_ad_unit_current, by_ad_unit_previous, "AD_UNIT_NAME"
        ),
        "anomalies": detect_anomalies(daily_current),
        "summary": {
            "current_days": len(daily_current),
            "previous_days": len(daily_previous),
            "total_countries": len(set(r.get("COUNTRY_CODE", "") for r in by_country_current)),
            "total_ad_units": len(set(r.get("AD_UNIT_NAME", "") for r in by_ad_unit_current)),
        },
    }

    if by_platform:
        bundle["by_platform"] = by_platform
    if by_ad_format:
        bundle["by_ad_format"] = by_ad_format

    return bundle
