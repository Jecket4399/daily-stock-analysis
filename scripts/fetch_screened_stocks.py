#!/usr/bin/env python3
"""
从 stock-screener 仓库拉取每日全市场筛选结果，提取 Top N 动量突破股票。
作为 daily_stock_analysis 的预筛选层，实现"全市场扫描 → AI深度分析"双引擎联动。

用法: python scripts/fetch_screened_stocks.py [--top 25] [--fallback AAPL,MSFT,...]
输出: 逗号分隔的股票代码列表（写入 stdout）
"""

import argparse
import re
import sys
import urllib.request
from pathlib import Path

# stock-screener 每日扫描结果（已通过 GitHub Actions 提交到仓库）
SCAN_URL = "https://raw.githubusercontent.com/Jecket4399/stock-screener/main/data/daily_scans/latest_optimized_scan.txt"

# 默认兜底列表（全行业覆盖，当拉取失败时使用）
DEFAULT_FALLBACK = (
    "AAPL,MSFT,NVDA,GOOGL,AMZN,META,TSLA,AVGO,CRM,NOW,"
    "AMD,PANW,CRWD,PLTR,JPM,V,MA,GS,UNH,LLY,JNJ,ABBV,"
    "XOM,CVX,GE,BA,CAT,LMT,NEE,HD,COST,WMT,PG,KO,NFLX,DIS,UBER,SBUX"
)


def fetch_scan_results() -> str:
    """从 stock-screener 仓库拉取最新扫描结果"""
    try:
        req = urllib.request.Request(SCAN_URL)
        req.add_header("User-Agent", "daily-stock-analysis-bot")
        with urllib.request.urlopen(req, timeout=30) as resp:
            return resp.read().decode("utf-8")
    except Exception as e:
        print(f"⚠️  拉取筛选结果失败: {e}", file=sys.stderr)
        return ""


def parse_tickers(content: str) -> list[str]:
    """从扫描报告中提取股票代码，优先取买入信号"""
    tickers = []
    buy_scores = {}  # ticker -> score

    for line in content.split("\n"):
        # 匹配买入信号: "🟢 BUY #1: AAPL | Score: 85/125"
        m = re.match(r".*BUY\s+#\d+:\s+(\w+)\s*\|\s*Score:\s*(\d+)", line)
        if m:
            ticker, score = m.group(1), int(m.group(2))
            buy_scores[ticker] = score
            if ticker not in tickers:
                tickers.append(ticker)
            continue

        # 匹配卖出信号: "🚨 SELL #1: NVDA | Score: 75/110"
        m = re.match(r".*SELL\s+#\d+:\s+(\w+)\s*\|\s*Score:\s*(\d+)", line)
        if m:
            ticker = m.group(1)
            # 卖出信号也纳入分析（AI 会判断是否真的该卖）
            if ticker not in tickers:
                tickers.append(ticker)

    # 按买入评分降序排列
    tickers.sort(key=lambda t: buy_scores.get(t, 0), reverse=True)
    return tickers


def parse_fallback_text(content: str) -> list[str]:
    """尝试从"Additional Buys"段落提取更多股票"""
    tickers = []
    in_additional = False
    for line in content.split("\n"):
        if "ADDITIONAL BUYS" in line:
            in_additional = True
            continue
        if in_additional and "=" * 40 in line:
            in_additional = False
            continue
        if in_additional:
            # 逗号分隔的股票列表
            found = re.findall(r"[A-Z]{1,5}", line)
            tickers.extend(found)
    return tickers


def main():
    parser = argparse.ArgumentParser(description="从 stock-screener 拉取筛选后的股票列表")
    parser.add_argument("--top", type=int, default=25, help="取前 N 只股票 (默认 25)")
    parser.add_argument("--fallback", type=str, default=DEFAULT_FALLBACK,
                        help="拉取失败时的兜底列表")
    args = parser.parse_args()

    content = fetch_scan_results()

    if not content:
        print(args.fallback)
        return

    tickers = parse_tickers(content)

    # 补充 Additional Buys 中的股票
    additional = parse_fallback_text(content)
    for t in additional:
        if t not in tickers:
            tickers.append(t)

    if not tickers:
        print("⚠️  未从扫描结果中提取到股票，使用兜底列表", file=sys.stderr)
        print(args.fallback)
        return

    top_n = tickers[: args.top]
    print(f"✅ 从全市场筛选到 {len(tickers)} 只有信号的股票，取 Top {len(top_n)}",
          file=sys.stderr)
    print(",".join(top_n))


if __name__ == "__main__":
    main()
