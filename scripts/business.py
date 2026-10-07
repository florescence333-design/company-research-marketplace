"""Conservative RKLB 2025 10-K phrase extraction; absent phrases stay absent."""

import html
import re
from decimal import Decimal


FILING_URL = "https://www.sec.gov/Archives/edgar/data/1819994/000181999426000013/rklb-20251231.htm"
FILING_ACCESSION = "0001819994-26-000013"
FILING_DATE = "2026-02-26"


def extract_business_facts(raw: bytes) -> dict:
    text = html.unescape(re.sub(r"<[^>]+>", " ", raw.decode("utf-8")))
    text = re.sub(r"\s+", " ", text)
    facts = {}

    def add(fact_id, value, unit, location):
        facts[fact_id] = {"value": value, "unit": unit, "location": location}

    backlog = re.search(r"Our backlog increased from \$([\d,]+\.[\d]+) million.{0,80}?to \$([\d,]+\.[\d]+) million.{0,100}?of which \$([\d,]+\.[\d]+) million is related to space systems and \$([\d,]+\.[\d]+) million is related to launch services", text, re.I)
    if backlog:
        values = [int(round(float(value.replace(",", "")) * 1_000_000)) for value in backlog.groups()]
        if values[2] + values[3] == values[1]:
            add("backlog_fy2024", values[0], "USD", "Item 7 MD&A > Backlog")
            add("backlog_fy2025", values[1], "USD", "Item 7 MD&A > Backlog")
            add("backlog_space_fy2025", values[2], "USD", "Item 7 MD&A > Backlog")
            add("backlog_launch_fy2025", values[3], "USD", "Item 7 MD&A > Backlog")

    concentration = re.search(
        r"For the year ended December 31, 2025, our top five customers accounted for approximately (\d+)% of our revenues and our top five backlog customers accounted for approximately (\d+)% of our backlog in the aggregate as of December 31, 2025",
        text, re.I)
    if concentration:
        add("top5_revenue_share_approx_fy2025", int(concentration[1]), "%",
            "Item 1A Risk Factors > Customer Concentration")
        add("top5_backlog_share_approx_fy2025", int(concentration[2]), "%",
            "Item 1A Risk Factors > Customer Concentration")

    employees = re.search(r"As of December 31, 2025, we had over ([\d,]+) full-time permanent employees", text, re.I)
    if employees:
        add("employees_min_fy2025", int(employees[1].replace(",", "")), "people", "Item 1 Business > Human Capital")

    launches = re.search(r"(\d+) successful launches and over (\d+) spacecraft deployed as of December 31, 2025", text, re.I)
    if launches:
        add("successful_launches_fy2025", int(launches[1]), "launches", "Item 1 Business > Growth Strategy")
        add("spacecraft_min_fy2025", int(launches[2]), "spacecraft", "Item 1 Business > Growth Strategy")

    neutron = re.search(r"Neutron.{0,250}?payloads up to ([\d,]+) kg for reusable configuration launches", text, re.I)
    if neutron:
        add("neutron_planned_capacity_kg", int(neutron[1].replace(",", "")), "kg", "Item 1 Business > Neutron")

    segment = re.search(r"Year Ended December 31, 2025 Launch Services Space Systems Total Revenues by recognition model.{0,400}?Total revenue by recognition model\s+\$\s*([\d,]+)\s+\$\s*([\d,]+)\s+\$\s*([\d,]+)", text, re.I)
    if segment:
        launch, space, total = [int(value.replace(",", "")) * 1000 for value in segment.groups()]
        if launch + space == total:
            add("launch_revenue_fy2025", launch, "USD", "Note 4 Revenue > Revenues by recognition model")
            add("space_revenue_fy2025", space, "USD", "Note 4 Revenue > Revenues by recognition model")

    return facts


def _visible_text(raw: bytes) -> str:
    """Keep table cell order while removing markup and hidden XBRL tags."""
    content = raw.decode("utf-8", errors="replace")
    content = re.sub(r"<(?:script|style|ix:header)\b[^>]*>.*?</(?:script|style|ix:header)\s*>",
                     " ", content, flags=re.I | re.S)
    return re.sub(r"\s+", " ", html.unescape(re.sub(r"<[^>]+>", " ", content)))


def _note(text: str, heading: str, next_heading: str) -> str:
    start = re.search(heading, text, re.I)
    if not start:
        return ""
    end = re.search(next_heading, text[start.end():], re.I)
    return text[start.start():start.end() + end.start()] if end else ""


def _money(amount: str, scale: int) -> int:
    return int(Decimal(amount.replace(",", "")) * scale)


def extract_company_filing_facts(ticker: str, filing: dict) -> dict:
    """Extract only explicitly reviewed company, form and report-period phrases."""
    key = (ticker, filing.get("form"), filing.get("report_date"))
    if key not in {("VRT", "10-K", "2025-12-31"), ("VRT", "10-Q", "2026-06-30"),
                   ("MSFT", "10-K", "2026-06-30"), ("MSFT", "10-Q", "2026-03-31")}:
        return {}
    text = _visible_text(filing["raw"])
    if (ticker == "VRT" and "Vertiv" not in text) or (ticker == "MSFT" and "Microsoft" not in text):
        return {}
    facts = {}

    def add(fact_id, value, unit, category, location, excerpt):
        facts[fact_id] = {"value": value, "unit": unit, "category": category,
                          "location": location, "excerpt": excerpt[:500]}

    if key == ("VRT", "10-K", "2025-12-31"):
        match = re.search(r"Backlog\s+Vertiv.s estimated combined order backlog was \$\s*([\d,.]+) billion and \$\s*([\d,.]+) billion as of December 31, 2025 and 2024, respectively", text, re.I)
        if match:
            for year, amount in zip((2025, 2024), match.groups()):
                add(f"backlog_fy{year}", _money(amount, 1_000_000_000),
                    "USD", "business", "Item 1 Business > Backlog", match.group())
        match = re.search(r"Sales and Marketing.{0,1600}?Our primary selling method is direct sales, and we have approximately ([\d,]+) salespeople", text, re.I)
        if match:
            add("salespeople_approx_fy2025", int(match[1].replace(",", "")), "people",
                "customer", "Item 1 Business > Sales and Marketing", match.group()[-300:])
        debt = _note(text, r"\(6\)\s+DEBT\s+Long-term debt", r"\(7\)\s+LEASES")
        if "December 31, 2025" in debt and "December 31, 2024" in debt:
            match = re.search(r"Total long-term debt, net of current portion\s*\$\s*([\d,]+\.\d+)\s*\$\s*[\d,]+\.\d+", debt, re.I)
            if match:
                add("long_term_debt_net_fy2025", _money(match[1], 1_000_000),
                    "USD", "debt", "Note 6 Debt > Long-term debt, net of current portion", match.group())
    elif key == ("VRT", "10-Q", "2026-06-30"):
        debt = _note(text, r"\(6\)\s+DEBT\s+Long-term debt", r"\(7\)\s+INCOME TAXES")
        if "June 30, 2026" in debt and "December 31, 2025" in debt:
            match = re.search(r"Total long-term debt, net of current portion\s*\$\s*([\d,]+\.\d+)\s*\$\s*[\d,]+\.\d+", debt, re.I)
            if match:
                add("long_term_debt_net_2026q2", _money(match[1], 1_000_000),
                    "USD", "debt", "Note 6 Debt > Long-term debt, net of current portion", match.group())
            match = re.search(r"Senior Notes\s+On\s+M\s*arch 3, 2026, Vertiv Holdings Co.{0,150}?issued \$\s*([\d,]+\.\d+) in aggregate principal amount of senior unsecured notes", debt, re.I)
            if match:
                add("senior_notes_issued_2026h1", _money(match[1], 1_000_000),
                    "USD", "one_off", "Note 6 Debt > Senior Notes issued March 3, 2026", match.group())
    elif key == ("MSFT", "10-K", "2026-06-30"):
        match = re.search(r"Revenue allocated to remaining performance obligations, which includes unearned revenue and amounts expected to be invoiced and recognized as revenue in future periods, was \$\s*([\d,]+) billion as of June 30, 2026", text, re.I)
        if match:
            add("remaining_performance_obligations_fy2026", int(match[1].replace(",", "")) * 1_000_000_000,
                "USD", "business", "Note 12 Unearned Revenue > Remaining performance obligations", match.group())
        match = re.search(r"No sales to an individual customer or country other than the United States accounted for more than (\d+)% of revenue for fiscal years 2026, 2025, or 2024", text, re.I)
        if match:
            add("individual_customer_revenue_ceiling_fy2026", int(match[1]), "%",
                "customer", "Note 18 Segment Information > Customer concentration", match.group())
        match = re.search(r"Current year net income and diluted EPS were positively impacted by net gains from investments in OpenAI, which resulted in an increase in net income and diluted EPS of \$\s*([\d,.]+) billion and \$\s*[\d.]+, respectively", text, re.I)
        if match:
            add("openai_net_income_impact_fy2026", _money(match[1], 1_000_000_000),
                "USD", "one_off", "Item 7 MD&A > OpenAI investment gains", match.group())
        debt = _note(text, r"NOTE 10\s*[—\-]\s*DEBT\s+The components of long-term debt", r"NOTE 11\s*[—\-]")
        if "June 30, 2026" in debt and "(In millions" in debt:
            match = re.search(r"\bTotal debt\s+([\d,]+)\s+[\d,]+\s+Current portion of long-term debt.*?Long-term debt\s*\$\s*([\d,]+)\s*\$\s*[\d,]+", debt, re.I)
            if match:
                add("total_debt_fy2026", int(match[1].replace(",", "")) * 1_000_000,
                    "USD", "debt", "Note 10 Debt > Total debt", match.group()[:250])
                add("long_term_debt_fy2026", int(match[2].replace(",", "")) * 1_000_000,
                    "USD", "debt", "Note 10 Debt > Long-term debt", match.group()[-250:])
    else:  # MSFT 2026-03-31 10-Q
        match = re.search(r"Revenue allocated to remaining performance obligations, which includes unearned revenue and amounts expected to be invoiced and recognized as revenue in future periods, was \$\s*([\d,]+) billion as of March 31, 2026", text, re.I)
        if match:
            add("remaining_performance_obligations_2026q3", int(match[1].replace(",", "")) * 1_000_000_000,
                "USD", "business", "Note 11 Unearned Revenue > Remaining performance obligations", match.group())
        debt = _note(text, r"NOTE 9\s*[—\-]\s*DEBT\s+The components of long-term debt", r"NOTE 10\s*[—\-]")
        if "March 31, 2026" in debt and "(In millions" in debt:
            match = re.search(r"\bTotal debt\s+([\d,]+)\s+[\d,]+\s+Current portion of long-term debt.*?Long-term debt\s*\$\s*([\d,]+)\s*\$\s*[\d,]+", debt, re.I)
            if match:
                add("total_debt_2026q3", int(match[1].replace(",", "")) * 1_000_000,
                    "USD", "debt", "Note 9 Debt > Total debt", match.group()[:250])
                add("long_term_debt_2026q3", int(match[2].replace(",", "")) * 1_000_000,
                    "USD", "debt", "Note 9 Debt > Long-term debt", match.group()[-250:])
    return facts
