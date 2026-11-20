"""P3-1 phase 2: scan the Talent Pool against a new position's approved rubric.

Each eligible pool application (see talent_pool.eligible_pool) is scored in
place with the deterministic rule engine only. No CV text leaves the system:
criteria the rules cannot decide stay UNCLEAR and are counted, so HR knows to
check them by hand. The LLM fallback is left out until DEP-05 allows sending
real CV content to a provider.

Results keep scores and redacted evidence quotes, never names or contact data.
Eligibility is checked again every time results are read; a result whose
application left the pool (consent withdrawn, expired, queued for deletion,
unmarked) is deleted before anything is shown.
"""
from __future__ import annotations

import json
import os
from collections import Counter
from datetime import datetime
from typing import Callable, Optional

from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.config import settings
from app.services.deterministic_matching import deterministic_matcher
from app.services.identity_matching import normalize_email, normalize_phone
from app.services.matching import matching_engine
from app.services.redaction import redact_text
from app.services.talent_pool import eligible_pool, pool_expiry

DECISIONS = ("CONTACT", "SKIP", "LATER")
QUOTE_LIMIT = 300


class ScanError(ValueError):
    def __init__(self, message: str, status_code: int = 400):
        super().__init__(message)
        self.status_code = status_code


def load_extracted_text(path: str) -> str:
    if not path:
        raise FileNotFoundError("No extracted text path is recorded")
    if settings.STORAGE_BACKEND == "local":
        with open(os.path.join(settings.LOCAL_STORAGE_PATH, settings.SUPABASE_STORAGE_BUCKET_EXTRACTED, path),
                  encoding="utf-8") as f:
            return f.read()
    if settings.STORAGE_BACKEND == "supabase":
        from app.db.supabase import get_supabase_client
        client = get_supabase_client()
        if not client:
            raise RuntimeError("Supabase storage is not configured")
        return client.storage.from_(settings.SUPABASE_STORAGE_BUCKET_EXTRACTED).download(path).decode("utf-8")
    raise ValueError(f"Unknown storage backend: {settings.STORAGE_BACKEND}")


def approved_rubric(db, position_id: str) -> tuple[dict, list[dict]]:
    """Approved criteria of the latest JD of an OPEN position, as the assessment worker reads them."""
    pos = db.execute(text("SELECT status FROM app_private.positions WHERE position_id = :p"), {"p": position_id}).first()
    if pos is None:
        raise ScanError("Không tìm thấy vị trí", 404)
    if pos[0] != "OPEN":
        raise ScanError("Chỉ quét Talent Pool cho vị trí đang mở", 409)
    cv = db.execute(text("""
        SELECT criteria_version_id, mandatory_weight_total, nice_to_have_weight_total
        FROM app_private.criteria_versions WHERE position_id = :p AND status = 'APPROVED'
          AND jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions WHERE position_id = :p
                               ORDER BY version_number DESC LIMIT 1)
        ORDER BY version_number DESC LIMIT 1
    """), {"p": position_id}).mappings().first()
    if not cv:
        raise ScanError("Tiêu chí của vị trí cần được HR và Hiring Manager duyệt trước khi quét", 409)
    rows = db.execute(text("""
        SELECT criterion_id, name, description, category, weight_in_group, expected_evidence_keywords, requirement_spec
        FROM app_private.criteria_items WHERE criteria_version_id = :c ORDER BY display_order
    """), {"c": str(cv["criteria_version_id"])}).mappings().all()
    items = []
    for row in rows:
        item = {**dict(row), "criterion_id": str(row["criterion_id"]), "weight_in_group": float(row["weight_in_group"])}
        if isinstance(item.get("requirement_spec"), str):
            try:
                item["requirement_spec"] = json.loads(item["requirement_spec"])
            except (TypeError, ValueError):
                item["requirement_spec"] = None
        items.append(item)
    if not items:
        raise ScanError("Bộ tiêu chí đã duyệt không có tiêu chí nào", 409)
    return dict(cv), items


def _cv_material(db, application_id: str) -> Optional[dict]:
    row = db.execute(text("""
        SELECT pr.extracted_text_storage_path,
               (SELECT pv.profile_version_id FROM app_private.profile_versions pv
                WHERE pv.application_id = :a AND pv.status = 'COMPLETED' ORDER BY pv.version_number DESC LIMIT 1) AS profile_version_id
        FROM app_private.application_documents d
        JOIN app_private.document_processing_runs pr ON pr.document_id = d.document_id AND pr.status = 'COMPLETED'
        WHERE d.application_id = :a AND d.document_type = 'CV' AND d.file_processing_status = 'COMPLETED'
          AND pr.extracted_text_storage_path IS NOT NULL
        ORDER BY d.created_at DESC, pr.created_at DESC LIMIT 1
    """), {"a": application_id}).mappings().first()
    return dict(row) if row else None


def _candidate_profile(db, application_id: str, profile_version_id) -> dict:
    facts = db.execute(text("""SELECT fact_type, fact_value FROM app_private.profile_facts
        WHERE profile_version_id = :v"""), {"v": str(profile_version_id)}).mappings().all() if profile_version_id else []
    return {
        "candidate_identifier": application_id,
        "total_years_experience": 0,
        "education": [f["fact_value"] for f in facts if f["fact_type"] == "EDUCATION"],
        "work_history": [f["fact_value"] for f in facts if f["fact_type"] == "WORK_EXPERIENCE"],
        "skills": [(f["fact_value"] or {}).get("name") for f in facts if f["fact_type"] == "SKILL"],
        "certifications": [f["fact_value"] for f in facts if f["fact_type"] == "CERTIFICATION"],
        "languages": [f["fact_value"] for f in facts if f["fact_type"] == "LANGUAGE"],
        "projects": [f["fact_value"] for f in facts if f["fact_type"] == "PROJECT"],
    }


def score_cv(cv_text: str, criteria: list[dict], candidate_profile: dict, group_weights: dict) -> dict:
    """Rules-only scoring of one CV. Quotes are verified against the (redacted) text."""
    result = deterministic_matcher.evaluate_criteria(cv_text, criteria, candidate_profile)
    if result.get("candidate_years_experience"):
        candidate_profile["total_years_experience"] = result["candidate_years_experience"]
    validated = []
    for finding in matching_engine.canonicalize_findings(criteria, list(result.get("findings", []))):
        evidence = finding.get("evidence") or {}
        quote = evidence.get("verbatim_quote") or ""
        span = matching_engine.find_quote_span(quote, cv_text) if quote else None
        if span is not None:
            evidence["verbatim_quote"] = cv_text[span[0]:span[1]]
        elif finding.get("outcome") != "UNCLEAR":
            finding["outcome"] = "UNCLEAR"
            finding["requires_verification"] = True
        finding["evidence"] = evidence
        validated.append(finding)
    score, coverage, status, results, _ = matching_engine.calculate_assessment_scores(
        criteria, validated, group_weights=group_weights)
    names = {c["criterion_id"]: (c.get("name"), c.get("category")) for c in criteria}
    criterion_results = [{
        "criterion_id": r["criterion_id"],
        "name": names.get(r["criterion_id"], (None, None))[0],
        "category": names.get(r["criterion_id"], (None, None))[1],
        "outcome": r["outcome"],
        "quote": ((r.get("evidence") or {}).get("verbatim_quote") or "")[:QUOTE_LIMIT] or None,
    } for r in results]
    return {"score": score, "coverage": coverage, "status": status, "criterion_results": criterion_results,
            "unresolved_count": sum(1 for r in results if r["outcome"] == "UNCLEAR")}


def _identities(db, application_ids: list[str]) -> dict[str, tuple[str, str]]:
    """application_id -> (normalized email, normalized phone); empty strings when absent or malformed."""
    if not application_ids:
        return {}
    rows = db.execute(text("""SELECT application_id, email, phone FROM app_private.application_identities
        WHERE application_id = ANY(CAST(:ids AS uuid[]))"""), {"ids": application_ids}).all()
    return {str(r[0]): (normalize_email(r[1]), normalize_phone(r[2])) for r in rows}


def _target_contacts(db, position_id: str) -> tuple[set[str], set[str]]:
    """Emails and phones (normalized) of everyone who already applied to the target position."""
    rows = db.execute(text("""SELECT i.email, i.phone FROM app_private.application_identities i
        JOIN app_private.applications a ON a.application_id = i.application_id
        WHERE a.position_id = :p"""), {"p": position_id}).all()
    emails = {e for e in (normalize_email(r[0]) for r in rows) if e}
    phones = {p for p in (normalize_phone(r[1]) for r in rows) if p}
    return emails, phones


def _rank_key(item: dict) -> tuple:
    result = item["result"]
    return (result["status"] != "POSSIBLE_MISMATCH", result["score"] if result["score"] is not None else -1.0,
            result["coverage"], item["consented_at"])


def run_scan(db, *, scan_id: str, position_id: str, user_id: str,
             read_text: Callable[[str], str] = load_extracted_text) -> dict:
    """Score eligible pool applications for the position and complete the scan row. Caller commits.

    Pool applications whose candidate already applied to this position (same email or
    phone) are left out, and only the best application per email is kept.
    """
    cv, criteria = approved_rubric(db, position_id)
    group_weights = {"MUST_HAVE": float(cv["mandatory_weight_total"]) / 100,
                     "NICE_TO_HAVE": float(cv["nice_to_have_weight_total"]) / 100}
    pool = [row for row in eligible_pool(db) if str(row["position_id"]) != position_id]
    eligible_count = len(pool)
    skipped: Counter = Counter()

    applied_emails, applied_phones = _target_contacts(db, position_id)
    identities = _identities(db, [str(r["application_id"]) for r in pool])
    if applied_emails or applied_phones:
        kept = []
        for row in pool:
            email, phone = identities.get(str(row["application_id"]), ("", ""))
            if (email and email in applied_emails) or (phone and phone in applied_phones):
                skipped["ALREADY_APPLIED"] += 1
            else:
                kept.append(row)
        pool = kept
    if len(pool) > settings.TALENT_POOL_SCAN_MAX:
        skipped["OVER_LIMIT"] = len(pool) - settings.TALENT_POOL_SCAN_MAX
        pool = sorted(pool, key=lambda r: r["consented_at"], reverse=True)[:settings.TALENT_POOL_SCAN_MAX]

    scored: list[dict] = []
    failed = 0
    for row in pool:
        application_id = str(row["application_id"])
        material = _cv_material(db, application_id)
        if not material:
            skipped["NO_EXTRACTED_TEXT"] += 1
            continue
        try:
            cv_text = redact_text(read_text(material["extracted_text_storage_path"]), detect_first_line_name=True)
        except Exception:
            skipped["TEXT_UNAVAILABLE"] += 1
            failed += 1
            continue
        try:
            result = score_cv(cv_text, criteria,
                              _candidate_profile(db, application_id, material["profile_version_id"]), group_weights)
        except Exception:
            skipped["SCORING_ERROR"] += 1
            failed += 1
            continue
        email, phone = identities.get(application_id, ("", ""))
        scored.append({"application_id": application_id, "consented_at": row["consented_at"], "result": result,
                       "email": email, "phone": phone})

    # One row per candidate: dedupe by email first, then by phone, keeping the best application.
    best_email: dict[str, dict] = {}
    after_email: list[dict] = []
    for item in scored:
        if not item["email"]:
            after_email.append(item)
            continue
        current = best_email.get(item["email"])
        if current is None:
            best_email[item["email"]] = item
            continue
        skipped["DUPLICATE_EMAIL"] += 1
        if _rank_key(item) > _rank_key(current):
            best_email[item["email"]] = item
    after_email.extend(best_email.values())

    best_phone: dict[str, dict] = {}
    final: list[dict] = []
    for item in after_email:
        if not item["phone"]:
            final.append(item)
            continue
        current = best_phone.get(item["phone"])
        if current is None:
            best_phone[item["phone"]] = item
            continue
        skipped["DUPLICATE_PHONE"] += 1
        if _rank_key(item) > _rank_key(current):
            best_phone[item["phone"]] = item
    final.extend(best_phone.values())

    for item in final:
        result = item["result"]
        db.execute(text("""INSERT INTO app_private.talent_pool_scan_results(scan_id, application_id, matching_score,
                evidence_coverage, matching_status, unresolved_count, criterion_results)
            VALUES (:s, :a, :score, :cov, :st, :u, CAST(:cr AS jsonb))"""),
                   {"s": scan_id, "a": item["application_id"], "score": result["score"], "cov": result["coverage"],
                    "st": result["status"], "u": result["unresolved_count"],
                    "cr": json.dumps(result["criterion_results"], ensure_ascii=False)})
    db.execute(text("""UPDATE app_private.talent_pool_scans
        SET criteria_version_id = :c, eligible_count = :e, scored_count = :n, failed_count = :f,
            skipped_counts = CAST(:k AS jsonb), status = 'COMPLETED', completed_at = NOW(), error_message = NULL
        WHERE scan_id = :s"""),
               {"c": str(cv["criteria_version_id"]), "e": eligible_count, "n": len(final), "f": failed,
                "k": json.dumps(dict(skipped)), "s": scan_id})
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, 'SCAN_TALENT_POOL', 'TALENT_POOL_SCAN', :s, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
               {"u": user_id, "s": scan_id, "p": position_id,
                "m": json.dumps({"eligible_count": eligible_count, "scored_count": len(final), "failed_count": failed,
                                 "skipped": dict(skipped), "criteria_version_id": str(cv["criteria_version_id"]),
                                 "method": "RULES_ONLY"})})
    return {"scan_id": scan_id, "eligible_count": eligible_count, "scored_count": len(final),
            "failed_count": failed, "skipped": dict(skipped)}


def enqueue_scan(db, *, position_id: str, user_id: str) -> dict:
    """Validate the rubric and queue a TALENT_POOL_SCAN job. Caller commits."""
    cv, _ = approved_rubric(db, position_id)
    busy = ScanError("Vị trí đang có một lượt quét Talent Pool chưa xong", 409)
    if db.execute(text("""SELECT 1 FROM app_private.talent_pool_scans
            WHERE position_id = :p AND status IN ('PENDING', 'PROCESSING') LIMIT 1"""), {"p": position_id}).first():
        raise busy
    operation_id = str(db.execute(text("""INSERT INTO app_private.operations(position_id, capability, status, requested_by)
        VALUES (:p, 'TALENT_POOL_SCAN', 'PENDING', :u) RETURNING operation_id"""),
                                  {"p": position_id, "u": user_id}).scalar_one())
    try:
        with db.begin_nested():
            scan_id = str(db.execute(text("""INSERT INTO app_private.talent_pool_scans(position_id, criteria_version_id,
                    requested_by, operation_id, status) VALUES (:p, :c, :u, :o, 'PENDING') RETURNING scan_id"""),
                                     {"p": position_id, "c": str(cv["criteria_version_id"]), "u": user_id,
                                      "o": operation_id}).scalar_one())
    except IntegrityError:  # unique index: another request queued a scan in between
        raise busy from None
    db.execute(text("""INSERT INTO app_private.audit_events(actor_user_id, action_type, object_type, object_id, position_id, outcome, metadata)
        VALUES (:u, 'REQUEST_TALENT_POOL_SCAN', 'TALENT_POOL_SCAN', :s, :p, 'QUEUED', CAST(:m AS jsonb))"""),
               {"u": user_id, "s": scan_id, "p": position_id, "m": json.dumps({"operation_id": operation_id})})
    return {"scan_id": scan_id, "operation_id": operation_id, "status": "PENDING"}


def run_scan_for_operation(db, operation_id: str, read_text: Callable[[str], str] = load_extracted_text) -> Optional[dict]:
    """Worker entry point: run the scan queued for this operation."""
    scan = db.execute(text("""SELECT scan_id, position_id, requested_by FROM app_private.talent_pool_scans
        WHERE operation_id = :o"""), {"o": operation_id}).mappings().first()
    if scan is None:
        return None
    db.execute(text("UPDATE app_private.talent_pool_scans SET status = 'PROCESSING', error_message = NULL WHERE scan_id = :s"),
               {"s": str(scan["scan_id"])})
    db.commit()
    return run_scan(db, scan_id=str(scan["scan_id"]), position_id=str(scan["position_id"]),
                    user_id=str(scan["requested_by"]), read_text=read_text)


def mark_scan_failed(db, operation_id: str, message: str) -> None:
    db.execute(text("""UPDATE app_private.talent_pool_scans
        SET status = 'FAILED', error_message = :m, completed_at = NOW()
        WHERE operation_id = :o AND status IN ('PENDING', 'PROCESSING')"""), {"o": operation_id, "m": message[:500]})


def scan_header(db, scan_id: str) -> Optional[dict]:
    row = db.execute(text("""SELECT s.scan_id, s.position_id, s.criteria_version_id, s.requested_by, s.created_at,
            s.eligible_count, s.scored_count, s.skipped_counts, s.method, s.status, s.failed_count,
            s.error_message, s.completed_at, s.operation_id
        FROM app_private.talent_pool_scans s WHERE s.scan_id = :s"""), {"s": scan_id}).mappings().first()
    return dict(row) if row else None


def scan_results(db, scan_id: str, now: Optional[datetime] = None) -> list[dict]:
    """Ranked results still eligible right now. Results that left the pool are deleted first."""
    state = db.execute(text("SELECT status FROM app_private.talent_pool_scans WHERE scan_id = :s"), {"s": scan_id}).scalar()
    if state != "COMPLETED":
        return []
    still = {str(r["application_id"]): r for r in eligible_pool(db, now)}
    db.execute(text("""DELETE FROM app_private.talent_pool_scan_results
        WHERE scan_id = :s AND NOT (application_id = ANY(CAST(:ids AS uuid[]))) """),
               {"s": scan_id, "ids": list(still)})
    rows = db.execute(text("""
        SELECT r.application_id, r.matching_score, r.evidence_coverage, r.matching_status, r.unresolved_count,
               r.criterion_results, r.hr_decision, r.decided_at, a.position_id AS source_position_id,
               p.title AS source_position_title, p.position_code AS source_position_code, m.reason_code AS mark_reason
        FROM app_private.talent_pool_scan_results r
        JOIN app_private.applications a ON a.application_id = r.application_id
        JOIN app_private.positions p ON p.position_id = a.position_id
        LEFT JOIN app_private.talent_pool_marks m ON m.application_id = r.application_id AND m.removed_at IS NULL
        WHERE r.scan_id = :s
        ORDER BY (r.matching_status = 'POSSIBLE_MISMATCH'), r.matching_score DESC NULLS LAST,
                 r.evidence_coverage DESC, r.application_id
    """), {"s": scan_id}).mappings().all()
    out = []
    for rank, r in enumerate(rows, start=1):
        item = dict(r)
        consented_at = still[str(r["application_id"])]["consented_at"]
        item.update({
            "rank": rank,
            "application_id": str(r["application_id"]),
            "source_position_id": str(r["source_position_id"]),
            "matching_score": float(r["matching_score"]) if r["matching_score"] is not None else None,
            "evidence_coverage": float(r["evidence_coverage"]),
            "pool_expires_on": pool_expiry(consented_at).date().isoformat(),
        })
        out.append(item)
    return out


def record_decision(db, *, scan_id: str, application_id: str, decision: str, user_id: str) -> bool:
    if decision not in DECISIONS:
        raise ScanError("Quyết định không hợp lệ", 400)
    still = {str(r["application_id"]) for r in eligible_pool(db)}
    if application_id not in still:
        db.execute(text("DELETE FROM app_private.talent_pool_scan_results WHERE scan_id = :s AND application_id = :a"),
                   {"s": scan_id, "a": application_id})
        raise ScanError("Hồ sơ không còn trong Talent Pool", 409)
    done = db.execute(text("""UPDATE app_private.talent_pool_scan_results
        SET hr_decision = :d, decided_by = :u, decided_at = NOW() WHERE scan_id = :s AND application_id = :a"""),
                      {"d": decision, "u": user_id, "s": scan_id, "a": application_id}).rowcount
    return bool(done)


def usable_candidate_name(display_name: str | None, cv_filename: str | None) -> str | None:
    """A person's name for a greeting, or None.

    The stored display name is the CV file name until a real name is available, and
    a file name is not a name ("Tran_Thu_Ha_CV"). Anything that looks like a file name
    is treated as missing so the email falls back to the generic greeting.
    """
    name = (display_name or "").strip()
    if not name:
        return None
    lowered = name.lower()
    if lowered.endswith((".pdf", ".docx", ".doc", ".jpg", ".jpeg", ".png")) or "_" in name:
        return None
    if cv_filename:
        stem = os.path.splitext(os.path.basename(cv_filename))[0].strip().lower()
        if lowered == stem or lowered == cv_filename.strip().lower():
            return None
    return name


def reveal_contact(db, *, scan_id: str, application_id: str) -> dict:
    """Return candidate contact details and a suggested email preview for a pool result
    that HR explicitly marked CONTACT. Re-verifies pool eligibility right before reveal;
    never sends email and never creates an application in the target position."""
    still = {str(r["application_id"]) for r in eligible_pool(db)}
    if application_id not in still:
        db.execute(text("DELETE FROM app_private.talent_pool_scan_results WHERE scan_id = :s AND application_id = :a"),
                   {"s": scan_id, "a": application_id})
        raise ScanError("Hồ sơ không còn trong Talent Pool", 409)
    row = db.execute(text("""
        SELECT r.hr_decision, s.status AS scan_status,
               tp.title AS target_title, tp.position_code AS target_code,
               sp.title AS source_title, sp.position_code AS source_code,
               i.display_name, i.email, i.phone,
               (SELECT d.original_filename FROM app_private.application_documents d
                 WHERE d.application_id = r.application_id AND d.document_type = 'CV'
                 ORDER BY d.created_at LIMIT 1) AS cv_filename
        FROM app_private.talent_pool_scan_results r
        JOIN app_private.talent_pool_scans s ON s.scan_id = r.scan_id
        JOIN app_private.positions tp ON tp.position_id = s.position_id
        JOIN app_private.applications a ON a.application_id = r.application_id
        JOIN app_private.positions sp ON sp.position_id = a.position_id
        LEFT JOIN app_private.application_identities i ON i.application_id = r.application_id
        WHERE r.scan_id = :s AND r.application_id = :a
    """), {"s": scan_id, "a": application_id}).mappings().first()
    if not row:
        raise ScanError("Không có kết quả này trong lượt quét", 404)
    if row["scan_status"] != "COMPLETED":
        raise ScanError("Lượt quét chưa hoàn tất", 409)
    if row["hr_decision"] != "CONTACT":
        raise ScanError("Cần chọn quyết định Liên hệ trước khi xem thông tin liên hệ", 409)
    name = usable_candidate_name(row["display_name"], row["cv_filename"])
    greeting = f"Chào {name}," if name else "Chào Anh/Chị,"
    subject = f"[VinUniversity] Mời trao đổi cơ hội tuyển dụng: {row['target_title']} ({row['target_code']})"
    body = (
        f"{greeting}\n\n"
        f"Bộ phận Nhân sự Trường Đại học VinUni liên hệ với bạn từ hồ sơ đã lưu trong Talent Pool "
        f"(trước đây ứng tuyển vị trí {row['source_title']} — {row['source_code']}).\n\n"
        f"Hiện tại VinUni đang tuyển vị trí {row['target_title']} ({row['target_code']}) và nhận thấy kinh nghiệm "
        f"của bạn phù hợp với yêu cầu công việc. Nếu bạn quan tâm, vui lòng phản hồi email này kèm CV mới nhất "
        f"(nếu có cập nhật) để chúng tôi trao đổi chi tiết hơn.\n\n"
        f"Nếu bạn không còn muốn VinUni lưu hồ sơ cho các vị trí khác, bạn có thể sử dụng mã rút đồng ý đã nhận "
        f"hoặc phản hồi trực tiếp email này để chúng tôi cập nhật ngay.\n\n"
        f"Trân trọng,\nBộ phận Nhân sự — VinUniversity"
    )
    return {
        "application_id": application_id,
        "display_name": name,
        "email": row["email"],
        "phone": row["phone"],
        "target_position_title": row["target_title"],
        "target_position_code": row["target_code"],
        "source_position_title": row["source_title"],
        "source_position_code": row["source_code"],
        "email_subject": subject,
        "email_body": body,
    }

