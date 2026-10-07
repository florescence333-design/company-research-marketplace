"""SEC Company Facts and 10-K/10-Q raw collector.

SEC facts are selected by filing date and period. Missing values remain missing.
This module does not make investment assessments.
"""

import hashlib
import json
import os
import re
import time
import urllib.error
import urllib.request
import uuid
from datetime import date, datetime, timedelta, timezone
from decimal import Decimal
from pathlib import Path

from business import FILING_ACCESSION, FILING_DATE, FILING_URL, extract_business_facts

ROOT = Path(__file__).resolve().parents[1]
FACTS_URL = "https://data.sec.gov/api/xbrl/companyfacts/CIK0001819994.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
TAG_MAP = {
    "revenue": ("RevenueFromContractWithCustomerExcludingAssessedTax", "Revenues", "SalesRevenueNet"),
    "operating_income": ("OperatingIncomeLoss",),
    "net_income": ("NetIncomeLoss", "ProfitLoss"),
    "operating_cash_flow": ("NetCashProvidedByUsedInOperatingActivities",),
    "capex": ("PaymentsToAcquirePropertyPlantAndEquipment",),
}
POINT_TAGS = {
    "cash": ("CashAndCashEquivalentsAtCarryingValue",),
    "assets": ("Assets",),
    "liabilities": ("Liabilities",),
    "stockholders_equity": ("StockholdersEquity",),
}


def validate_us_gaap(data):
    """Fail before downloading filing bodies when core USD facts are not US-GAAP."""
    facts = data.get("facts") if isinstance(data, dict) else None
    gaap = facts.get("us-gaap") if isinstance(facts, dict) else None
    def has_usd(tags):
        return any(isinstance(gaap.get(tag, {}).get("units", {}).get("USD"), list)
                   and gaap[tag]["units"]["USD"] for tag in tags)
    if not isinstance(gaap, dict) or not has_usd(TAG_MAP["revenue"]) or not has_usd(TAG_MAP["net_income"]):
        raise ValueError("지원 범위 밖: US-GAAP 재무 확인 불가")


def select_filings(submissions, cik, as_of):
    """Select the latest filed original 10-K and 10-Q, never future or foreign forms."""
    if int(submissions.get("cik", cik)) != int(cik):
        raise ValueError("SEC submissions CIK 불일치")
    recent = submissions.get("filings", {}).get("recent", {})
    fields = ("form", "reportDate", "filingDate", "accessionNumber", "primaryDocument")
    if not all(isinstance(recent.get(field), (list, tuple)) for field in fields):
        raise ValueError("SEC 공시 메타데이터 불완전")
    if len({len(recent[field]) for field in fields}) != 1:
        raise ValueError("SEC 공시 메타데이터 길이 불일치")
    selected = []
    cutoff = date.fromisoformat(as_of)
    for form in ("10-K", "10-Q"):
        eligible = []
        for values in zip(*(recent[field] for field in fields)):
            if values[0] != form:
                continue
            row = dict(zip(fields, values))
            try:
                report_date = date.fromisoformat(row["reportDate"])
                filed_date = date.fromisoformat(row["filingDate"])
            except (TypeError, ValueError):
                raise ValueError(f"{form} 공시 날짜 검증 실패") from None
            if filed_date <= cutoff and report_date <= cutoff:
                eligible.append(row)
        if not eligible:
            raise ValueError(f"기준일 내 {form} 공시 확인 불가")
        item = max(eligible, key=lambda row: (row["reportDate"], row["filingDate"]))
        accession = item["accessionNumber"]
        document = item["primaryDocument"]
        if not re.fullmatch(r"\d{10}-\d{2}-\d{6}", accession) or not re.fullmatch(r"[A-Za-z0-9._-]+", document):
            raise ValueError(f"{form} 공시 주소 검증 실패")
        selected.append({"form": form, "report_date": item["reportDate"], "filed": item["filingDate"],
                         "accession_number": accession, "primary_document": document,
                         "url": f"https://www.sec.gov/Archives/edgar/data/{int(cik)}/{accession.replace('-', '')}/{document}"})
    return selected


def filing_cache_path(root, ticker, filing):
    return root / "data" / "sec" / ticker / "filings" / f"{filing['accession_number'].replace('-', '')}-{filing['primary_document']}"


def _download_sec(url):
    request = urllib.request.Request(url, headers={"User-Agent": sec_user_agent(), "Accept-Encoding": "identity"})
    for attempt in range(3):
        try:
            time.sleep(1)
            with urllib.request.urlopen(request, timeout=30) as response:
                return response.read()
        except (urllib.error.HTTPError, urllib.error.URLError, TimeoutError) as exc:
            if attempt == 2 or isinstance(exc, urllib.error.HTTPError) and exc.code not in (429, 500, 502, 503, 504):
                raise
            time.sleep(2 ** attempt)
    raise RuntimeError("SEC collection failed")


def fetch_submissions(cik):
    return json.loads(_download_sec(SUBMISSIONS_URL.format(cik=int(cik))))


def fetch_filing(cache_path, url):
    if cache_path.exists():
        raw = cache_path.read_bytes()
    else:
        raw = _download_sec(url)
        if not raw:
            raise ValueError("빈 SEC 공시 본문")
        cache_path.parent.mkdir(parents=True, exist_ok=True)
        cache_path.write_bytes(raw)
    return raw


def sec_user_agent():
    """Read SEC identity from the process or Windows user environment, never log it."""
    user_agent = os.environ.get("SEC_USER_AGENT", "").strip()
    if not user_agent and os.name == "nt":
        try:
            import winreg
            with winreg.OpenKey(winreg.HKEY_CURRENT_USER, "Environment") as key:
                user_agent = str(winreg.QueryValueEx(key, "SEC_USER_AGENT")[0]).strip()
        except (ImportError, OSError):
            pass
    if "@" not in user_agent or len(user_agent) < 12:
        raise RuntimeError("Set SEC_USER_AGENT in the Windows User environment or current process")
    return user_agent


def _duration(entry):
    try:
        return (date.fromisoformat(entry["end"]) - date.fromisoformat(entry["start"])).days + 1
    except (KeyError, ValueError):
        return None


def _eligible(entry, as_of):
    return entry.get("form") in ("10-K", "10-Q") and entry.get("filed", "9999") <= as_of and entry.get("end", "9999") <= as_of


def _eligible_period(entry, as_of):
    return entry.get("form") in ("10-K", "10-Q", "10-K/A", "10-Q/A") and entry.get("filed", "9999") <= as_of and entry.get("end", "9999") <= as_of


def annual_facts(entries, as_of, include_amended=False):
    """Latest known annual fact per period end, newest period first."""
    chosen = {}
    for entry in entries:
        if not (_eligible_period(entry, as_of) if include_amended else _eligible(entry, as_of)) \
                or entry.get("form") not in (("10-K", "10-K/A") if include_amended else ("10-K",)):
            continue
        duration = _duration(entry)
        if duration is None or not 330 <= duration <= 380 or not isinstance(entry.get("val"), (int, float)):
            continue
        key = entry["end"]
        if key not in chosen or (entry["filed"], entry.get("accn", "")) > (chosen[key]["filed"], chosen[key].get("accn", "")):
            chosen[key] = entry
    return [chosen[end] for end in sorted(chosen, reverse=True)]


def quarterly_facts(entries, as_of, include_amended=False):
    """Disclosed standalone quarters, excluding year-to-date 10-Q values."""
    chosen = {}
    for entry in entries:
        if not (_eligible_period(entry, as_of) if include_amended else _eligible(entry, as_of)) \
                or not 70 <= (_duration(entry) or 0) <= 110:
            continue
        if not isinstance(entry.get("val"), (int, float)):
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


def _period_fact(data, tags, unit, start, end, as_of, *, form=None, accession=None):
    """Select one comparable, non-dimensional Company Facts period and tag."""
    candidates = []
    for tag in tags:
        for entry in _tag_entries(data, tag, unit):
            if (entry.get("start") != start or entry.get("end") != end
                    or not _eligible_period(entry, as_of)
                    or form is not None and entry.get("form") not in (form, f"{form}/A")
                    or accession is not None and entry.get("accn") != accession
                    or not isinstance(entry.get("val"), (int, float))):
                continue
            candidates.append((entry, tag))
    if not candidates:
        return None
    # A later filing may restate a period. Ties with different values or tags
    # are ambiguous rather than an invitation to pick an arbitrary range.
    latest = max((entry["filed"], entry.get("accn", "")) for entry, _ in candidates)
    tied = [(entry, tag) for entry, tag in candidates
            if (entry["filed"], entry.get("accn", "")) == latest]
    return tied[0] if len({(tag, entry["val"]) for entry, tag in tied}) == 1 else None


def _period_summary(data, filings, as_of, add_source):
    """Annual, latest standalone quarter and TTM from the latest report end."""
    annual_filing, quarter_filing = filings
    annual_end = annual_filing["report_date"]
    annual = {}
    for name, tags in {**{key: TAG_MAP[key] for key in ("revenue", "operating_income", "net_income")},
                       "eps": ("EarningsPerShareDiluted",)}.items():
        unit = "USD/shares" if name == "eps" else "USD"
        # Annual start comes from the filed 10-K fact, not January 1.
        matches = []
        for tag in tags:
            for entry in _tag_entries(data, tag, unit):
                if (entry.get("end") == annual_end and entry.get("form") in ("10-K", "10-K/A")
                        and _eligible_period(entry, as_of) and 330 <= (_duration(entry) or 0) <= 380
                        and isinstance(entry.get("val"), (int, float))):
                    matches.append((entry, tag))
        starts = {entry["start"] for entry, _ in matches}
        if len(starts) == 1:
            annual[name] = _period_fact(data, tags, unit, starts.pop(), annual_end, as_of, form="10-K")
        else:
            annual[name] = None

    latest = max(filings, key=lambda item: (item["report_date"], item["filed"]))
    quarter_end = latest["report_date"]
    results = []

    def unavailable(metric_id, unit, reason):
        return {"metric_id": metric_id, "value": None, "status": "unavailable", "unit": unit,
                "approximate": False, "reason": reason}

    def direct(metric_id, unit, selected):
        if selected is None:
            return unavailable(metric_id, unit, "동일 태그·단위·기간의 SEC 원본 값 확인 불가")
        entry, tag = selected
        return {"metric_id": metric_id, "value": entry["val"], "status": "ok", "unit": unit,
                "approximate": False, "period_start": entry["start"], "period_end": entry["end"],
                "source_ids": [add_source(entry, tag, unit)]}

    def derived(metric_id, unit, parts, operation, start, end):
        if any(part is None for part in parts):
            return unavailable(metric_id, unit, "같은 회계기간·태그·단위의 계산 원본 확인 불가")
        tags = {tag for _, tag in parts}
        if len(tags) != 1:
            return unavailable(metric_id, unit, "계산 원본 태그 불일치")
        values = [entry["val"] for entry, _ in parts]
        value = values[0] - values[1] if operation == "annual_minus_nine_months" else values[0] + values[1] - values[2]
        return {"metric_id": metric_id, "value": value, "status": "ok", "unit": unit,
                "approximate": False, "calculation": operation, "period_start": start, "period_end": end,
                "source_ids": [add_source(entry, tag, unit) for entry, tag in parts]}

    def disclosed_quarter(tags, unit, filing):
        candidates = []
        for tag in tags:
            for entry in _tag_entries(data, tag, unit):
                if (entry.get("end") == filing["report_date"]
                        and entry.get("form") in (filing["form"], f"{filing['form']}/A")
                        and _eligible_period(entry, as_of) and 70 <= (_duration(entry) or 0) <= 110):
                    candidates.append((entry, tag))
        starts = {entry["start"] for entry, _ in candidates}
        if len(starts) != 1:
            return None
        return _period_fact(data, tags, unit, starts.pop(), filing["report_date"], as_of,
                            form=filing["form"])

    for name in ("revenue", "operating_income", "net_income", "eps"):
        tags = ("EarningsPerShareDiluted",) if name == "eps" else TAG_MAP[name]
        unit = "USD/shares" if name == "eps" else "USD"
        base = annual[name]
        if name == "eps":
            results.append(direct("eps_annual", unit, base))
        else:
            results.append(direct(f"{name}_fy{annual_end[:4]}", unit, base))
        quarter_id = f"{name}_quarter_latest"
        ttm_id = f"{name}_ttm"
        if latest["form"] == "10-K":
            if name == "eps":
                disclosed = disclosed_quarter(tags, unit, latest)
                results.append(direct(quarter_id, unit, disclosed) if disclosed else
                               unavailable(quarter_id, unit, "4분기 희석 EPS 원본 없음; 연간·9개월 EPS 차감 불가"))
            elif base:
                start = base[0]["start"]
                nine = _period_fact(data, (base[1],), unit, start, quarter_filing["report_date"], as_of,
                                    form="10-Q")
                if nine and 240 <= (_duration(nine[0]) or 0) <= 300 and 70 <= (date.fromisoformat(annual_end) - date.fromisoformat(nine[0]["end"])).days <= 110:
                    quarter_start = (date.fromisoformat(nine[0]["end"]) + timedelta(days=1)).isoformat()
                    results.append(derived(quarter_id, unit, (base, nine), "annual_minus_nine_months",
                                           quarter_start, annual_end))
                else:
                    results.append(unavailable(quarter_id, unit, "같은 회계연도의 9개월 누적 10-Q 확인 불가"))
            else:
                results.append(unavailable(quarter_id, unit, "10-K 연간 원본 확인 불가"))
            results.append(direct(ttm_id, unit, base))
            continue

        # A 10-Q can contain both standalone and year-to-date facts. They
        # share the end date, so the duration and filing accession matter.
        standalone = disclosed_quarter(tags, unit, latest)
        results.append(direct(quarter_id, unit, standalone))
        if name == "eps":
            # A sum/difference of EPS or a one-quarter share denominator is
            # not an observed TTM diluted EPS.
            direct_ttm = None
            for tag in tags:
                for entry in _tag_entries(data, tag, unit):
                    if (entry.get("end") == quarter_end and entry.get("form") in ("10-Q", "10-Q/A")
                            and _eligible_period(entry, as_of) and 330 <= (_duration(entry) or 0) <= 380):
                        direct_ttm = _period_fact(data, (tag,), unit, entry["start"], quarter_end,
                                                  as_of, form="10-Q")
            results.append(direct(ttm_id, unit, direct_ttm))
            continue
        if not base:
            results.append(unavailable(ttm_id, unit, "10-K 연간 원본 확인 불가"))
            continue
        annual_start = date.fromisoformat(base[0]["start"])
        current_start = (date.fromisoformat(annual_end) + timedelta(days=1)).isoformat()
        current = _period_fact(data, (base[1],), unit, current_start, quarter_end, as_of, form="10-Q")
        try:
            prior_end = date.fromisoformat(quarter_end).replace(year=date.fromisoformat(quarter_end).year - 1).isoformat()
        except ValueError:
            prior_end = None
        prior = (_period_fact(data, (base[1],), unit, annual_start.isoformat(), prior_end, as_of, form="10-Q")
                 if prior_end else None)
        if (current and prior and 70 <= (_duration(current[0]) or 0) <= 300
                and 70 <= (_duration(prior[0]) or 0) <= 300):
            ttm_start = (date.fromisoformat(prior_end) + timedelta(days=1)).isoformat()
            results.append(derived(ttm_id, unit, (base, current, prior),
                                   "annual_plus_current_ytd_minus_prior_ytd", ttm_start, quarter_end))
        else:
            results.append(unavailable(ttm_id, unit, "동일 회계기간 누적 10-Q 원본 확인 불가"))
    return results, latest


def build_sec_bundle(data, raw, engine, now, business_raw=None, *, company=None, filings=None):
    """Construct a schema-valid bundle from already downloaded public facts."""
    if company is None:
        if data.get("cik") != 1819994 or "Rocket Lab" not in data.get("entityName", ""):
            raise ValueError("SEC response is not RKLB / Rocket Lab")
        ticker, cik, exchange, security_type = "RKLB", "0001819994", "NASDAQ", "Common Stock"
    else:
        ticker, cik = company["ticker"], company["cik"]
        if data.get("cik") != int(cik):
            raise ValueError("SEC Company Facts CIK 불일치")
        exchange, security_type = company.get("exchange"), company.get("security_type")
        filings = filings or []
        if [item["form"] for item in filings] != ["10-K", "10-Q"]:
            raise ValueError("10-K·10-Q 원본 둘 다 필요")
        business_raw = filings[0]["raw"]
    if engine not in ("gpt", "claude"):
        raise ValueError("Unknown engine")
    as_of = now.date().isoformat()
    raw_digest = hashlib.sha256(raw).hexdigest()
    digest = hashlib.sha256(raw + (b"".join(item["raw"] for item in filings) if company else (business_raw or b""))).hexdigest()
    snapshot_id = f"sec-snapshot-{digest[:16]}"
    run_id = f"{ticker.lower()}-{engine}-{now:%Y%m%dT%H%M%SZ}-{uuid.uuid4().hex[:8]}"
    timestamp = now.isoformat()
    template = json.loads((ROOT / "template" / "sections.json").read_text(encoding="utf-8"))
    meta = {
        "schema_version": "v1-draft", "run_id": run_id, "data_snapshot_id": snapshot_id,
        "analysis_as_of": timestamp, "generated_at": timestamp, "ticker": ticker,
        "company_name": data["entityName"],
        "cik": cik, "exchange": exchange, "security_type": security_type,
        "currency": "USD", "engine": engine, "model": None, "sample": False,
        "code_version": "v0.1", "template_version": template["source_sha256"],
        "technical_defaults_version": "v1", "decision_policy_version": "v0.1",
        "filing_sha256": hashlib.sha256(business_raw).hexdigest() if business_raw else None,
    }
    if company:
        meta["companyfacts_sha256"] = raw_digest
        meta["sec_filings"] = [{**{key: item[key] for key in ("form", "report_date", "filed", "accession_number", "primary_document", "url")},
                                "sha256": hashlib.sha256(item["raw"]).hexdigest()} for item in filings]
    metrics, sources = [], []

    def add_source(selected, tag, unit):
        source_id = f"sec-{len(sources) + 1:03d}"
        facts_url = FACTS_URL if company is None else f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
        form_label = f", {selected['form']}" if company else ""
        sources.append({"source_id": source_id, "url": facts_url,
                        "title": f"SEC Company Facts · {tag}", "accessed_at": timestamp,
                        "accession_number": selected.get("accn"),
                        "location": f"us-gaap/{tag}, {unit}, {selected.get('start', 'instant')}~{selected['end']}, filed {selected['filed']}{form_label}",
                        "content_sha256": raw_digest})
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
            candidates.extend((entry, tag) for entry in annual_facts(_tag_entries(data, tag, "USD"), as_of,
                                                                        include_amended=bool(company)))
        by_end = {}
        for entry, tag in sorted(candidates, key=lambda item: (item[0]["filed"], item[0].get("accn", "")), reverse=True):
            by_end.setdefault(entry["end"], (entry, tag))
        for end in sorted(by_end, reverse=True)[:4]:
            entry, tag = by_end[end]
            append_metric(f"{metric_name}_fy{end[:4]}", "USD", entry, tag)
        if not by_end:
            append_metric(f"{metric_name}_annual", "USD", None)

    quarter_candidates = []
    for tag in TAG_MAP["revenue"]:
        quarter_candidates.extend((entry, tag) for entry in quarterly_facts(_tag_entries(data, tag, "USD"), as_of,
                                                                               include_amended=bool(company)))
    quarter_by_end = {}
    for entry, tag in sorted(quarter_candidates, key=lambda item: (item[0]["filed"], item[0].get("accn", "")), reverse=True):
        quarter_by_end.setdefault(entry["end"], (entry, tag))
    latest_end = max(quarter_by_end, default=None)
    latest_entry, latest_tag = quarter_by_end[latest_end] if latest_end else (None, None)
    prior_end = f"{int(latest_end[:4]) - 1}{latest_end[4:]}" if latest_end else None
    prior_entry, prior_tag = quarter_by_end.get(prior_end, (None, None))
    append_metric("revenue_quarter_latest", "USD", latest_entry, latest_tag)
    append_metric("revenue_quarter_prior_year", "USD", prior_entry, prior_tag)
    latest_metric, prior_metric = metrics[-2:]
    if latest_entry and prior_entry and prior_entry["val"] > 0:
        metrics.append({"metric_id": "revenue_quarter_yoy", "unit": "%", "approximate": False,
                        "status": "ok", "value": float((Decimal(str(latest_entry["val"])) /
                                                       Decimal(str(prior_entry["val"])) - 1) * 100),
                        "period_start": latest_entry["start"], "period_end": latest_entry["end"],
                        "source_ids": latest_metric["source_ids"] + prior_metric["source_ids"]})
    else:
        metrics.append({"metric_id": "revenue_quarter_yoy", "unit": "%", "approximate": False,
                        "status": "unavailable", "value": None,
                        "reason": "동일 분기의 전년 매출과 양수 비교 기준 필요"})

    for metric_name, tags in POINT_TAGS.items():
        candidates = [(entry, tag) for tag in tags if (entry := _point_fact(_tag_entries(data, tag, "USD"), as_of))]
        entry, tag = max(candidates, key=lambda item: (item[0]["end"], item[0]["filed"]), default=(None, None))
        append_metric(metric_name, "USD", entry, tag)

    annual_metrics = {m["metric_id"]: m for m in metrics if m["status"] == "ok"}
    liabilities, equity = annual_metrics.get("liabilities"), annual_metrics.get("stockholders_equity")
    if liabilities and equity and liabilities["period_end"] == equity["period_end"] and equity["value"] > 0:
        metrics.append({"metric_id": "liabilities_to_equity", "value": float(
            Decimal(str(liabilities["value"])) / Decimal(str(equity["value"])) * 100),
                        "status": "ok", "unit": "%", "approximate": False,
                        "period_end": liabilities["period_end"],
                        "source_ids": list(dict.fromkeys(liabilities["source_ids"] + equity["source_ids"]))})
    else:
        metrics.append({"metric_id": "liabilities_to_equity", "value": None,
                        "status": "unavailable", "unit": "%", "approximate": False,
                        "reason": "동일 기준일 총부채·양수 자기자본 필요"})
    for year in sorted({key[-4:] for key in annual_metrics if key.startswith("operating_income_fy")}):
        income, revenue = annual_metrics[f"operating_income_fy{year}"], annual_metrics.get(f"revenue_fy{year}")
        if revenue and income["period_start"] == revenue["period_start"] and income["period_end"] == revenue["period_end"]:
            result = {"metric_id": f"operating_margin_fy{year}", "unit": "%", "approximate": False}
            if revenue["value"] > 0:
                result.update(value=float(Decimal(str(income["value"])) / Decimal(str(revenue["value"])) * 100),
                              status="ok", period_start=income["period_start"], period_end=income["period_end"],
                              source_ids=list(dict.fromkeys(income["source_ids"] + revenue["source_ids"])))
            else:
                result.update(value=None, status="unavailable", reason="매출 0 이하로 영업이익률 계산 불가")
            metrics.append(result)
    for year in sorted({key[-4:] for key in annual_metrics if key.startswith("operating_cash_flow_fy")}):
        cash_flow, capex = annual_metrics[f"operating_cash_flow_fy{year}"], annual_metrics.get(f"capex_fy{year}")
        if capex and cash_flow["period_start"] == capex["period_start"] and cash_flow["period_end"] == capex["period_end"]:
            result = {"metric_id": f"free_cash_flow_fy{year}", "unit": "USD", "approximate": False}
            if capex["value"] >= 0:
                result.update(value=float(Decimal(str(cash_flow["value"])) - Decimal(str(capex["value"]))),
                              status="ok", period_start=cash_flow["period_start"], period_end=cash_flow["period_end"],
                              source_ids=list(dict.fromkeys(cash_flow["source_ids"] + capex["source_ids"])))
            else:
                result.update(value=None, status="unavailable", reason="설비투자 지출 부호 확인 필요")
            metrics.append(result)

    annual_revenue = {int(m["metric_id"][-4:]): m for m in metrics
                      if m["metric_id"].startswith("revenue_fy") and m["status"] == "ok"}
    for year in sorted(annual_revenue):
        current, prior = annual_revenue[year], annual_revenue.get(year - 1)
        if prior and prior["value"] > 0 and current["value"] > 0:
            value = float((Decimal(str(current["value"])) / Decimal(str(prior["value"])) - 1) * 100)
            metrics.append({"metric_id": f"revenue_growth_fy{year}", "value": value,
                            "status": "ok", "unit": "%", "approximate": False,
                            "period_start": current["period_start"], "period_end": current["period_end"],
                            "source_ids": list(dict.fromkeys(current["source_ids"] + prior["source_ids"]))})
    newest = max(annual_revenue, default=None)
    base = annual_revenue.get(newest - 3) if newest else None
    if base and all(year in annual_revenue for year in range(newest - 3, newest + 1)) and base["value"] > 0 and annual_revenue[newest]["value"] > 0:
        current = annual_revenue[newest]
        value = float(((Decimal(str(current["value"])) / Decimal(str(base["value"]))) ** (Decimal(1) / Decimal(3)) - 1) * 100)
        metrics.append({"metric_id": "revenue_cagr_3y", "value": value,
                        "status": "ok", "unit": "%", "approximate": False,
                        "period_start": base["period_start"], "period_end": current["period_end"],
                        "source_ids": list(dict.fromkeys(current["source_ids"] + base["source_ids"]))})
    else:
        metrics.append({"metric_id": "revenue_cagr_3y", "value": None,
                        "status": "unavailable", "unit": "%", "approximate": False,
                        "reason": "연속 4개 회계연도 매출과 양수 시작·종료 값 필요"})

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

    if company:
        normalized, latest_filing = _period_summary(data, filings, as_of, add_source)
        replaced = {item["metric_id"] for item in normalized}
        metrics[:] = [item for item in metrics if item["metric_id"] not in replaced]
        metrics.extend(normalized)
        latest_year = latest_filing["report_date"][:4] if latest_filing["form"] == "10-K" else filings[0]["report_date"][:4]
        normalized_by_id = {item["metric_id"]: item for item in normalized}
        if normalized_by_id[f"revenue_fy{latest_year}"]["status"] != "ok":
            metrics[:] = [item for item in metrics if item["metric_id"] not in (
                f"operating_margin_fy{latest_year}", f"revenue_growth_fy{latest_year}", "revenue_cagr_3y")]
        elif normalized_by_id[f"operating_income_fy{latest_year}"]["status"] != "ok":
            metrics[:] = [item for item in metrics if item["metric_id"] != f"operating_margin_fy{latest_year}"]
        # Prior-year quarter and YoY must refer to the same latest quarter.
        # The older revenue-only selector may have chosen a prior 10-Q when
        # the latest report is a 10-K, so suppress it until matched evidence.
        if latest_filing["form"] == "10-K" or normalized_by_id["revenue_quarter_latest"]["status"] != "ok":
            for item in metrics:
                if item["metric_id"] in ("revenue_quarter_prior_year", "revenue_quarter_yoy"):
                    metric_id = item["metric_id"]
                    item.clear()
                    item.update(metric_id=metric_id, value=None, status="unavailable",
                        unit="USD" if metric_id == "revenue_quarter_prior_year" else "%",
                        approximate=False, reason="최신 분기와 전년 동기 원본의 비교 가능성 확인 불가")
        used_sources = {source_id for item in metrics for source_id in item.get("source_ids", [])}
        sources[:] = [item for item in sources if item["source_id"] in used_sources]
        source_ids = {item["source_id"]: f"sec-{index:03d}" for index, item in enumerate(sources, 1)}
        for item in sources:
            item["source_id"] = source_ids[item["source_id"]]
        for item in metrics:
            if "source_ids" in item:
                item["source_ids"] = [source_ids[source_id] for source_id in item["source_ids"]]

    extracted = {"schema_version": "v1-draft", "run_id": run_id,
                 "data_snapshot_id": snapshot_id, "facts": []}
    annual_revenue = next((m for m in metrics if m["metric_id"] == "revenue_fy2025" and m["status"] == "ok"), None)
    valid_filing = annual_revenue and any(s["source_id"] in annual_revenue["source_ids"] and s["accession_number"] == FILING_ACCESSION for s in sources)
    if business_raw and ticker == "RKLB" and as_of >= FILING_DATE and valid_filing:
        business_digest = hashlib.sha256(business_raw).hexdigest()
        business = extract_business_facts(business_raw)
        launch = business.get("launch_revenue_fy2025")
        space = business.get("space_revenue_fy2025")
        if launch and space and launch["value"] + space["value"] != annual_revenue["value"]:
            business.pop("launch_revenue_fy2025")
            business.pop("space_revenue_fy2025")
        for fact_id, item in business.items():
            source_id = f"sec-{len(sources) + 1:03d}"
            sources.append({"source_id": source_id, "url": FILING_URL,
                            "title": "RKLB 2025 Form 10-K", "accessed_at": timestamp,
                            "accession_number": FILING_ACCESSION, "location": item["location"],
                            "content_sha256": business_digest})
            extracted["facts"].append({"fact_id": fact_id, "value": item["value"],
                                        "unit": item["unit"], "source_id": source_id,
                                        "location": item["location"],
                                        "verification": "matched_official_filing_text"})

    decision = {"schema_version": "v1-draft", "decision_policy_version": "v0.1",
                "run_id": run_id, "data_snapshot_id": snapshot_id, "verdict": "판정 보류 (v0.1)",
                "reason": "판정 세부 규칙 미정", "business_quality": None, "price_category": None,
                "pending_rules": ["item_thresholds", "required_financials", "reverse_dcf_details"]}
    return {"meta": meta, "metrics": {"run_id": run_id, "data_snapshot_id": snapshot_id, "metrics": metrics},
            "sources": {"sources": sources}, "decision": decision,
            "extracted-facts": extracted}


def fetch_companyfacts(cache_path, cik=1819994, max_age_hours=None):
    """Read an eligible cache or fetch CIK-specific facts with SEC request spacing."""
    if cache_path.exists() and (max_age_hours is None or time.time() - cache_path.stat().st_mtime <= max_age_hours * 3600):
        raw = cache_path.read_bytes()
        data = json.loads(raw)
        if data.get("cik") != int(cik):
            raise ValueError("SEC Company Facts CIK 불일치")
        return data, raw
    url = f"https://data.sec.gov/api/xbrl/companyfacts/CIK{int(cik):010d}.json"
    raw = _download_sec(url)
    data = json.loads(raw)
    if data.get("cik") != int(cik):
        raise ValueError("SEC Company Facts CIK 불일치")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(raw)
    return data, raw


def fetch_10k(cache_path):
    """Legacy RKLB 2025 filing cache reader for older runs."""
    if cache_path.exists():
        return cache_path.read_bytes()
    raw = _download_sec(FILING_URL)
    if b"rocket lab" not in raw.lower() or b"2025" not in raw:
        raise ValueError("Unexpected SEC 10-K response")
    cache_path.parent.mkdir(parents=True, exist_ok=True)
    cache_path.write_bytes(raw)
    return raw
