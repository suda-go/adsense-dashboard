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


def analyze_ad_formats(current: list[dict], previous: list[dict] = None) -> list[dict]:
    """Analyze ad format performance with period comparison."""
    def _group(data, key="AD_FORMAT_NAME"):
        groups = defaultdict(lambda: defaultdict(float))
        for r in data:
            name = r.get(key, "Unknown")
            for m in ["ESTIMATED_EARNINGS", "PAGE_VIEWS", "CLICKS", "IMPRESSIONS"]:
                groups[name][m] += float(r.get(m, 0))
            # Weighted averages for ratio metrics
            groups[name]["_count"] += 1
        return groups

    cur = _group(current)
    prev = _group(previous) if previous else {}
    total_revenue = sum(g["ESTIMATED_EARNINGS"] for g in cur.values())

    result = []
    for name, metrics in cur.items():
        rev = metrics["ESTIMATED_EARNINGS"]
        clicks = metrics["CLICKS"]
        views = metrics["PAGE_VIEWS"]
        imps = metrics["IMPRESSIONS"]
        ctr = (clicks / views * 100) if views else 0
        cpc = (rev / clicks) if clicks else 0
        rpm = (rev / views * 1000) if views else 0
        share = (rev / total_revenue * 100) if total_revenue else 0

        entry = {
            "name": name,
            "revenue": round(rev, 4),
            "page_views": round(views),
            "clicks": round(clicks),
            "impressions": round(imps),
            "ctr": round(ctr, 4),
            "cpc": round(cpc, 4),
            "rpm": round(rpm, 4),
            "share_pct": round(share, 2),
        }

        if prev and name in prev:
            prev_rev = prev[name]["ESTIMATED_EARNINGS"]
            prev_clicks = prev[name]["CLICKS"]
            prev_views = prev[name]["PAGE_VIEWS"]
            delta = rev - prev_rev
            pct = (delta / prev_rev * 100) if prev_rev else 0
            prev_ctr = (prev_clicks / prev_views * 100) if prev_views else 0
            prev_cpc = (prev_rev / prev_clicks) if prev_clicks else 0
            prev_rpm = (prev_rev / prev_views * 1000) if prev_views else 0
            entry["prev_revenue"] = round(prev_rev, 4)
            entry["revenue_change_pct"] = round(pct, 2)
            entry["revenue_delta"] = round(delta, 4)
            entry["prev_ctr"] = round(prev_ctr, 4)
            entry["ctr_change"] = round(ctr - prev_ctr, 4)
            entry["prev_cpc"] = round(prev_cpc, 4)
            entry["cpc_change_pct"] = round(((cpc - prev_cpc) / prev_cpc * 100) if prev_cpc else 0, 2)
            entry["prev_rpm"] = round(prev_rpm, 4)
            entry["rpm_change_pct"] = round(((rpm - prev_rpm) / prev_rpm * 100) if prev_rpm else 0, 2)

        result.append(entry)

    result.sort(key=lambda x: x["revenue"], reverse=True)
    return result


def build_analysis_bundle(
    daily_current: list[dict],
    daily_previous: list[dict],
    by_country_current: list[dict],
    by_country_previous: list[dict],
    by_ad_unit_current: list[dict],
    by_ad_unit_previous: list[dict],
    by_platform: list[dict] = None,
    by_ad_format: list[dict] = None,
    prev_by_ad_format: list[dict] = None,
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
        bundle["ad_format_analysis"] = analyze_ad_formats(by_ad_format, prev_by_ad_format)

    return bundle
