"""Build and validate a sourced 16-section report from a SEC snapshot."""

import argparse
import json
from decimal import Decimal
from pathlib import Path

from jsonschema import Draft202012Validator


ROOT = Path(__file__).resolve().parents[1]
TEMPLATE = json.loads((ROOT / "template" / "sections.json").read_text(encoding="utf-8"))["sections"]
SCHEMA = json.loads((ROOT / "schemas" / "v1" / "report-items.schema.json").read_text(encoding="utf-8"))
STATUS_LABELS = {"complete": "작성 완료", "partial": "부분 작성", "unavailable": "자료 확인 대기"}


def section_status(item, *, verified=False):
    """Derive display status from evidence, prose, and successful validation."""
    sources = item.get("source_ids") or []
    if not sources:
        return "unavailable"
    body = item.get("body") or ""
    if body.strip() and "[해석]" in body and "반대 논거" in body and verified:
        return "complete"
    return "partial"


def recalculate_statuses(report, verified_ids=()):
    """Overwrite model supplied statuses for parents and nested sections."""
    verified_ids = set(verified_ids)
    for section in report.get("sections", []):
        for item in (section, *section.get("subsections", [])):
            item["status"] = section_status(item, verified=item.get("section_id") in verified_ids)
    return report


def build_report_items(bundle):
    meta = bundle["meta"]
    metrics = {m["metric_id"]: m for m in bundle["metrics"]["metrics"]}
    facts = {f["fact_id"]: f for f in bundle.get("extracted-facts", {}).get("facts", [])}
    sections = []

    def add(index, body, ids=(), fact_ids=()):
        used = [metrics[metric_id] for metric_id in ids if metric_id in metrics and metrics[metric_id]["status"] == "ok"]
        used_facts = [facts[fact_id] for fact_id in fact_ids if fact_id in facts]
        sections.append({"section_id": TEMPLATE[index - 1]["section_id"],
                         "title": TEMPLATE[index - 1]["title"],
                         "status": "partial" if used or used_facts else "unavailable",
                         "body": body, "metric_ids": [m["metric_id"] for m in used],
                         "fact_ids": [f["fact_id"] for f in used_facts],
                         "source_ids": list(dict.fromkeys([s for m in used for s in m.get("source_ids", [])]
                                                       + [f["source_id"] for f in used_facts]))})

    def amount(metric_id):
        metric = metrics.get(metric_id)
        return f"{metric['value']:,.0f} USD" if metric and metric["status"] == "ok" else "확인 불가"

    def growth(a, b):
        first, second = metrics.get(a), metrics.get(b)
        if not first or not second or first["status"] != "ok" or second["status"] != "ok" or second["value"] <= 0:
            return "확인 불가"
        value = (Decimal(str(first["value"])) / Decimal(str(second["value"])) - 1) * 100
        return f"{value:.1f}%"

    def fact_amount(fact_id, suffix=""):
        fact = facts.get(fact_id)
        return f"{fact['value']:,.0f}{suffix}" if fact else "확인 불가"

    def percentage(metric_id):
        metric = metrics.get(metric_id)
        return f"{metric['value']:.1f}%" if metric and metric["status"] == "ok" else "확인 불가"

    def backlog_growth():
        current, prior = facts.get("backlog_fy2025"), facts.get("backlog_fy2024")
        if not current or not prior or prior["value"] <= 0:
            return "확인 불가"
        return f"{(Decimal(current['value']) / Decimal(prior['value']) - 1) * 100:.1f}%"

    rev_ids = [key for key in sorted(metrics, reverse=True) if key.startswith("revenue_fy")]
    rev_current = rev_ids[0] if rev_ids else None
    rev_prior = rev_ids[1] if len(rev_ids) > 1 else None
    year = rev_current[-4:] if rev_current else "최근"
    add(1, f"{meta.get('company_name', 'RKLB')} · 티커 RKLB · CIK {meta['cik']}. SEC Company Facts와 2025년 10-K에서 확인한 내용만 담은 부분 분석이다.", [rev_current] if rev_current else [])
    growth_ids = sorted(key for key in metrics if key.startswith("revenue_growth_fy") and metrics[key]["status"] == "ok")
    growth_history = ", ".join(f"{key[-4:]}년 {percentage(key)}" for key in growth_ids)
    cagr_text = f" 3년 CAGR {percentage('revenue_cagr_3y')}." if metrics.get("revenue_cagr_3y", {}).get("status") == "ok" else ""
    quarter = metrics.get("revenue_quarter_latest", {})
    quarter_ids = []
    quarter_text = ""
    if quarter.get("status") == "ok":
        quarter_ids.append("revenue_quarter_latest")
        quarter_label = "계산한 단독 분기" if quarter.get("calculation") else "단독 분기"
        quarter_text = (f" {quarter['period_start']}~{quarter['period_end']} {quarter_label} 매출 "
                        f"{amount('revenue_quarter_latest')}.")
        if metrics.get("revenue_quarter_yoy", {}).get("status") == "ok":
            quarter_ids.extend(("revenue_quarter_prior_year", "revenue_quarter_yoy"))
            quarter_text += f" 전년 같은 분기 대비 {percentage('revenue_quarter_yoy')}."
    add(2, f"{year}년 매출 {amount(rev_current)}. 연도별 매출 성장률: {growth_history or '확인 불가'}.{cagr_text}{quarter_text} 산업 전체 성장률·TAM과 메가트렌드 적합성은 자료 확인 대기.", [x for x in (rev_current, rev_prior, *growth_ids, "revenue_cagr_3y", *quarter_ids) if x])
    add(3, "규제·경쟁사·Porter 5 Forces를 판단할 검증 자료 확인 대기.")
    segment_facts = [f for f in ("launch_revenue_fy2025", "space_revenue_fy2025") if f in facts]
    segment_body = (f"2025년 Launch Services 매출 {fact_amount('launch_revenue_fy2025', ' USD')}, "
                    f"Space Systems 매출 {fact_amount('space_revenue_fy2025', ' USD')}. "
                    "두 사업부 합계는 총매출과 대조했다. 세부 계약 구조는 자료 확인 대기.") if len(segment_facts) == 2 else "사업부별 매출과 계약 구조는 공시 본문 확인 대기."
    add(4, f"연간 총매출은 {amount(rev_current)}. {segment_body}", [rev_current] if rev_current else [], segment_facts)
    concentration_ids = [f for f in ("top5_revenue_share_approx_fy2025", "top5_backlog_share_approx_fy2025") if f in facts]
    concentration_text = (f"2025년 상위 5개 고객은 매출의 약 {fact_amount('top5_revenue_share_approx_fy2025')}%, "
                          f"연말 상위 5개 수주 고객은 수주잔고의 약 {fact_amount('top5_backlog_share_approx_fy2025')}%를 차지했다. "
                          "서로 다른 기준의 고객군·기간이며 수주잔고는 매출이 아니다. ") if len(concentration_ids) == 2 else ""
    add(5, concentration_text + "고객군·유지율·LTV/CAC를 확인할 추가 자료는 확인 대기.", fact_ids=concentration_ids)
    launch_facts = [f for f in ("successful_launches_fy2025", "spacecraft_min_fy2025") if f in facts]
    launch_body = (f"2025년 말 누적 성공 발사 {fact_amount('successful_launches_fy2025')}회, "
                   f"배치 우주선 {fact_amount('spacecraft_min_fy2025')}기 초과. "
                   "이는 누적 실적이며 2025년 단일 연도 실적이 아니다. 시장 재편 능력 평가는 자료 확인 대기.") if len(launch_facts) == 2 else "혁신 성과와 시장 재편 능력을 평가할 검증 자료 확인 대기."
    add(6, launch_body, fact_ids=launch_facts)
    neutron_fact = ["neutron_planned_capacity_kg"] if "neutron_planned_capacity_kg" in facts else []
    neutron_body = (f"개발 중인 Neutron의 재사용 구성 계획 탑재량은 최대 {fact_amount('neutron_planned_capacity_kg')} kg이다. "
                    "계획치이며 실현된 성능으로 보지 않는다. R&D 투자 효과는 자료 확인 대기.") if neutron_fact else "기술력·R&D의 성과와 투자 규모를 판단할 검증 자료 확인 대기."
    add(7, neutron_body, fact_ids=neutron_fact)
    add(8, "데이터 우위 또는 AI 경쟁력을 확인할 검증 자료 확인 대기.")
    op_current = f"operating_income_fy{year}"
    backlog_facts = [f for f in ("backlog_fy2024", "backlog_fy2025") if f in facts]
    backlog_body = (f"2025년 말 수주잔고는 {fact_amount('backlog_fy2025', ' USD')}로 전년 말 대비 {backlog_growth()} 증가했다. "
                    "수주잔고는 확정 매출이 아니다. ") if len(backlog_facts) == 2 else ""
    add(9, f"매출은 직전 연도 대비 {growth(rev_current, rev_prior)} 변했으며, {year}년 영업손익은 {amount(op_current)}. {backlog_body}규모의 경제 여부는 단정할 수 없다.", [x for x in (rev_current, rev_prior, op_current) if x], backlog_facts)
    add(10, "독점력·진입장벽의 검증 자료 확인 대기.")
    employee_fact = ["employees_min_fy2025"] if "employees_min_fy2025" in facts else []
    employee_body = (f"2025년 말 정규직 직원은 {fact_amount('employees_min_fy2025')}명 초과. "
                     "인재 유지·조직문화 평가는 자료 확인 대기.") if employee_fact else "창업자·인재·조직문화의 검증 자료 확인 대기."
    add(11, employee_body, fact_ids=employee_fact)
    financial_ids = [key for key in sorted(metrics) if key.startswith(("revenue_fy", "revenue_growth_fy", "operating_income_fy", "operating_margin_fy", "net_income_fy", "operating_cash_flow_fy", "capex_fy", "free_cash_flow_fy"))] + ["revenue_cagr_3y", *quarter_ids, "operating_income_quarter_latest", "net_income_quarter_latest", "eps_annual", "eps_quarter_latest", "revenue_ttm", "operating_income_ttm", "net_income_ttm", "cash", "assets", "liabilities", "stockholders_equity", "liabilities_to_equity", "eps_ttm"]
    financial_lines = []
    for metric_id in financial_ids:
        metric = metrics.get(metric_id)
        if metric and metric["status"] == "ok":
            value = f"{metric['value']:,.2f}" if metric_id == "eps_ttm" else f"{metric['value']:,.1f}" if metric["unit"] == "%" else f"{metric['value']:,.0f}"
            suffix = " (계산: 원본 출처 ID 참조)" if metric.get("calculation") else " (근사)" if metric["approximate"] else ""
            financial_lines.append(f"- {metric_id}: {value} {metric['unit']}{suffix}; 기간 종료 {metric['period_end']}")
    add(12, "SEC 공시 태그와 그 값에서 코드로 계산한 지표:\n" + "\n".join(financial_lines) + "\nCapEx는 지출액을 양수로 표시하며 FCF는 영업현금흐름에서 CapEx를 뺀 값이다. 부채비율의 분자는 총부채이며 총차입금과 다르다. 회계 품질 종합 평가는 수행하지 않았다.", financial_ids)
    ocf_current = f"operating_cash_flow_fy{year}"
    add(13, f"{year}년 영업현금흐름은 {amount(ocf_current)}. 현금 소진 지속성은 별도 기간·자금조달·약정 확인이 필요하며 강제 회피 판정은 수행하지 않는다.", [ocf_current])
    add(14, "주가·기업가치 입력과 역DCF 세부 규칙이 없어 밸류에이션 계산·가격 판정을 보류한다.")
    add(15, f"후속 모니터링 항목: 매출({amount(rev_current)}), 영업손익({amount(op_current)}), 영업현금흐름({amount(ocf_current)}), 수주잔고({fact_amount('backlog_fy2025', ' USD')}). 목표치·확률 시나리오는 자료 확인 대기.", [x for x in (rev_current, op_current, ocf_current) if x], ["backlog_fy2025"] if "backlog_fy2025" in facts else [])
    add(16, f"확인된 최근 연간 매출은 {amount(rev_current)}. 나머지 사업·가격 평가와 투자 프레임워크 v2는 입력 대기. 최종 판정: 판정 보류 (v0.1).", [rev_current] if rev_current else [])
    return recalculate_statuses({"schema_version": "v1-draft", "run_id": meta["run_id"],
                                 "data_snapshot_id": meta["data_snapshot_id"], "sections": sections})


def validate_report_items(report, bundle):
    errors = [f"schema: {error.message}" for error in Draft202012Validator(SCHEMA).iter_errors(report)]
    if report.get("run_id") != bundle["meta"]["run_id"] or report.get("data_snapshot_id") != bundle["meta"]["data_snapshot_id"]:
        errors.append("보고서 실행·스냅샷 ID 불일치")
    source_ids = {source["source_id"] for source in bundle["sources"]["sources"]}
    metric_ids = {metric["metric_id"] for metric in bundle["metrics"]["metrics"]}
    fact_ids = {fact["fact_id"] for fact in bundle.get("extracted-facts", {}).get("facts", [])}
    for index, (expected, actual) in enumerate(zip(TEMPLATE, report.get("sections", []))):
        if (actual.get("section_id"), actual.get("title")) != (expected["section_id"], expected["title"]):
            errors.append(f"섹션 {index + 1} ID·제목·순서 불일치")
        seen = set()
        for item in [actual, *actual.get("subsections", [])]:
            sid = item.get("section_id", "")
            if sid in seen or (item is not actual and not sid.startswith(actual.get("section_id", "") + "-")):
                errors.append(f"섹션 {index + 1} 하위 ID 중복 또는 부모 불일치")
            seen.add(sid)
            if set(item.get("source_ids", [])) - source_ids or set(item.get("metric_ids", [])) - metric_ids or set(item.get("fact_ids", [])) - fact_ids:
                errors.append(f"섹션 {sid} 알 수 없는 출처·지표 ID")
            if item.get("status") == "complete" and section_status(item, verified=True) != "complete":
                errors.append(f"섹션 {sid} 작성 완료 조건 미충족")
    if len(report.get("sections", [])) != len(TEMPLATE):
        errors.append("16개 섹션 수 불일치")
    return errors


def render_report(report, bundle):
    lines = [f"# {bundle['meta']['ticker']} 기업분석 — v0.1 부분 보고서", "",
             f"기준시각: {bundle['meta']['analysis_as_of']} · 데이터 스냅샷: {bundle['meta']['data_snapshot_id']}",
             "이 보고서는 SEC 공시 수치 중심의 초기 결과다. 자료 확인 대기 섹션은 결론으로 간주하지 않는다.", ""]
    if bundle["meta"].get("filing_body_basis"):
        lines.extend([f"공시 본문 한계: {bundle['meta']['filing_body_basis']}", ""])
    for section in report["sections"]:
        for item, level in [(section, "##"), *[(sub, "###") for sub in section.get("subsections", [])]]:
            lines.extend([f"{level} {item['section_id']} {item['title']}", "",
                          f"상태: {STATUS_LABELS[item['status']]}", "",
                          item["body"], ""])
            if item["source_ids"]:
                lines.extend(["출처 ID: " + ", ".join(item["source_ids"]), ""])
    lines.extend(["---", "", "최종 판정: **판정 보류 (v0.1)**", ""])
    return "\n".join(lines)


def write_report(folder):
    bundle = {name: json.loads((folder / f"{name}.json").read_text(encoding="utf-8"))
              for name in ("meta", "metrics", "sources", "decision")}
    extracted_path = folder / "extracted-facts.json"
    if extracted_path.exists():
        bundle["extracted-facts"] = json.loads(extracted_path.read_text(encoding="utf-8"))
    report = build_report_items(bundle)
    errors = validate_report_items(report, bundle)
    if errors:
        raise ValueError("; ".join(errors))
    (folder / "report-items.json").write_text(json.dumps(report, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    (folder / "report.md").write_text(render_report(report, bundle), encoding="utf-8")


if __name__ == "__main__":
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("bundle", type=Path)
    args = parser.parse_args()
    write_report(args.bundle)
    print(args.bundle / "report.md")
