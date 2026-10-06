"""Conservative RKLB 2025 10-K phrase extraction; absent phrases stay absent."""

import html
import re


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
