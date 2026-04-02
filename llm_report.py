"""Claude API integration for generating natural language insight reports."""

import json
import anthropic
import config
import db


def generate_insight_report(analysis_bundle: dict) -> str:
    """Generate a natural language insight report from analysis data using Claude.

    Returns the report text, or a fallback message if API is unavailable.
    """
    if not config.ANTHROPIC_API_KEY:
        return _fallback_report(analysis_bundle)

    prompt = f"""你是一位专业的广告收入数据分析师。请根据以下 Google AdSense 数据分析结果，撰写一份简洁的中文洞察报告（3-5段）。

要求：
1. 总体收入趋势和关键变化（具体数字）
2. 表现最好和最差的广告位分析
3. 地域（国家）维度的趋势变化
4. 检测到的异常波动及可能原因
5. 可执行的优化建议

注意：使用具体数字，避免空泛描述。如果某维度变化超过20%，重点分析原因。

数据：
{json.dumps(analysis_bundle, indent=2, ensure_ascii=False)}"""

    try:
        client_kwargs = {"api_key": config.ANTHROPIC_API_KEY}
        if config.ANTHROPIC_BASE_URL:
            client_kwargs["base_url"] = config.ANTHROPIC_BASE_URL
        client = anthropic.Anthropic(**client_kwargs)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=2000,
            messages=[{"role": "user", "content": prompt}],
        )
        return response.content[0].text
    except Exception as e:
        return f"LLM 报告生成失败: {e}\n\n" + _fallback_report(analysis_bundle)


def generate_insight_report_cached(analysis_bundle: dict) -> str:
    """Generate report with caching (6h TTL)."""
    cache_key = db.make_cache_key("llm_report", analysis_bundle)
    cached = db.get_cached_analysis(cache_key)
    if cached:
        return cached.get("report", "")

    report = generate_insight_report(analysis_bundle)
    db.set_cached_analysis(cache_key, {"report": report})
    return report


def _fallback_report(bundle: dict) -> str:
    """Generate a simple text report without LLM (rule-based fallback)."""
    comp = bundle.get("period_comparison", {})
    earnings = comp.get("ESTIMATED_EARNINGS", {})
    clicks = comp.get("CLICKS", {})
    rpm = comp.get("RPM", {})

    lines = ["## AdSense 数据分析摘要\n"]

    # Overall
    direction = "增长" if earnings.get("change_pct", 0) >= 0 else "下降"
    lines.append(
        f"**总收入**: ${earnings.get('current', 0):.2f}，"
        f"环比{direction} {abs(earnings.get('change_pct', 0)):.1f}%"
        f"（上期 ${earnings.get('previous', 0):.2f}）\n"
    )
    lines.append(
        f"**点击量**: {clicks.get('current', 0):,.0f}，"
        f"环比变化 {clicks.get('change_pct', 0):+.1f}%\n"
    )
    lines.append(
        f"**RPM**: ${rpm.get('current', 0):.2f}，"
        f"环比变化 {rpm.get('change_pct', 0):+.1f}%\n"
    )

    # Top contributors
    countries = bundle.get("country_contributors", [])
    if countries:
        top = countries[0]
        lines.append(
            f"\n**收入变化最大的国家**: {top['name']}，"
            f"变化 ${top['delta']:+.2f}（{top['change_pct']:+.1f}%）\n"
        )

    ad_units = bundle.get("ad_unit_contributors", [])
    if ad_units:
        top = ad_units[0]
        lines.append(
            f"**收入变化最大的广告位**: {top['name']}，"
            f"变化 ${top['delta']:+.2f}（{top['change_pct']:+.1f}%）\n"
        )

    # Anomalies
    anomalies = bundle.get("anomalies", [])
    if anomalies:
        lines.append(f"\n**检测到 {len(anomalies)} 个异常日**:")
        for a in anomalies[:3]:
            lines.append(
                f"  - {a['date']}: ${a['value']:.2f}（{a['direction']}，"
                f"偏离均值 {abs(a['deviation']):.1f} 个标准差）"
            )

    return "\n".join(lines)
