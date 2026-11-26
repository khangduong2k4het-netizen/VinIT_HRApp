"""Queue public-portal CVs that arrived while their position had a running job.

The portal never waits behind a running job: a CV that arrives then is stored
and marked as held. Each worker poll gathers the held CVs of every position
that is free again into ONE job, so a burst of applications becomes one batch
instead of one job per CV, and HR does not have to press "reprocess" for each.

Same lock order as the HR upload, the reprocess endpoint and the portal: lock
the position, then check for a running job, so two workers (or a worker and an
HR upload) cannot both start a job on the same position.
"""
from __future__ import annotations

import json

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.db.database import SessionLocal

logger = get_logger(__name__)

DEFERRED_WHILE_BUSY = ("CV nộp qua cổng công khai khi vị trí đang có tác vụ xử lý; "
                       "hệ thống sẽ tự xử lý khi tác vụ hiện tại hoàn tất.")
# Wording used before automatic dispatch existed; rows stored with it are picked up too.
LEGACY_DEFERRED_WHILE_BUSY = "CV nộp qua cổng công khai khi vị trí đang có tác vụ xử lý; bấm Xử lý lại để chấm điểm."
HELD_MARKERS = [DEFERRED_WHILE_BUSY, LEGACY_DEFERRED_WHILE_BUSY]

_ACTIVE_JOB_SQL = """
    SELECT 1 FROM app_private.operations WHERE position_id = :p
      AND capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING') AND status IN ('PENDING', 'PROCESSING') LIMIT 1
"""
# Open with approved criteria for the latest JD: the same conditions the reprocess endpoint requires.
_READY_POSITION_SQL = """
    SELECT p.position_id FROM app_private.positions p
    WHERE p.position_id = :p AND p.status = 'OPEN'
      AND EXISTS (SELECT 1 FROM app_private.criteria_versions cv
                  WHERE cv.position_id = p.position_id AND cv.status = 'APPROVED'
                    AND cv.jd_version_id = (SELECT jd_version_id FROM app_private.jd_versions
                                            WHERE position_id = p.position_id ORDER BY version_number DESC LIMIT 1))
    FOR UPDATE OF p SKIP LOCKED
"""


# Both public /apply and server-to-server /v1/intake CVs can arrive while the position is busy.
# Every channel that stores a CV and holds it while the position is busy: /apply, the
# partner site and the Gmail mailbox (EMAIL).
PUBLIC_INTAKE_SOURCES = ("PORTAL", "PARTNER_SITE", "EMAIL")


def _positions_with_held_cvs(db) -> list[str]:
    return [str(row[0]) for row in db.execute(text("""
        SELECT DISTINCT a.position_id
        FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
        WHERE a.source_code = ANY(:sources) AND d.document_type = 'CV'
          AND d.file_processing_status = 'NEEDS_HR_REVIEW' AND d.processing_error = ANY(:markers)
    """), {"sources": list(PUBLIC_INTAKE_SOURCES), "markers": HELD_MARKERS}).all()]


def _dispatch_position(position_id: str) -> int:
    """Start one job for the held CVs of a position. Returns how many CVs were queued."""
    db = SessionLocal()
    try:
        # SKIP LOCKED: a position locked by an HR upload or the portal is tried on the next poll.
        if not db.execute(text(_READY_POSITION_SQL), {"p": position_id}).first():
            db.rollback()
            return 0
        if db.execute(text(_ACTIVE_JOB_SQL), {"p": position_id}).first():
            db.rollback()
            return 0
        docs = db.execute(text("""
            SELECT d.document_id, d.application_id, d.original_filename, d.mime_type, d.size_bytes
            FROM app_private.application_documents d JOIN app_private.applications a USING (application_id)
            WHERE a.position_id = :p AND a.source_code = ANY(:sources) AND d.document_type = 'CV'
              AND d.file_processing_status = 'NEEDS_HR_REVIEW' AND d.processing_error = ANY(:markers)
            ORDER BY d.created_at, d.document_id
            LIMIT :limit FOR UPDATE OF d
        """), {"p": position_id, "sources": list(PUBLIC_INTAKE_SOURCES), "markers": HELD_MARKERS,
               "limit": settings.MAX_FILES_PER_BATCH}).mappings().all()
        if not docs:
            db.rollback()
            return 0
        operation_id = db.execute(text("""INSERT INTO app_private.operations(position_id, capability, status)
            VALUES (:p, 'CV_PROCESSING', 'PENDING') RETURNING operation_id"""), {"p": position_id}).scalar_one()
        batch_id = db.execute(text("""INSERT INTO app_private.cv_batches(position_id, operation_id, status, total_files, total_size_bytes)
            VALUES (:p, :o, 'PROCESSING', :n, :s) RETURNING batch_id"""),
                              {"p": position_id, "o": operation_id, "n": len(docs),
                               "s": sum(int(d["size_bytes"] or 0) for d in docs)}).scalar_one()
        for doc in docs:
            db.execute(text("""UPDATE app_private.application_documents
                SET file_processing_status = 'RECEIVED', processing_error = NULL WHERE document_id = :d"""),
                       {"d": doc["document_id"]})
            db.execute(text("""INSERT INTO app_private.document_processing_runs(document_id, operation_id, extraction_type, status)
                VALUES (:d, :o, 'INITIAL_EXTRACTION', 'PENDING')"""), {"d": doc["document_id"], "o": operation_id})
            db.execute(text("""INSERT INTO app_private.cv_batch_items(batch_id, original_filename, declared_mime_type, detected_mime_type,
                    size_bytes, validation_result, application_id) VALUES (:b, :fn, :m, :m, :s, 'ACCEPTED', :a)"""),
                       {"b": batch_id, "fn": doc["original_filename"], "m": doc["mime_type"], "s": doc["size_bytes"],
                        "a": doc["application_id"]})
        db.execute(text("""INSERT INTO app_private.audit_events(action_type, object_type, object_id, position_id, outcome, metadata)
            VALUES ('QUEUE_HELD_PUBLIC_CVS', 'CV_BATCH', :b, :p, 'SUCCESS', CAST(:m AS jsonb))"""),
                   {"b": batch_id, "p": position_id,
                    "m": json.dumps({"operation_id": str(operation_id), "cv_count": len(docs)})})
        db.commit()
        return len(docs)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


def dispatch_held_portal_cvs() -> int:
    """Queue held portal CVs of every position without a running job. Returns CVs queued."""
    db = SessionLocal()
    try:
        positions = _positions_with_held_cvs(db)
    finally:
        db.close()
    queued = 0
    for position_id in positions:
        try:
            queued += _dispatch_position(position_id)
        except Exception as exc:
            logger.error("Could not queue held portal CVs", position_id=position_id, error_type=type(exc).__name__)
    if queued:
        logger.info("Queued held portal CVs", cv_count=queued)
    return queued
