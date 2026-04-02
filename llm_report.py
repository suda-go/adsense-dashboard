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

    prompt = f"""你是一位资深的广告变现数据分析师，擅长从多维数据中发现因果关系。请根据以下 Google AdSense 全维度数据，撰写一份深度中文分析报告。

## 分析框架

### 1. 收入涨跌归因（必须回答"为什么涨/跌"）
- 总收入变化的具体数字和百分比
- **逐一交叉分析**以下维度，找出哪个维度是涨跌的主因：
  - 广告位（Ad Unit）：哪个广告位贡献了最大涨幅/跌幅？
  - 国家/地区：哪些国家的流量或收入变化最大？是否与季节/节假日相关？
  - 广告格式（Format）：In-page / Anchor / Vignette 各自表现如何？格式切换是否影响了收入？
  - 设备平台（Platform）：Desktop vs Mobile vs Tablet 的收入和 CTR 差异
  - 域名（Domain）：哪个域名贡献最多？是否有某个域名异常？
  - 广告尺寸（Ad Size）：哪种尺寸 RPM 最高？尺寸分布是否合理？
  - 买方网络（Buyer Network）：哪些广告网络出价变化大？是否有网络退出/新增？
  - 自定义渠道（Custom Channel）：渠道间表现差异及原因

### 2. 关键指标联动分析
- RPM 变化原因：是 CPC 变了还是 CTR 变了？
- CTR 变化原因：是流量质量变了还是广告位置变了？
- CPC 变化原因：是买方出价变了还是流量地域结构变了？

### 3. 异常检测与风险
- 任何偏离均值超过2个标准差的日期，分析可能原因
- 是否存在流量作弊迹象（CTR异常高/低）
- 收入与流量不匹配的情况

### 4. 可执行优化建议（按优先级排序）
- 基于数据给出3-5条具体可操作的建议
- 每条建议说明预期收益

## 格式要求
- 使用 Markdown 格式，带标题和小标题
- 所有结论必须附带具体数字
- 变化超过20%的维度要重点标注和分析
- 报告应为5-8段，覆盖所有维度

数据：
{json.dumps(analysis_bundle, indent=2, ensure_ascii=False)}"""

    try:
        client_kwargs = {"api_key": config.ANTHROPIC_API_KEY}
        if config.ANTHROPIC_BASE_URL:
            client_kwargs["base_url"] = config.ANTHROPIC_BASE_URL
        client = anthropic.Anthropic(**client_kwargs)
        response = client.messages.create(
            model="claude-sonnet-4-20250514",
            max_tokens=4000,
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

    # Domain
    domains = bundle.get("domain_contributors", [])
    if domains:
        top = domains[0]
        lines.append(
            f"\n**收入变化最大的域名**: {top['name']}，"
            f"变化 ${top['delta']:+.2f}（{top['change_pct']:+.1f}%），占比 {top['share_pct']:.1f}%\n"
        )

    # Ad Size
    ad_sizes = bundle.get("ad_size_contributors", [])
    if ad_sizes:
        top = ad_sizes[0]
        lines.append(
            f"**收入变化最大的广告尺寸**: {top['name']}，"
            f"变化 ${top['delta']:+.2f}（{top['change_pct']:+.1f}%）\n"
        )

    # Buyer Network
    buyers = bundle.get("buyer_network_contributors", [])
    if buyers:
        top = buyers[0]
        lines.append(
            f"**收入变化最大的买方网络**: {top['name']}，"
            f"变化 ${top['delta']:+.2f}（{top['change_pct']:+.1f}%）\n"
        )

    # Custom Channel
    channels = bundle.get("custom_channel_contributors", [])
    if channels:
        top = channels[0]
        lines.append(
            f"**收入变化最大的渠道**: {top['name']}，"
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
