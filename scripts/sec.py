"""Small SEC Company Facts collector for the v0.1 RKLB path.

SEC facts are selected by filing date and period. Missing values remain missing.
This module does not make investment assessments.
"""

import hashlib
import json
import os
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from pathlib import Path


ROOT = Path(__file__).resolve().parents[1]
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001819994.json"
TAG_MAP = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
}
POINT_TAGS = {
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity",),
}


def _duration(entry):
    try:
        return (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days + 1
    except (KeyError, ValueError):
        return None


def _eligible(entry, as_of):
    return entry.get("form") in ("10-K", "10-Q") and entry.get("filed", "9999") <= as_of and entry.get("end", "9999") <= as_of


def annual_facts(entries, as_of):
    """Latest known annual fact per period end, newest period first."""
    chosen = {}
    for entry in entries:
        if not _eligible(entry, as_of) or entry.get("form") != "10-K":
            continue
        duration = _duration(entry)
        if duration is None or not 330 <= duration <= 380 or not isinstance(entry.get("val"), (int, float)):
            continue
        key = entry["end"]
        if key not in chosen or (entry["filed"], entry.get("accn", "")) > (chosen[key]["filed"], chosen[key].get("accn", "")):
            chosen[key] = entry
    return [chosen[end] for end in sorted(chosen, reverse=True)]


def quarterly_eps_ttm(entries, as_of):
    """Sum four contiguous independently disclosed quarterly diluted EPS facts."""
    quarters = _four_quarters(entries, as_of)
    return round(sum(entry["val"] for entry in quarters), 6) if quarters else None


def _four_quarters(entries, as_of):
    selected = {}
    for entry in entries:
        if not _eligible(entry, as_of) or not 70 <= (_duration(entry) or 0) <= 110:
            continue
        if not isinstance(entry.get("val"), (int, float)):
            continue
        key = (entry["start"], entry["end"])
        if key not in selected or entry["filed"] > selected[key]["filed"]:
            selected[key] = entry
    quarters = sorted(selected.values(), key=lambda e: e["end"], reverse=True)
    for idx in range(len(quarters) - 3):
        four = quarters[idx:idx + 4]
        if all(date.fromisoformat(four[i]["start"]) - date.fromisoformat(four[i + 1]["end"]) == timedelta(days=1) for i in range(3)):
            return four
    return None


def _eps_fallback(data, as_of):
    """Return TTM numerator components and latest diluted denominator, if comparable."""
    annual = annual_facts(_tag_entries(data, "NetIncomeLoss", "USD"), as_of)
    if not annual:
        return None
    base = annual[0]
    end_year = int(base["end"][:4])
    net_income = _tag_entries(data, "NetIncomeLoss", "USD")
    current = [e for e in net_income if _eligible(e, as_of) and e["form"] == "10-Q"
               and e.get("start") == f"{end_year + 1}-01-01" and 80 <= (_duration(e) or 0) <= 300]
    current = max(current, key=lambda e: (e["end"], e["filed"]), default=None)
    if not current:
        return None
    prior_end = f"{end_year}{current['end'][4:]}"
    prior = [e for e in net_income if _eligible(e, as_of) and e.get("start") == f"{end_year}-01-01"
             and e.get("end") == prior_end and isinstance(e.get("val"), (int, float))]
    prior = max(prior, key=lambda e: e["filed"], default=None)
    shares = _tag_entries(data, "WeightedAverageNumberOfDilutedSharesOutstanding", "shares")
    denominator = [e for e in shares if _eligible(e, as_of) and 70 <= (_duration(e) or 0) <= 110
                   and e.get("end") == current["end"] and e.get("val", 0) > 0]
    denominator = max(denominator, key=lambda e: e["filed"], default=None)
    if not prior or not denominator or (date.fromisoformat(as_of) - date.fromisoformat(denominator["end"])).days > 135:
        return None
    return base, current, prior, denominator


def _tag_entries(data, tag, unit):
    return data.get("facts", {}).get("us-gaap", {}).get(tag, {}).get("units", {}).get(unit, [])


def _point_fact(entries, as_of):
    eligible = [e for e in entries if _eligible(e, as_of) and "start" not in e and isinstance(e.get("val"), (int, float))]
    return max(eligible, key=lambda e: (e["end"], e["filed"], e.get("accn", "")), default=None)


def build_sec_bundle(data, raw, engine, now):
    """Construct a schema-valid bundle from already downloaded public facts."""
    if data.get("cik") != 1819994 or "Rocket Lab" not in data.get("entityName", ""):
        raise ValueError("SEC response is not RKLB / Rocket Lab")
    if engine not in ("gpt", "claude"):
        raise ValueError("Unknown engine")
    as_of = now.date().isoformat()
    digest = hashlib.sha256(raw).hexdigest()
    snapshot_id = f"sec-companyfacts-{digest[:16]}"
    run_id = f"rklb-{engine}-{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    timestamp = now.isoformat()
    template = json.loads((ROOT / "template" / "sections.json").read_text(encoding="utf-8"))
    meta = {
        "schema_version": "v1-draft", "run_id": run_id, "data_snapshot_id": snapshot_id,
        "analysis_as_of": timestamp, "generated_at": timestamp, "ticker": "RKLB",
        "cik": "0001819994", "exchange": "NASDAQ", "security_type": "Common Stock",
        "currency": "USD", "engine": engine, "model": None, "sample": False,
        "code_version": "v0.1", "template_version": template["source_sha256"],
        "technical_defaults_version": "v1", "decision_policy_version": "v0.1",
    }
    metrics, sources = [], []

    def add_source(selected, tag, unit):
        source_id = f"sec-{len(sources) + 1:03d}"
        sources.append({"source_id": source_id, "url": FACTS_URL,
                        "title": f"SEC Company Facts · {tag}", "accessed_at": timestamp,
                        "accession_number": selected.get("accn"),
                        "location": f"us-gaap/{tag}, {unit}, {selected.get('start', 'instant')}~{selected['end']}, filed {selected['filed']}",
                        "content_sha256": digest})
        return source_id

    def append_metric(metric_id, unit, selected, tag=None):
        metric = {"metric_id": metric_id, "value": None, "status": "unavailable",
                  "unit": unit, "approximate": False, "reason": "기준일 내 적합한 SEC 공시 값 없음"}
        if selected is not None:
            source_id = add_source(selected, tag, unit)
            metric.update(value=selected["val"], status="ok", source_ids=[source_id],
                          period_end=selected["end"])
            if "start" in selected:
                metric["period_start"] = selected["start"]
            metric.pop("reason")
        metrics.append(metric)

    for metric_name, tags in TAG_MAP.items():
        candidates = []
        for tag in tags:
            candidates.extend((entry, tag) for entry in annual_facts(_tag_entries(data, tag, "USD"), as_of))
        by_end = {}
        for entry, tag in sorted(candidates, key=lambda item: (item[0]["filed"], item[0].get("accn", "")), reverse=True):
            by_end.setdefault(entry["end"], (entry, tag))
        for end in sorted(by_end, reverse=True)[:3]:
            entry, tag = by_end[end]
            append_metric(f"{metric_name}_fy{end[:4]}", "USD", entry, tag)
        if not by_end:
            append_metric(f"{metric_name}_annual", "USD", None)

    for metric_name, tags in POINT_TAGS.items():
        candidates = [(entry, tag) for tag in tags if (entry := _point_fact(_tag_entries(data, tag, "USD"), as_of))]
        entry, tag = max(candidates, key=lambda item: (item[0]["end"], item[0]["filed"]), default=(None, None))
        append_metric(metric_name, "USD", entry, tag)

    eps_entries = _tag_entries(data, "EarningsPerShareDiluted", "USD/shares")
    eps_quarters = _four_quarters(eps_entries, as_of)
    append_metric("eps_ttm", "USD/shares", None)
    if eps_quarters:
        metrics[-1].update(value=round(sum(e["val"] for e in eps_quarters), 6), status="ok",
                           source_ids=[add_source(e, "EarningsPerShareDiluted", "USD/shares") for e in eps_quarters],
                           period_start=eps_quarters[-1]["start"], period_end=eps_quarters[0]["end"])
        metrics[-1].pop("reason")
    elif fallback := _eps_fallback(data, as_of):
        base, current, prior, denominator = fallback
        metrics[-1].update(value=(base["val"] + current["val"] - prior["val"]) / denominator["val"],
                           status="ok", approximate=True,
                           reason="근사: (연간 순이익 + 최신 누적 순이익 - 전년 동기 누적 순이익) ÷ 최근 분기 희석 가중평균 주식 수; 기간·귀속 차이 가능",
                           source_ids=[add_source(e, tag, unit) for e, tag, unit in (
                               (base, "NetIncomeLoss", "USD"), (current, "NetIncomeLoss", "USD"),
                               (prior, "NetIncomeLoss", "USD"),
                               (denominator, "WeightedAverageNumberOfDilutedSharesOutstanding", "shares"))],
                           period_start=(date.fromisoformat(current["end"]).replace(year=int(current["end"][:4]) - 1) + timedelta(days=1)).isoformat(),
                           period_end=current["end"])

    decision = {"schema_version": "v1-draft", "decision_policy_version": "v0.1",
                "run_id": run_id, "data_snapshot_id": snapshot_id, "verdict": "판정 보류 (v0.1)",
                "reason": "판정 세부 규칙 미정", "business_quality": None, "price_category": None,
                "pending_rules": ["item_thresholds", "required_financials", "reverse_dcf_details"]}
    return {"meta": meta, "metrics": {"run_id": run_id, "data_snapshot_id": snapshot_id, "metrics": metrics},
            "sources": {"sources": sources}, "decision": decision}


def fetch_companyfacts(cache_path):
    """Download once, with a declared SEC User-Agent, 1-second spacing and retries."""
    if cache_path.exists():
        raw = cache_path.read_bytes()
        return json.loads(raw), raw
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if "@" not in user_agent or len(user_agent) < 12:
        raise RuntimeError("Set SEC_USER_AGENT locally to an identifying name and contact email")
    request = urllib.request.Request(FACTS_URL, headers={"User-Agent": user_agent, "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            time.sleep(1)
            with urllib.request.urlopen(request, timeout=30) as response:
                raw = response.read()
            data = json.loads(raw)
            if data.get("cik") != 1819994:
                raise ValueError("Unexpected SEC company response")
            cache_path.parent.mkdir(parents=True, exist_ok=True)
            cache_path.write_bytes(raw)
            return data, raw
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2 or isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("SEC collection failed")
