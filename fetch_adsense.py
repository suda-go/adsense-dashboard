#!/usr/bin/env python3
"""
AdSense API 数据拉取 + 深度分析
使用 Cloudflare Worker 代理绕过国内网络限制
"""
import requests
import json
import sys
import os
from datetime import datetime, timedelta
from collections import defaultdict

# ===== 配置 =====
CLIENT_ID = os.environ.get('ADSENSE_CLIENT_ID', '')
CLIENT_SECRET = os.environ.get('ADSENSE_CLIENT_SECRET', '')
PROXY = ''
DAYS = 30  # 拉取天数

# ===== 从 OAuth Playground 获取 Refresh Token =====
REFRESH_TOKEN = os.environ.get('ADSENSE_REFRESH_TOKEN', '')
if not REFRESH_TOKEN:
    print("⚠️  请设置环境变量 ADSENSE_REFRESH_TOKEN")
    print("步骤：")
    print("1. 打开 https://developers.google.com/oauthplayground")
    print("2. 右上角齿轮 → Use your own OAuth credentials → 填入同事的 Client ID/Secret")
    print("3. 找到 AdSense Management API v2 → 选 adsense.readonly → Authorize")
    print("4. 点 Exchange authorization code for tokens")
    print("5. 复制 refresh_token")
    print(f"\n然后运行: ADSENSE_REFRESH_TOKEN='你的token' python3 fetch_adsense.py")


def get_access_token():
    """用 refresh token 换 access token"""
    token_url = f'{PROXY}/https://oauth2.googleapis.com/token' if PROXY else 'https://oauth2.googleapis.com/token'
    resp = requests.post(token_url, data={
        'client_id': CLIENT_ID,
        'client_secret': CLIENT_SECRET,
        'refresh_token': REFRESH_TOKEN,
        'grant_type': 'refresh_token',
    }, timeout=15)
    resp.raise_for_status()
    return resp.json()['access_token']


def api_get(token, url, params=None):
    """调用 AdSense API"""
    full_url = f'{PROXY}{url}' if PROXY else url
    headers = {
        'Authorization': f'Bearer {token}',
        'Accept': 'application/json',
    }
    resp = requests.get(full_url, headers=headers, params=params, timeout=30)
    resp.raise_for_status()
    return resp.json()


def fetch_accounts(token):
    """获取账号列表"""
    data = api_get(token, 'https://adsense.googleapis.com/v2/accounts')
    return data.get('accounts', [])


def fetch_report(token, account, start_date, end_date, metrics, dimensions):
    """获取报告数据（GET + 查询参数）"""
    params = {
        'dateRange': 'CUSTOM',
        'startDate.year': start_date.year,
        'startDate.month': start_date.month,
        'startDate.day': start_date.day,
        'endDate.year': end_date.year,
        'endDate.month': end_date.month,
        'endDate.day': end_date.day,
    }
    params['metrics'] = metrics
    params['dimensions'] = dimensions

    url = f'https://adsense.googleapis.com/v2/{account}/reports:generate'
    return api_get(token, url, params)


def parse_daily(rows):
    """解析每日数据"""
    result = []
    for row in rows:
        cells = row.get('cells', [])
        result.append({
            'date': cells[0]['value'],
            'impressions': int(cells[1].get('value', 0)),
            'clicks': int(cells[2].get('value', 0)),
            'earnings': float(cells[3].get('value', 0)),
            'pageViews': int(cells[4].get('value', 0)),
        })
    return sorted(result, key=lambda x: x['date'])


def parse_country(rows):
    """解析国家数据"""
    result = []
    for row in rows:
        cells = row.get('cells', [])
        result.append({
            'code': cells[0]['value'],
            'earnings': float(cells[1].get('value', 0)),
            'pageViews': int(cells[2].get('value', 0)),
        })
    return sorted(result, key=lambda x: x['earnings'], reverse=True)


def parse_platform(rows):
    """解析平台数据"""
    result = []
    for row in rows:
        cells = row.get('cells', [])
        result.append({
            'platform': cells[0]['value'],
            'earnings': float(cells[1].get('value', 0)),
            'pageViews': int(cells[2].get('value', 0)),
        })
    return result


def analyze(daily, countries, platforms):
    """深度分析"""
    print("\n" + "="*70)
    print("📊 AdSense 数据深度分析报告")
    print("="*70)
    
    earnings = [d['earnings'] for d in daily]
    pvs = [d['pageViews'] for d in daily]
    clicks = [d['clicks'] for d in daily]
    n = len(daily)
    
    # 基础统计
    total_earnings = sum(earnings)
    avg_daily = total_earnings / n
    total_pv = sum(pvs)
    total_clicks = sum(clicks)
    total_impressions = sum(d['impressions'] for d in daily)
    avg_rpm = (total_earnings / total_pv * 1000) if total_pv > 0 else 0
    avg_ctr = (total_clicks / total_impressions * 100) if total_impressions > 0 else 0
    
    print(f"\n📅 周期: {daily[0]['date']} ~ {daily[-1]['date']} ({n} 天)")
    print(f"{'─'*40}")
    print(f"  💰 总收入:     ${total_earnings:.2f}")
    print(f"  📊 日均收入:   ${avg_daily:.2f}")
    print(f"  👀 总浏览量:   {total_pv:,}")
    print(f"  👆 总点击量:   {total_clicks:,}")
    print(f"  📈 平均 RPM:   ${avg_rpm:.2f}")
    print(f"  🖱️  平均 CTR:   {avg_ctr:.2f}%")
    
    # 最佳/最差
    sorted_daily = sorted(daily, key=lambda x: x['earnings'], reverse=True)
    print(f"\n🏆 最佳日: {sorted_daily[0]['date']} (${sorted_daily[0]['earnings']:.2f})")
    print(f"  💔 最差日: {sorted_daily[-1]['date']} (${sorted_daily[-1]['earnings']:.2f})")
    print(f"  📊 波动系数: {sorted_daily[0]['earnings']/max(sorted_daily[-1]['earnings'], 0.01):.1f}x")
    
    # 趋势分析（线性回归）
    mean_x = (n - 1) / 2
    mean_y = total_earnings / n
    num = sum((i - mean_x) * (e - mean_y) for i, e in enumerate(earnings))
    den = sum((i - mean_x) ** 2 for i in range(n))
    slope = num / den if den else 0
    
    total_change = slope * n
    pct_change = (total_change / mean_y * 100) if mean_y > 0 else 0
    
    trend = "📈 上升" if pct_change > 5 else "📉 下降" if pct_change < -5 else "➡️ 平稳"
    print(f"\n{trend} 趋势: {'+' if pct_change >= 0 else ''}{pct_change:.1f}% ({'+' if slope >= 0 else ''}${slope:.2f}/天)")
    
    # R²
    predicted = [mean_y + slope * i for i in range(n)]
    ss_res = sum((earnings[i] - predicted[i])**2 for i in range(n))
    ss_tot = sum((e - mean_y)**2 for e in earnings)
    r2 = 1 - ss_res / ss_tot if ss_tot > 0 else 0
    print(f"  趋势拟合度 R² = {r2:.3f} ({'稳定' if r2 > 0.7 else '一般' if r2 > 0.3 else '不明显'})")
    
    # 波动率
    import math
    std = math.sqrt(sum((e - mean_y)**2 for e in earnings) / n)
    cv = (std / mean_y * 100) if mean_y > 0 else 0
    print(f"  波动率 CV = {cv:.1f}% ({'高波动' if cv > 30 else '中等' if cv > 15 else '低波动'})")
    
    # 前半 vs 后半
    mid = n // 2
    first_avg = sum(earnings[:mid]) / mid
    second_avg = sum(earnings[mid:]) / (n - mid)
    period_chg = (second_avg - first_avg) / first_avg * 100 if first_avg > 0 else 0
    print(f"  前半 vs 后半: {'+' if period_chg >= 0 else ''}{period_chg:.1f}%")
    
    # 预测
    pred7 = sum(max(0, mean_y + slope * (n + i)) for i in range(7))
    print(f"\n🔮 未来 7 天预测: ${pred7:.2f} (线性外推)")
    
    # 异常检测
    print(f"\n🚨 异常检测:")
    anomalies = [(d, (d['earnings'] - mean_y) / std) for d in daily if std > 0 and abs(d['earnings'] - mean_y) > std * 1.5]
    if anomalies:
        for d, z in anomalies:
            arrow = "🟢" if z > 0 else "🔴"
            print(f"  {arrow} {d['date']}: ${d['earnings']:.2f} (z={z:+.1f}σ)")
    else:
        print(f"  ✅ 未检测到显著异常 (±1.5σ 范围内)")
    
    low_days = [d for d in daily if d['earnings'] < mean_y * 0.2]
    if low_days:
        print(f"  ⚠️  {len(low_days)} 天收入低于均值 20%: {', '.join(d['date'][5:] for d in low_days)}")
    
    # 星期分析
    print(f"\n📅 星期分析:")
    dow_names = ['周日','周一','周二','周三','周四','周五','周六']
    dow_data = defaultdict(lambda: {'earnings': 0, 'count': 0})
    for d in daily:
        dow = datetime.strptime(d['date'], '%Y-%m-%d').weekday()
        dow = (dow + 1) % 7  # Convert to 0=Sunday
        dow_data[dow]['earnings'] += d['earnings']
        dow_data[dow]['count'] += 1
    
    dow_avgs = []
    for i in range(7):
        d = dow_data[i]
        avg = d['earnings'] / max(d['count'], 1)
        dow_avgs.append((dow_names[i], avg, d['count']))
    
    max_dow = max(dow_avgs, key=lambda x: x[1])
    min_dow = min(dow_avgs, key=lambda x: x[1])
    
    for name, avg, count in dow_avgs:
        bar = '█' * int(avg / max(x[1] for x in dow_avgs) * 20) if max(x[1] for x in dow_avgs) > 0 else ''
        print(f"  {name} {bar} ${avg:.2f} ({count}天)")
    print(f"  最佳: {max_dow[0]} | 最差: {min_dow[0]}")
    
    # 周度趋势
    print(f"\n📅 周度趋势:")
    weeks = []
    current_week = []
    for d in daily:
        dt = datetime.strptime(d['date'], '%Y-%m-%d')
        current_week.append(d)
        if dt.weekday() == 6 or d == daily[-1]:  # Sunday or last day
            if current_week:
                we = sum(x['earnings'] for x in current_week)
                wpv = sum(x['pageViews'] for x in current_week)
                weeks.append({
                    'start': current_week[0]['date'],
                    'end': current_week[-1]['date'],
                    'earnings': we,
                    'avg_daily': we / len(current_week),
                    'days': len(current_week),
                })
                current_week = []
    
    for i, w in enumerate(weeks):
        wow = ''
        if i > 0:
            chg = (w['avg_daily'] - weeks[i-1]['avg_daily']) / max(weeks[i-1]['avg_daily'], 0.01) * 100
            wow = f" {'🟢' if chg >= 0 else '🔴'}{chg:+.1f}%"
        print(f"  {w['start'][5:]}~{w['end'][5:]} ({w['days']}天): ${w['earnings']:.2f}{wow}")
    
    # 国家分析
    print(f"\n🌍 国家/地区 TOP 10:")
    total_country_earnings = sum(c['earnings'] for c in countries)
    for i, c in enumerate(countries[:10]):
        pct = (c['earnings'] / total_country_earnings * 100) if total_country_earnings > 0 else 0
        rpm = (c['earnings'] / max(c['pageViews'], 1) * 1000)
        print(f"  {i+1:2d}. {c['code']:4s} ${c['earnings']:8.2f} ({pct:5.1f}%) PV:{c['pageViews']:>10,} RPM:${rpm:.2f}")
    
    # 平台分析
    if platforms:
        print(f"\n📱 平台分析:")
        for p in platforms:
            print(f"  {p['platform']:10s} ${p['earnings']:8.2f} PV:{p['pageViews']:>10,}")
    
    # 收入分布
    print(f"\n📊 收入分布:")
    min_e, max_e = min(earnings), max(earnings)
    bucket_count = min(10, n)
    bucket_size = (max_e - min_e) / bucket_count or 1
    buckets = [0] * bucket_count
    for e in earnings:
        idx = min(int((e - min_e) / bucket_size), bucket_count - 1)
        buckets[idx] += 1
    
    median_e = sorted(earnings)[n // 2]
    for i, count in enumerate(buckets):
        low = min_e + i * bucket_size
        high = min_e + (i+1) * bucket_size
        bar = '█' * (count * 2)
        marker = ' ← 均值' if mean_y >= low and mean_y < high else ''
        print(f"  ${low:6.2f}-${high:6.2f} {bar} {count}天{marker}")
    print(f"  均值: ${mean_y:.2f} | 中位数: ${median_e:.2f}")
    
    return {
        'daily': daily,
        'countries': countries,
        'platforms': platforms,
        'summary': {
            'total': total_earnings,
            'avgDaily': avg_daily,
            'avgRPM': avg_rpm,
            'avgCTR': avg_ctr,
            'trend': pct_change,
            'r2': r2,
            'cv': cv,
        }
    }


def main():
    if not REFRESH_TOKEN:
        sys.exit(1)
    
    print("🔄 正在获取 access token...")
    token = get_access_token()
    print("✅ Token 获取成功")
    
    print("📊 正在获取账号列表...")
    accounts = fetch_accounts(token)
    if not accounts:
        print("❌ 没有可用的账号")
        sys.exit(1)
    
    account_name = accounts[0]['name']
    print(f"✅ 账号: {account_name}")
    
    end_date = datetime.now()
    start_date = end_date - timedelta(days=DAYS)
    
    print(f"📈 正在拉取 {start_date.strftime('%Y-%m-%d')} ~ {end_date.strftime('%Y-%m-%d')} 数据...")
    
    # Daily report
    daily_data = fetch_report(token, account_name, start_date, end_date,
        ['IMPRESSIONS', 'CLICKS', 'ESTIMATED_EARNINGS', 'PAGE_VIEWS'], ['DATE'])
    daily = parse_daily(daily_data.get('rows', []))
    print(f"  ✅ 每日数据: {len(daily)} 天")
    
    # Country report
    try:
        country_data = fetch_report(token, account_name, start_date, end_date,
            ['ESTIMATED_EARNINGS', 'PAGE_VIEWS'], ['COUNTRY_CODE'])
        countries = parse_country(country_data.get('rows', []))
        print(f"  ✅ 国家数据: {len(countries)} 个")
    except Exception as e:
        print(f"  ⚠️  国家数据获取失败: {e}")
        countries = []
    
    # Platform report
    try:
        plat_data = fetch_report(token, account_name, start_date, end_date,
            ['ESTIMATED_EARNINGS', 'PAGE_VIEWS'], ['PLATFORM_CODE'])
        platforms = parse_platform(plat_data.get('rows', []))
        print(f"  ✅ 平台数据: {len(platforms)} 个")
    except Exception as e:
        print(f"  ⚠️  平台数据获取失败: {e}")
        platforms = []
    
    # Analyze
    result = analyze(daily, countries, platforms)
    
    # Save
    output_file = 'adsense_data.json'
    with open(output_file, 'w', encoding='utf-8') as f:
        json.dump(result, f, ensure_ascii=False, indent=2)
    print(f"\n💾 数据已保存到 {output_file}")


if __name__ == '__main__':
    main()
