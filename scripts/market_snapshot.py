"""Refresh one company's optional market snapshot without persisting the API key."""

import argparse
import json
import math
import os
import re
import urllib.error
import urllib.parse
import urllib.request
from datetime import datetime, timedelta, timezone
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASE = "https://api.twelvedata.com"


def user_api_key():
    key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if not key and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as registry:
                key = str(winreg.QueryValueEx(registry, "TWELVE_DATA_API_KEY")[0]).strip()
        except (ImportError, OSError):
            pass
    return key


def finite_positive(value):
    try:
        number = float(value)
        return number if math.isfinite(number) and number > 0 else None
    except (TypeError, ValueError):
        return None


def normalize_provider_data(quote, statistics):
    quote = quote if isinstance(quote, dict) and quote.get("status") != "error" else {}
    statistics = statistics if isinstance(statistics, dict) else {}
    details = statistics.get("statistics") or {}
    valuations = details.get("valuations_metrics") or details.get("valuation_metrics") or {}
    week = quote.get("fifty_two_week") or {}
    low, high = finite_positive(week.get("low")), finite_positive(week.get("high"))
    day = str(quote.get("datetime") or "")[:10]
    if not day or len(day) != 10:
        day = None
    return {
        "source": "Twelve Data",
        "as_of": day,
        "price": finite_positive(quote.get("close")),
        "market_cap": finite_positive(valuations.get("market_capitalization")),
        "pe_ttm": finite_positive(valuations.get("trailing_pe")),
        "range_52w": {"low": low, "high": high} if low and high and high >= low else None,
    }


def _request(path, key):
    request = urllib.request.Request(BASE + path, headers={"Authorization": "apikey " + key,
                                                       "User-Agent": "company-research-dashboard/0.1"})
    with urllib.request.urlopen(request, timeout=12) as response:
        result = json.loads(response.read(1_000_000))
    return result if isinstance(result, dict) else {}


def refresh_market_snapshot(ticker, root=ROOT):
    if not isinstance(ticker, str) or not re.fullmatch(r"[A-Z][A-Z0-9.-]{0,9}", ticker):
        raise ValueError("안전하지 않은 시장 스냅샷 티커")
    snapshot = root / "site" / "data" / "companies" / ticker / "market-snapshot.json"
    key = user_api_key()
    if not key:
        snapshot.unlink(missing_ok=True)
        return "키 없음 · 시장 스냅샷 확인 불가"
    if snapshot.exists():
        try:
            saved = json.loads(snapshot.read_text(encoding="utf-8"))
            created = datetime.fromisoformat(saved["fetched_at"])
            if saved.get("ticker") == ticker and created > datetime.now(timezone.utc) - timedelta(hours=20):
                return "기존 시장 스냅샷 재사용"
        except (OSError, KeyError, ValueError, json.JSONDecodeError):
            pass
    try:
        quote = _request("/quote?" + urllib.parse.urlencode({"symbol": ticker, "interval": "1day"}), key)
    except (OSError, ValueError, json.JSONDecodeError):
        snapshot.unlink(missing_ok=True)
        return "Twelve Data 주가 조회 실패 · 확인 불가"
    if quote.get("symbol") and quote["symbol"].upper() != ticker:
        snapshot.unlink(missing_ok=True)
        return "시장 자료 티커 불일치 · 확인 불가"
    try:
        statistics = _request("/statistics?" + urllib.parse.urlencode({"symbol": ticker}), key)
    except (OSError, ValueError, json.JSONDecodeError):
        statistics = None  # Pro/Venture plan only; absence is not zero.
    if statistics and statistics.get("symbol") and statistics["symbol"].upper() != ticker:
        statistics = None
    normalized = normalize_provider_data(quote, statistics)
    normalized["ticker"] = ticker
    normalized["fetched_at"] = datetime.now(timezone.utc).isoformat()
    snapshot.parent.mkdir(parents=True, exist_ok=True)
    snapshot.write_text(json.dumps(normalized, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    return "시장 스냅샷 갱신 · 제공되지 않은 항목은 확인 불가"


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("ticker")
    args = parser.parse_args()
    print(refresh_market_snapshot(args.ticker.upper()))
