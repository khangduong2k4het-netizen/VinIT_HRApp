"""Persisted assessment samples and read-only, version-bound QA context.

Sampling tops up a frozen random cohort to ceil(10% of completed assessments).
Previously selected cases are never removed; risk cases are additional.
"""
import hashlib
import json
import math
from pathlib import Path, PurePosixPath

from fastapi import HTTPException
from sqlalchemy import text

from app.core.config import settings


def ocr_mean_confidence(pages: list[dict]) -> float | None:
    values = []
    for page in pages:
        data = page.get('ocr_confidence')
        if not isinstance(data, dict):
            continue
        for raw in data.get('conf', []):
            try:
                value = float(raw)
            except (ValueError, TypeError):
                continue
            if math.isfinite(value) and 0 <= value <= 100:
                values.append(value)
    return round(sum(values) / len(values), 2) if values else None


BORDERLINE_COVERAGE_MARGIN = 0.05  # "sát ngưỡng": within ±5 points of the configured threshold


def risk_reasons(coverage: float | None, mandatory_no_match: int) -> list[str]:
    reasons = []
    if mandatory_no_match == 1:
        reasons.append('SINGLE_MANDATORY_MISS')
    # Follow the threshold matching actually uses, so changing the config moves the band too.
    threshold = settings.MIN_EVIDENCE_COVERAGE
    if coverage is not None and abs(float(coverage) - threshold) <= BORDERLINE_COVERAGE_MARGIN + 1e-9:
        reasons.append('BORDERLINE_COVERAGE')
    return reasons


def select_samples(rows: list[dict], selected_random: set[str], position_id: str) -> dict[str, list[str]]:
    reasons = {str(r['assessment_id']): risk_reasons(r['evidence_coverage'], r['mandatory_misses']) for r in rows}
    needed = max(0, math.ceil(len(rows) * 0.1) - len(selected_random))
    candidates = sorted((key for key in reasons if key not in selected_random),
                        key=lambda key: hashlib.sha256(f'qa-v1:{position_id}:{key}'.encode()).hexdigest())
    for key in selected_random | set(candidates[:needed]):
        if key in reasons:
            reasons[key].append('RANDOM_SAMPLE')
    return {key: value for key, value in reasons.items() if value}


def generate_samples(db, position_id: str) -> int:
    # Serialize sample selection across concurrent workers and manual scans.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext(:key))"), {'key': f'quality:{position_id}'})
    # Reassessment adds a new run and leaves the old one COMPLETED; only each
    # application's latest completed run is current, so only those are sampled.
    rows = [dict(row) for row in db.execute(text("""
        WITH latest AS (
            SELECT DISTINCT ON (application_id) assessment_id,evidence_coverage
            FROM app_private.assessment_runs
            WHERE position_id=:p AND status='COMPLETED'
            ORDER BY application_id,completed_at DESC NULLS LAST,created_at DESC,assessment_id DESC
        )
        SELECT l.assessment_id,l.evidence_coverage,
          (SELECT COUNT(*) FROM app_private.criterion_assessment_results r
           JOIN app_private.criteria_items c ON c.criterion_id=r.criterion_id
           WHERE r.assessment_id=l.assessment_id AND c.category='MUST_HAVE' AND r.outcome='NO_MATCH') AS mandatory_misses
        FROM latest l
    """), {'p': position_id}).mappings()]
    existing = {str(r['assessment_id']): r['reasons'] for r in db.execute(text(
        'SELECT assessment_id,reasons FROM app_private.quality_inspections WHERE position_id=:p'), {'p': position_id}).mappings()}
    current = {str(r['assessment_id']) for r in rows}
    # Cases on superseded runs stay in the queue (never removed) but no longer
    # count towards the random quota of the current cohort.
    random = {key for key, reasons in existing.items() if 'RANDOM_SAMPLE' in reasons and key in current}
    created = 0
    for assessment_id, reasons in select_samples(rows, random, position_id).items():
        if assessment_id in existing:
            # An already selected risk case can also fill a random slot.
            # Preserve its original risk evidence and never reset its review.
            combined = sorted(set(existing[assessment_id]) | set(reasons))
            if combined != sorted(existing[assessment_id]):
                db.execute(text('UPDATE app_private.quality_inspections SET reasons=CAST(:r AS jsonb) WHERE assessment_id=:a'),
                           {'r': json.dumps(combined), 'a': assessment_id})
            continue
        db.execute(text("""
            INSERT INTO app_private.quality_inspections(assessment_id,position_id,reasons)
            VALUES (:a,:p,CAST(:r AS jsonb)) ON CONFLICT (assessment_id) DO NOTHING
        """), {'a': assessment_id, 'p': position_id, 'r': json.dumps(reasons)})
        created += 1
    return created


def read_storage(bucket: str, path: str) -> bytes:
    """Paths are database-owned, but still reject traversal and symlink escapes."""
    relative = PurePosixPath(path)
    if not path or relative.is_absolute() or '..' in relative.parts or '\\' in path:
        raise HTTPException(503, 'Đường dẫn tài liệu không hợp lệ')
    if bucket not in {settings.SUPABASE_STORAGE_BUCKET_CV, settings.SUPABASE_STORAGE_BUCKET_EXTRACTED}:
        raise HTTPException(503, 'Kho tài liệu không hợp lệ')
    try:
        if settings.STORAGE_BACKEND == 'local':
            root = (Path(settings.LOCAL_STORAGE_PATH) / bucket).resolve()
            target = (root / path).resolve()
            if not target.is_relative_to(root):
                raise HTTPException(503, 'Đường dẫn tài liệu không hợp lệ')
            return target.read_bytes()
        from app.db.supabase import get_supabase_client
        client = get_supabase_client()
        if not client or settings.STORAGE_BACKEND != 'supabase':
            raise HTTPException(503, 'Kho tài liệu chưa được cấu hình')
        return client.storage.from_(bucket).download(path)
    except HTTPException:
        raise
    except Exception:
        raise HTTPException(503, 'Chưa thể đọc tài liệu nguồn') from None
