"""SEC metadata-only eligibility check before financial collection."""

import json
import re
import urllib.error
import urllib.request
from dataclasses import dataclass
from datetime import date

from sec import sec_user_agent


TICKERS_URL = "https://www.sec.gov/files/company_tickers_exchange.json"
SUBMISSIONS_URL = "https://data.sec.gov/submissions/CIK{cik:010d}.json"
SUBMISSIONS_HISTORY_URL = "https://data.sec.gov/submissions/{name}"
LISTED_EXCHANGES = {"NYSE", "Nasdaq", "NYSE American"}


@dataclass(frozen=True)
class S0Result:
    ticker: str
    eligible: bool
    reason: str
    cik: str | None = None
    name: str | None = None
    exchange: str | None = None
    sic: str | None = None
    fiscal_years: tuple[int, ...] = ()
    security_type: str | None = None


def _stop(ticker, reason, listing=None, sic=None):
    listing = listing or {}
    return S0Result(ticker, False, reason, str(listing.get("cik", "")).zfill(10) if listing.get("cik") else None,
                    listing.get("name"), listing.get("exchange"), sic)


def _rows(columnar):
    if not isinstance(columnar, dict):
        return []
    fields = ("form", "reportDate", "filingDate")
    if not all(isinstance(columnar.get(key), list) for key in fields):
        return []
    if len({len(columnar[key]) for key in fields}) != 1:
        return []
    return [dict(zip(fields, values)) for values in zip(*(columnar[key] for key in fields))]


def assess(ticker, listing, submission, history=(), as_of=None):
    """Assess eligibility using SEC ticker/submissions metadata only."""
    ticker = ticker.upper()
    as_of = as_of or date.today()
    if not listing or listing.get("ticker") != ticker or not isinstance(listing.get("cik"), int):
        return _stop(ticker, "적합성 확인 실패: 티커 식별 불가")
    if listing.get("exchange") not in LISTED_EXCHANGES:
        return _stop(ticker, "지원 범위 밖: 미국 주요 거래소 상장 확인 불가", listing)
    if not isinstance(submission, dict):
        return _stop(ticker, "적합성 확인 실패: SEC submissions 없음", listing)
    if submission.get("cik") is not None and int(submission["cik"]) != listing["cik"]:
        return _stop(ticker, "적합성 확인 실패: CIK 불일치", listing)
    if ticker not in submission.get("tickers", []):
        return _stop(ticker, "적합성 확인 실패: SEC 티커 불일치", listing)
    ticker_index = submission["tickers"].index(ticker)
    exchanges = submission.get("exchanges", [])
    if ticker_index >= len(exchanges) or exchanges[ticker_index] != listing["exchange"]:
        return _stop(ticker, "적합성 확인 실패: SEC 거래소 불일치", listing)
    sic = str(submission.get("sic") or "")
    if not re.fullmatch(r"\d{4}", sic):
        return _stop(ticker, "적합성 확인 실패: SIC 없음", listing)
    if 6000 <= int(sic) <= 6799:
        return _stop(ticker, f"지원 범위 밖: 금융·보험·부동산(SIC {sic})", listing, sic)
    filings = submission.get("filings", {})
    rows = _rows(filings.get("recent", {}))
    for older in history:
        rows.extend(_rows(older.get("filings", older)))
    if not rows:
        return _stop(ticker, "적합성 확인 실패: 공시 이력 없음", listing, sic)
    forms = {row["form"] for row in rows}
    annual = [row for row in rows if row["form"] in ("10-K", "20-F") and row.get("reportDate") and row.get("filingDate")
              and row["filingDate"] <= as_of.isoformat()]
    latest_annual = max(annual, key=lambda row: (row["reportDate"], row["filingDate"])) if annual else None
    if latest_annual and latest_annual["form"] == "20-F":
        return _stop(ticker, "지원 범위 밖: 20-F/IFRS 공시", listing, sic)
    if "10-K" not in forms or "10-Q" not in forms:
        return _stop(ticker, "적합성 확인 실패: 10-K·10-Q 공시 확인 불가", listing, sic)
    if submission.get("entityType") not in ("operating",):
        return _stop(ticker, "적합성 확인 실패: 일반 영업회사 여부 불명", listing, sic)
    if ticker != submission.get("tickers", [None])[0] or len(submission.get("exchanges", [])) == 0:
        return _stop(ticker, "적합성 확인 실패: 보통주 대표 티커 확인 불가", listing, sic)
    if not re.fullmatch(r"[A-Z][A-Z0-9]*", ticker):
        return _stop(ticker, "적합성 확인 실패: 증권 종류 확인 불가", listing, sic)
    if submission.get("fiscalYearEnd") is None:
        return _stop(ticker, "적합성 확인 실패: 회계연도 말일 없음", listing, sic)

    spac_ends = []
    for old in submission.get("formerNames", []):
        if re.search(r"\b(?:Acquisition|Blank Check)\b", old.get("name", ""), re.I):
            try:
                spac_ends.append(date.fromisoformat(old["to"][:10]))
            except (KeyError, ValueError, TypeError):
                return _stop(ticker, "적합성 확인 실패: SPAC 합병 시점 불명", listing, sic)
    merger_date = max(spac_ends) if spac_ends else None
    years = set()
    unknown_annual_dates = False
    for row in rows:
        if row["form"] != "10-K":
            continue
        try:
            period = date.fromisoformat(row["reportDate"])
            filed = date.fromisoformat(row["filingDate"])
        except (TypeError, ValueError):
            unknown_annual_dates = True
            continue
        if filed <= as_of and period <= as_of and (merger_date is None or period > merger_date):
            years.add(period.year)
    if len(years) < 4:
        if unknown_annual_dates:
            return _stop(ticker, "적합성 확인 실패: 10-K 회계연도 확인 불가", listing, sic)
        return _stop(ticker, "지원 범위 밖: 신규 상장사는 v1에서 지원하지 않음 (합병·상장 후 10-K 회계연도 4개 미만)", listing, sic)
    return S0Result(ticker, True, "S0 통과", str(listing["cik"]).zfill(10), listing.get("name"),
                    listing.get("exchange"), sic, tuple(sorted(years)), "대표 상장주식(보통주 여부 후속 확인)")


def _get_json(url):
    request = urllib.request.Request(url, headers={"User-Agent": sec_user_agent()})
    with urllib.request.urlopen(request, timeout=20) as response:
        return json.load(response)


def load_s0(ticker, get_json=None):
    """Fetch only the SEC listing and submissions metadata needed for S0."""
    ticker = ticker.upper()
    get_json = get_json or _get_json
    try:
        ticker_map = get_json(TICKERS_URL)
        fields = ticker_map["fields"]
        matches = [dict(zip(fields, row)) for row in ticker_map["data"] if row[fields.index("ticker")] == ticker]
        if len(matches) != 1:
            return _stop(ticker, "적합성 확인 실패: 티커 식별 불가")
        listing = matches[0]
        submission = get_json(SUBMISSIONS_URL.format(cik=listing["cik"]))
        history = []
        # Old metadata shards are fetched only if recent filings do not cover four annual years.
        recent = _rows(submission.get("filings", {}).get("recent", {}))
        annual_years = {row["reportDate"][:4] for row in recent if row.get("form") == "10-K" and row.get("reportDate")}
        if len(annual_years) < 4:
            for shard in submission.get("filings", {}).get("files", []):
                name = shard.get("name", "")
                if not re.fullmatch(r"CIK\d{10}-submissions-\d{3}\.json", name):
                    continue
                history.append(get_json(SUBMISSIONS_HISTORY_URL.format(name=name)))
                old_rows = _rows(history[-1].get("filings", history[-1]))
                annual_years.update(row["reportDate"][:4] for row in old_rows if row.get("form") == "10-K" and row.get("reportDate"))
                if len(annual_years) >= 4:
                    break
        return assess(ticker, listing, submission, history)
    except (OSError, TimeoutError, ValueError, KeyError, TypeError, IndexError, json.JSONDecodeError, RuntimeError):
        return _stop(ticker, "적합성 확인 실패: SEC 메타데이터 조회 실패")
