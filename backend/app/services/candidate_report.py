"""F2.09: side-by-side candidate comparison and custom Excel/PDF export.

Both read the same data: for every application of a position, its latest
completed assessment made with the position's current approved criteria
version and the application's current profile. Comparing or exporting rows
assessed against different rubrics would be misleading, so stale or
unassessed applications are reported, never mixed in.

Privacy: contact details (email, phone, address, links) are never read here,
so they cannot reach a comparison payload or an exported file. Only
whitelisted profile fact keys are used. Text that came from CVs is guarded
against spreadsheet formula injection.
"""
from __future__ import annotations

import io
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Iterable

from sqlalchemy import bindparam, text

from app.core.config import settings

MIN_COMPARE, MAX_COMPARE = 2, 4

# Outcome strength for "best per criterion". UNCLEAR is "no evidence yet",
# not a weak result, so it is never ranked against known outcomes.
OUTCOME_ORDER = {"STRONG_MATCH": 3, "MATCH": 2, "NO_MATCH": 0}

COLUMNS = ("candidate", "rank", "application_status", "matching_status", "score", "coverage",
           "criteria", "evidence", "profile")
DEFAULT_COLUMNS = ("candidate", "rank", "application_status", "matching_status", "score", "coverage", "criteria")

LABELS: dict[str, dict[str, str]] = {
    "vi": {
        "title": "Báo cáo ứng viên", "position": "Vị trí", "code": "Mã vị trí", "exported_at": "Thời điểm xuất",
        "criteria_version": "Phiên bản tiêu chí", "rows": "Số hồ sơ", "note": "Ghi chú",
        "privacy_note": "Không chứa thông tin liên hệ. Điểm \"một phần\" chỉ tính trên tiêu chí đã có bằng chứng; xem cùng độ phủ.",
        "candidate": "Ứng viên", "reference": "Mã hồ sơ", "rank": "Thứ hạng", "application_status": "Trạng thái hồ sơ",
        "matching_status": "Kết luận AI", "score": "Điểm", "coverage": "Độ phủ bằng chứng", "criterion": "Tiêu chí",
        "category": "Loại", "outcome": "Kết quả", "quote": "Trích dẫn bằng chứng", "page": "Trang",
        "education": "Học vấn", "work": "Kinh nghiệm", "certifications": "Chứng chỉ", "languages": "Ngoại ngữ",
        "evidence_sheet": "Bằng chứng", "candidates_sheet": "Ứng viên", "info_sheet": "Thông tin",
        "unverified": "(chưa xác minh)", "summary": "Tóm tắt",
        "MUST_HAVE": "Bắt buộc", "NICE_TO_HAVE": "Ưu tiên",
        "STRONG_MATCH": "Đáp ứng rõ", "MATCH": "Đáp ứng", "NO_MATCH": "Chưa đáp ứng", "UNCLEAR": "Chưa rõ",
        "MEETS_MANDATORY": "Đáp ứng bắt buộc", "NEEDS_HR_VERIFICATION": "Cần HR xác minh",
        "POSSIBLE_MISMATCH": "Có dấu hiệu chưa đáp ứng", "NOT_ASSESSED": "Chưa đánh giá",
        "NEW": "Mới", "IN_REVIEW": "Đang xem xét", "SHORTLIST": "Shortlist", "INTERVIEW": "Phỏng vấn",
        "OFFERED": "Đã gửi offer", "ACCEPTED": "Nhận offer", "REJECTED_SCREENING": "Loại vòng sàng lọc",
        "REJECTED_INTERVIEW": "Loại sau phỏng vấn", "WITHDRAWN": "Rút hồ sơ",
    },
    "en": {
        "title": "Candidate report", "position": "Position", "code": "Position code", "exported_at": "Exported at",
        "criteria_version": "Criteria version", "rows": "Applications", "note": "Note",
        "privacy_note": "No contact details. A \"partial\" score only covers criteria with evidence; read it with coverage.",
        "candidate": "Candidate", "reference": "Application ref", "rank": "Rank", "application_status": "Application status",
        "matching_status": "AI conclusion", "score": "Score", "coverage": "Evidence coverage", "criterion": "Criterion",
        "category": "Type", "outcome": "Outcome", "quote": "Evidence quote", "page": "Page",
        "education": "Education", "work": "Experience", "certifications": "Certifications", "languages": "Languages",
        "evidence_sheet": "Evidence", "candidates_sheet": "Candidates", "info_sheet": "Info",
        "unverified": "(unverified)", "summary": "Summary",
        "MUST_HAVE": "Mandatory", "NICE_TO_HAVE": "Preferred",
        "STRONG_MATCH": "Strong match", "MATCH": "Match", "NO_MATCH": "Not met", "UNCLEAR": "Unclear",
        "MEETS_MANDATORY": "Meets mandatory", "NEEDS_HR_VERIFICATION": "Needs HR verification",
        "POSSIBLE_MISMATCH": "Possible mismatch", "NOT_ASSESSED": "Not assessed",
        "NEW": "New", "IN_REVIEW": "In review", "SHORTLIST": "Shortlist", "INTERVIEW": "Interview",
        "OFFERED": "Offered", "ACCEPTED": "Accepted", "REJECTED_SCREENING": "Rejected (screening)",
        "REJECTED_INTERVIEW": "Rejected (interview)", "WITHDRAWN": "Withdrawn",
    },
}


class ReportError(Exception):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.message, self.status_code = message, status_code


# ------------------------------------------------------------------ data
def _current_criteria_version(db, position_id: str) -> str | None:
    value = db.execute(text("""
        SELECT criteria_version_id FROM app_private.criteria_versions
        WHERE position_id = :p AND status = 'APPROVED'
          AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                               WHERE position_id = :p ORDER BY version_number DESC LIMIT 1)
        ORDER BY version_number DESC LIMIT 1
    """), {"p": position_id}).scalar_one_or_none()
    return str(value) if value else None


def candidate_rows(db, position_id: str, criteria_version_id: str,
                   application_ids: Iterable[str] | None = None) -> list[dict]:
    """Current assessment per application (no contact columns are selected)."""
    ids = [str(i) for i in application_ids] if application_ids is not None else None
    query = """
        WITH latest AS (
            SELECT DISTINCT ON (ar.application_id) ar.application_id, ar.assessment_id, ar.matching_status,
                   ar.matching_score, ar.evidence_coverage, ar.profile_version_id
            FROM app_private.assessment_runs ar
            JOIN app_private.applications a ON a.application_id = ar.application_id
            WHERE a.position_id = :p AND ar.status = 'COMPLETED' AND ar.criteria_version_id = :cv
              AND ar.profile_version_id = (SELECT profile_version_id FROM app_private.profile_versions
                  WHERE application_id = ar.application_id AND status = 'COMPLETED'
                  ORDER BY version_number DESC LIMIT 1)
              {filter}
            ORDER BY ar.application_id, ar.completed_at DESC NULLS LAST, ar.created_at DESC
        ), run AS (
            SELECT ranking_run_id FROM app_private.ranking_runs
            WHERE position_id = :p AND status = 'COMPLETED' AND criteria_version_id = :cv
            ORDER BY created_at DESC, ranking_run_id DESC LIMIT 1
        )
        SELECT a.application_id, a.application_status, a.created_at,
               COALESCE(NULLIF(btrim(i.display_name), ''), '') AS candidate_name,
               l.assessment_id, l.profile_version_id,
               COALESCE(ri.ranking_status, l.matching_status, 'NOT_ASSESSED') AS matching_status,
               l.matching_score, l.evidence_coverage, ri.rank_number
        FROM latest l
        JOIN app_private.applications a ON a.application_id = l.application_id
        LEFT JOIN app_private.application_identities i ON i.application_id = a.application_id
        LEFT JOIN app_private.ranking_items ri ON ri.assessment_id = l.assessment_id
             AND ri.ranking_run_id = (SELECT ranking_run_id FROM run)
        ORDER BY ri.rank_number ASC NULLS LAST, l.matching_score DESC NULLS LAST, a.created_at, a.application_id
    """
    params: dict[str, Any] = {"p": position_id, "cv": criteria_version_id}
    stmt = text(query.format(filter="AND ar.application_id IN :ids" if ids is not None else ""))
    if ids is not None:
        if not ids:
            return []
        stmt = stmt.bindparams(bindparam("ids", expanding=True))
        params["ids"] = ids
    rows = []
    for row in db.execute(stmt, params).mappings():
        item = dict(row)
        for key in ("matching_score", "evidence_coverage"):
            if item[key] is not None:
                item[key] = float(item[key])
        coverage = item["evidence_coverage"] or 0
        item["needs_verification"] = (item["matching_status"] == "NEEDS_HR_VERIFICATION"
                                      or coverage < settings.MIN_EVIDENCE_COVERAGE)
        item["reference"] = str(item["application_id"])[:8]
        rows.append(item)
    return rows


def _criteria(db, criteria_version_id: str) -> list[dict]:
    rows = db.execute(text("""
        SELECT c.criterion_id, c.name, c.category, c.display_order,
               (CASE WHEN c.category = 'MUST_HAVE' THEN cv.mandatory_weight_total
                     ELSE cv.nice_to_have_weight_total END) * c.weight_in_group / 100.0 AS effective_weight
        FROM app_private.criteria_items c
        JOIN app_private.criteria_versions cv ON cv.criteria_version_id = c.criteria_version_id
        WHERE c.criteria_version_id = :cv
        ORDER BY CASE c.category WHEN 'MUST_HAVE' THEN 0 ELSE 1 END, c.display_order, c.criterion_id
    """), {"cv": criteria_version_id}).mappings().all()
    return [{**dict(r), "criterion_id": str(r["criterion_id"]),
             "effective_weight": round(float(r["effective_weight"]), 1) if r["effective_weight"] is not None else None}
            for r in rows]


def _results(db, assessment_ids: list[str], with_evidence: bool) -> dict[str, dict[str, dict]]:
    """assessment_id -> criterion_id -> result (+ evidence quotes)."""
    if not assessment_ids:
        return {}
    rows = db.execute(text("""
        SELECT r.result_id, r.assessment_id, r.criterion_id, r.outcome, r.score, r.requires_hr_verification
        FROM app_private.criterion_assessment_results r WHERE r.assessment_id IN :ids
    """).bindparams(bindparam("ids", expanding=True)), {"ids": assessment_ids}).mappings().all()
    evidence: dict[str, list[dict]] = {}
    if with_evidence and rows:
        for e in db.execute(text("""
            SELECT criterion_result_id, verbatim_quote, page_number, verification_status
            FROM app_private.evidence_items WHERE criterion_result_id IN :ids AND btrim(verbatim_quote) <> ''
              -- Only quotes verified to exist in the CV text; a failed check may be
              -- model output (even profile JSON) and would mislead a reader.
              AND verification_status = 'VERIFIED'
            ORDER BY created_at, evidence_id
        """).bindparams(bindparam("ids", expanding=True)), {"ids": [str(r["result_id"]) for r in rows]}).mappings():
            evidence.setdefault(str(e["criterion_result_id"]), []).append({
                "quote": e["verbatim_quote"], "page_number": e["page_number"],
                "verified": e["verification_status"] == "VERIFIED"})
    out: dict[str, dict[str, dict]] = {}
    for r in rows:
        out.setdefault(str(r["assessment_id"]), {})[str(r["criterion_id"])] = {
            "outcome": r["outcome"], "score": float(r["score"]) if r["score"] is not None else None,
            "requires_verification": bool(r["requires_hr_verification"]),
            "evidence": evidence.get(str(r["result_id"]), [])[:3] if with_evidence else []}
    return out


# Only these keys of free-form profile facts are shown; identity-like keys
# (email, phone, address, links, birth date...) are never read.
_FACT_KEYS = {
    "EDUCATION": ("degree", "field_of_study", "major", "institution", "school", "year", "years",
                  "graduation_year", "end_date", "description"),
    "WORK_EXPERIENCE": ("job_title", "title", "role", "position", "company", "organization", "employer",
                        "start_date", "end_date", "duration", "description"),
    "CERTIFICATION": ("name", "title", "issuer", "year", "date"),
    "LANGUAGE": ("name", "language", "level", "proficiency", "score", "certificate"),
}
_FACT_GROUP = {"EDUCATION": "education", "WORK_EXPERIENCE": "work", "CERTIFICATION": "certifications",
               "LANGUAGE": "languages"}


def _fact_label(fact_type: str, value: Any) -> str:
    if isinstance(value, str):
        return value.strip()[:160]
    if not isinstance(value, dict):
        return ""
    keys = _FACT_KEYS[fact_type]
    if fact_type == "WORK_EXPERIENCE":
        head = next((str(value[k]) for k in ("job_title", "title", "role", "position") if value.get(k)), "")
        org = next((str(value[k]) for k in ("company", "organization", "employer") if value.get(k)), "")
        dates = " – ".join(str(value[k]) for k in ("start_date", "end_date") if value.get(k)) or str(value.get("duration") or "")
        label = ", ".join(p for p in (head, org) if p) + (f" ({dates})" if dates else "")
    elif fact_type == "EDUCATION":
        head = next((str(value[k]) for k in ("degree", "field_of_study", "major") if value.get(k)), "")
        org = next((str(value[k]) for k in ("institution", "school") if value.get(k)), "")
        year = next((str(value[k]) for k in ("year", "years", "graduation_year", "end_date") if value.get(k)), "")
        label = ", ".join(p for p in (head, org) if p) + (f" ({year})" if year else "")
    else:
        label = " – ".join(str(value[k]) for k in keys if value.get(k) and k != "description")
    if not label.strip():
        label = str(value.get("description") or "")
    return " ".join(label.split())[:160]


def _profiles(db, profile_version_ids: list[str]) -> dict[str, dict[str, list[str]]]:
    if not profile_version_ids:
        return {}
    out: dict[str, dict[str, list[str]]] = {}
    for row in db.execute(text("""
        SELECT profile_version_id, fact_type, fact_value FROM app_private.profile_facts
        WHERE profile_version_id IN :ids AND fact_type IN ('EDUCATION','WORK_EXPERIENCE','CERTIFICATION','LANGUAGE')
        ORDER BY profile_version_id, fact_type, fact_id
    """).bindparams(bindparam("ids", expanding=True)), {"ids": profile_version_ids}).mappings():
        label = _fact_label(row["fact_type"], row["fact_value"])
        group = out.setdefault(str(row["profile_version_id"]),
                               {"education": [], "work": [], "certifications": [], "languages": []})
        bucket = group[_FACT_GROUP[row["fact_type"]]]
        if label and label not in bucket and len(bucket) < 5:
            bucket.append(label)
    return out


def _position(db, position_id: str) -> dict:
    row = db.execute(text("SELECT position_id, title, position_code FROM app_private.positions WHERE position_id = :p"),
                     {"p": position_id}).mappings().first()
    if not row:
        raise ReportError("Không tìm thấy vị trí", 404)
    return {"position_id": str(row["position_id"]), "title": row["title"], "position_code": row["position_code"]}


# ------------------------------------------------------------ comparison
def best_by_criterion(criteria: list[dict], candidates: list[dict]) -> dict[str, list[str]]:
    """Candidates with the strongest known outcome per criterion, only where
    candidates actually differ (a tie across everyone highlights nobody)."""
    best: dict[str, list[str]] = {}
    for criterion in criteria:
        cid = criterion["criterion_id"]
        known = {c["application_id"]: OUTCOME_ORDER[c["results"][cid]["outcome"]]
                 for c in candidates
                 if cid in c["results"] and c["results"][cid]["outcome"] in OUTCOME_ORDER}
        if not known:
            continue
        top = max(known.values())
        winners = [app for app, value in known.items() if value == top]
        if top > 0 and len(winners) < len(candidates):
            best[cid] = winners
    return best


def build_comparison(db, position_id: str, application_ids: list[str]) -> dict:
    ids = list(dict.fromkeys(str(i) for i in application_ids))
    if not MIN_COMPARE <= len(ids) <= MAX_COMPARE:
        raise ReportError(f"Chọn từ {MIN_COMPARE} đến {MAX_COMPARE} hồ sơ để so sánh")
    position = _position(db, position_id)
    criteria_version_id = _current_criteria_version(db, position_id)
    if not criteria_version_id:
        raise ReportError("Vị trí chưa có bộ tiêu chí đã duyệt", 409)
    belongs = {str(r[0]) for r in db.execute(text(
        "SELECT application_id FROM app_private.applications WHERE position_id = :p AND application_id IN :ids"
    ).bindparams(bindparam("ids", expanding=True)), {"p": position_id, "ids": ids})}
    if belongs != set(ids):
        raise ReportError("Có hồ sơ không thuộc vị trí này", 404)
    rows = candidate_rows(db, position_id, criteria_version_id, ids)
    missing = len(ids) - len(rows)
    if missing:
        raise ReportError(f"{missing} hồ sơ chưa được đánh giá theo bộ tiêu chí hiện tại; "
                          "hãy chạy đánh giá lại trước khi so sánh", 409)
    criteria = _criteria(db, criteria_version_id)
    results = _results(db, [str(r["assessment_id"]) for r in rows], with_evidence=True)
    profiles = _profiles(db, [str(r["profile_version_id"]) for r in rows])
    candidates = []
    for row in sorted(rows, key=lambda r: ids.index(str(r["application_id"]))):
        res = results.get(str(row["assessment_id"]), {})
        candidates.append({
            "application_id": str(row["application_id"]),
            "candidate_name": row["candidate_name"] or row["reference"],
            "application_status": row["application_status"],
            "rank_number": row["rank_number"],
            "matching_status": row["matching_status"],
            "matching_score": row["matching_score"],
            "evidence_coverage": row["evidence_coverage"],
            "needs_verification": row["needs_verification"],
            "profile": profiles.get(str(row["profile_version_id"]),
                                    {"education": [], "work": [], "certifications": [], "languages": []}),
            "results": res,
            "strengths": [c["name"] for c in criteria if res.get(c["criterion_id"], {}).get("outcome") == "STRONG_MATCH"],
            "to_clarify": [c["name"] for c in criteria
                           if c["criterion_id"] not in res
                           or res[c["criterion_id"]]["outcome"] == "UNCLEAR"
                           or res[c["criterion_id"]]["requires_verification"]],
        })
    return {"position": position, "criteria_version_id": criteria_version_id, "criteria": criteria,
            "candidates": candidates, "best_by_criterion": best_by_criterion(criteria, candidates)}


# ---------------------------------------------------------------- export
def build_export(db, position_id: str, application_ids: list[str] | None, columns: list[str]) -> dict:
    position = _position(db, position_id)
    criteria_version_id = _current_criteria_version(db, position_id)
    if not criteria_version_id:
        raise ReportError("Vị trí chưa có bộ tiêu chí đã duyệt", 409)
    rows = candidate_rows(db, position_id, criteria_version_id, application_ids)
    if not rows:
        raise ReportError("Không có hồ sơ nào đã được đánh giá theo bộ tiêu chí hiện tại", 409)
    if len(rows) > settings.EXPORT_MAX_ROWS:
        raise ReportError(f"Tối đa {settings.EXPORT_MAX_ROWS} hồ sơ mỗi lần xuất; hãy chọn bớt hồ sơ", 413)
    wants = set(columns)
    criteria = _criteria(db, criteria_version_id) if wants & {"criteria", "evidence"} else []
    results = (_results(db, [str(r["assessment_id"]) for r in rows], with_evidence="evidence" in wants)
               if criteria else {})
    profiles = _profiles(db, [str(r["profile_version_id"]) for r in rows]) if "profile" in wants else {}
    for row in rows:
        row["results"] = results.get(str(row["assessment_id"]), {})
        row["profile"] = profiles.get(str(row["profile_version_id"]), {})
    return {"position": position, "criteria_version_id": criteria_version_id, "criteria": criteria,
            "rows": rows, "columns": [c for c in COLUMNS if c in wants]}


def safe_cell(value: Any) -> Any:
    """Neutralise spreadsheet formulas in text that came from CVs or users."""
    if isinstance(value, str) and value[:1] in ("=", "+", "-", "@", "\t", "\r"):
        return "'" + value
    return value


def _percent(value: float | None) -> str:
    return "" if value is None else f"{round(value * 100)}%"


def _evidence_text(result: dict, label: dict[str, str]) -> str:
    parts = []
    for e in result.get("evidence", []):
        page = f" [{label['page']} {e['page_number']}]" if e.get("page_number") else ""
        parts.append(f"\"{e['quote']}\"{page}" + ("" if e.get("verified") else f" {label['unverified']}"))
    return "\n".join(parts)


def _row_values(report: dict, row: dict, label: dict[str, str]) -> list[tuple[str, Any]]:
    """(header, value) pairs for the main sheet / PDF summary, in column order."""
    cols = report["columns"]
    values: list[tuple[str, Any]] = []
    if "candidate" in cols:
        values.append((label["candidate"], row["candidate_name"] or row["reference"]))
    values.append((label["reference"], row["reference"]))
    if "rank" in cols:
        values.append((label["rank"], row["rank_number"]))
    if "application_status" in cols:
        values.append((label["application_status"], label.get(row["application_status"], row["application_status"])))
    if "matching_status" in cols:
        values.append((label["matching_status"], label.get(row["matching_status"], row["matching_status"])))
    if "score" in cols:
        values.append((label["score"], row["matching_score"]))
    if "coverage" in cols:
        values.append((label["coverage"], _percent(row["evidence_coverage"])))
    if "criteria" in cols:
        for c in report["criteria"]:
            outcome = row["results"].get(c["criterion_id"], {}).get("outcome")
            values.append((f"{c['name']} ({label[c['category']]})", label.get(outcome, "") if outcome else ""))
    if "profile" in cols:
        for key in ("education", "work", "certifications", "languages"):
            values.append((label[key], "\n".join(row["profile"].get(key, []))))
    return values


def to_xlsx(report: dict, language: str = "vi") -> bytes:
    from openpyxl import Workbook
    from openpyxl.styles import Alignment, Font, PatternFill
    from openpyxl.utils import get_column_letter

    label = LABELS[language]
    wb = Workbook()
    ws = wb.active
    ws.title = label["candidates_sheet"]
    header_font, header_fill = Font(bold=True, color="FFFFFF"), PatternFill("solid", fgColor="1F3A5F")
    wrap = Alignment(wrap_text=True, vertical="top")
    rows = [_row_values(report, row, label) for row in report["rows"]]
    headers = [h for h, _ in rows[0]]
    ws.append([safe_cell(h) for h in headers])
    for values in rows:
        ws.append([safe_cell(v) for _, v in values])
    for cell in ws[1]:
        cell.font, cell.fill, cell.alignment = header_font, header_fill, wrap
    for row in ws.iter_rows(min_row=2):
        for cell in row:
            cell.alignment = wrap
    for index, header in enumerate(headers, start=1):
        width = max(len(str(header)), *(len(str(v[index - 1][1] or "")) for v in rows))
        ws.column_dimensions[get_column_letter(index)].width = min(max(width + 2, 10), 45)
    ws.freeze_panes = "B2"

    if "evidence" in report["columns"] and report["criteria"]:
        ev = wb.create_sheet(label["evidence_sheet"])
        ev.append([label["candidate"], label["reference"], label["criterion"], label["category"], label["outcome"],
                   label["quote"]])
        for row in report["rows"]:
            for c in report["criteria"]:
                result = row["results"].get(c["criterion_id"])
                if not result:
                    continue
                name = row["candidate_name"] if "candidate" in report["columns"] else ""
                ev.append([safe_cell(v) for v in (name or row["reference"], row["reference"], c["name"],
                                                   label[c["category"]], label.get(result["outcome"], ""),
                                                   _evidence_text(result, label))])
        for cell in ev[1]:
            cell.font, cell.fill = header_font, header_fill
        for col, width in zip("ABCDEF", (24, 12, 36, 12, 16, 80)):
            ev.column_dimensions[col].width = width
        for row in ev.iter_rows(min_row=2):
            for cell in row:
                cell.alignment = wrap
        ev.freeze_panes = "A2"

    info = wb.create_sheet(label["info_sheet"])
    for key, value in ((label["title"], ""), (label["position"], report["position"]["title"]),
                       (label["code"], report["position"]["position_code"]),
                       (label["criteria_version"], report["criteria_version_id"]),
                       (label["rows"], len(report["rows"])),
                       (label["exported_at"], datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC")),
                       (label["note"], label["privacy_note"])):
        info.append([safe_cell(key), safe_cell(value)])
    info["A1"].font = Font(bold=True, size=14)
    info.column_dimensions["A"].width, info.column_dimensions["B"].width = 22, 90
    buffer = io.BytesIO()
    wb.save(buffer)
    return buffer.getvalue()


_FONT_CANDIDATES = (
    ("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf"),
    ("C:/Windows/Fonts/arial.ttf", "C:/Windows/Fonts/arialbd.ttf"),
    ("/Library/Fonts/Arial Unicode.ttf", None),
)


def _pdf_fonts() -> tuple[str, str | None]:
    if settings.PDF_FONT_PATH:
        if Path(settings.PDF_FONT_PATH).is_file():
            return settings.PDF_FONT_PATH, None
        raise ReportError("Không tìm thấy font PDF đã cấu hình (PDF_FONT_PATH)", 503)
    for regular, bold in _FONT_CANDIDATES:
        if Path(regular).is_file():
            return regular, bold if bold and Path(bold).is_file() else None
    # A core PDF font would silently drop Vietnamese diacritics.
    raise ReportError("Máy chủ chưa có font Unicode để xuất PDF; cài fonts-dejavu-core hoặc đặt PDF_FONT_PATH", 503)


def _line(pdf, height: float, value: str) -> None:
    """Full-width paragraph that leaves the cursor at the left margin."""
    pdf.multi_cell(0, height, value, new_x="LMARGIN", new_y="NEXT")


def to_pdf(report: dict, language: str = "vi") -> bytes:
    from fpdf import FPDF
    from fpdf.fonts import FontFace

    label = LABELS[language]
    regular, bold = _pdf_fonts()
    pdf = FPDF(orientation="L", unit="mm", format="A4")
    pdf.set_auto_page_break(auto=True, margin=12)
    pdf.add_font("Report", "", regular)
    pdf.add_font("Report", "B", bold or regular)
    pdf.set_title(f"{label['title']} - {report['position']['position_code'] or ''}")
    pdf.add_page()
    pdf.set_font("Report", "B", 15)
    _line(pdf, 8, f"{label['title']}: {report['position']['title']}")
    pdf.set_font("Report", "", 9)
    _line(pdf, 5, f"{label['code']}: {report['position']['position_code'] or '—'}   ·   "
                         f"{label['rows']}: {len(report['rows'])}   ·   {label['exported_at']}: "
                         f"{datetime.now(timezone.utc).strftime('%Y-%m-%d %H:%M UTC')}")
    _line(pdf, 5, label["privacy_note"])
    pdf.ln(2)

    # Summary table: the scalar columns only; criteria/evidence/profile go per candidate below.
    summary_keys = {label[k] for k in ("candidate", "reference", "rank", "application_status", "matching_status",
                                        "score", "coverage")}
    head = [h for h, _ in _row_values(report, report["rows"][0], label) if h in summary_keys]
    heading = FontFace(emphasis="BOLD", color=(255, 255, 255), fill_color=(31, 58, 95))
    pdf.set_font("Report", "", 8.5)
    with pdf.table(headings_style=heading, line_height=5, text_align="LEFT") as table:
        table.row(head)
        for row in report["rows"]:
            values = dict(_row_values(report, row, label))
            table.row(["" if values[h] is None else str(values[h]) for h in head])

    if {"criteria", "evidence", "profile"} & set(report["columns"]):
        for row in report["rows"]:
            pdf.ln(4)
            pdf.set_font("Report", "B", 11)
            name = row["candidate_name"] if "candidate" in report["columns"] else ""
            _line(pdf, 6, f"{name or row['reference']} ({row['reference']})")
            pdf.set_font("Report", "", 8.5)
            if report["criteria"] and {"criteria", "evidence"} & set(report["columns"]):
                with pdf.table(headings_style=heading, line_height=4.5, text_align="LEFT",
                               col_widths=(70, 22, 28, 150) if "evidence" in report["columns"] else (150, 40, 80)) as table:
                    table.row([label["criterion"], label["category"], label["outcome"]]
                              + ([label["quote"]] if "evidence" in report["columns"] else []))
                    for c in report["criteria"]:
                        result = row["results"].get(c["criterion_id"], {})
                        cells = [c["name"], label[c["category"]], label.get(result.get("outcome"), "") if result else ""]
                        if "evidence" in report["columns"]:
                            cells.append(_evidence_text(result, label) if result else "")
                        table.row(cells)
            if "profile" in report["columns"]:
                for key in ("education", "work", "certifications", "languages"):
                    items = row["profile"].get(key, [])
                    if items:
                        pdf.set_font("Report", "B", 8.5)
                        _line(pdf, 4.5, label[key] + ":")
                        pdf.set_font("Report", "", 8.5)
                        _line(pdf, 4.5, "\n".join(f"• {item}" for item in items))
    return bytes(pdf.output())
