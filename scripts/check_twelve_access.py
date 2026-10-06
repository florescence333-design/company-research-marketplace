"""Check current Twelve Data account access without recording or printing its API key."""

import json
import os
import urllib.error
import urllib.parse
import urllib.request
from datetime import date, timedelta, timezone, datetime


BASE = "https://api.twelvedata.com"
ENDPOINTS = {
    "dividend_history": ("dividends", {"symbol": "AAPL", "range": "1y"}),
    "earnings_schedule": ("earnings_calendar", {
        "country": "United States",
        "start_date": date.today().isoformat(),
        "end_date": (date.today() + timedelta(days=1)).isoformat(),
    }),
}


def classify_response(payload: dict) -> str:
    if payload.get("status") == "error":
        message = str(payload.get("message", "")).lower()
        if any(word in message for word in ("plan", "upgrade", "subscribe", "subscription", "access level", "not available")):
            return "plan_unavailable"
        if "credit" in message or "rate limit" in message:
            return "quota_or_rate_limit"
        return "api_error"
    if "dividends" in payload or "earnings" in payload:
        return "accessible"
    return "unexpected_response"


def probe(path: str, params: dict, key: str) -> str:
    query = urllib.parse.urlencode({**params, "apikey": key})
    request = urllib.request.Request(f"{BASE}/{path}?{query}", headers={"Accept": "application/json"})
    try:
        with urllib.request.urlopen(request, timeout=20) as response:
            payload = json.load(response)
    except urllib.error.HTTPError as exc:
        try:
            payload = json.load(exc)
        except (ValueError, OSError):
            return f"http_{exc.code}"
    except (urllib.error.URLError, TimeoutError, OSError):
        return "network_error"
    except (ValueError, TypeError):
        return "unexpected_response"
    return classify_response(payload) if isinstance(payload, dict) else "unexpected_response"


def main() -> int:
    key = os.environ.get("TWELVE_DATA_API_KEY", "").strip()
    if not key:
        print("Twelve Data API 키 없음: 실제 계정 권한 미확인")
        return 2
    results = {name: probe(path, params, key) for name, (path, params) in ENDPOINTS.items()}
    print(json.dumps({"checked_at": datetime.now(timezone.utc).isoformat(), "access": results}, ensure_ascii=False))
    return 0 if all(value == "accessible" for value in results.values()) else 1


if __name__ == "__main__":
    raise SystemExit(main())
