"""Public listing, explicitly enabled only after HR reviews the OPEN JDs.

No applications are accepted by this router. The intake flow is not ready.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import text

from app.core.config import settings
from app.db.database import SessionLocal

router = APIRouter()


@router.get('/jobs')
def jobs(response: Response, cursor: UUID | None = None, limit: int = Query(25, ge=1, le=100)):
    response.headers['Cache-Control'] = 'no-store'
    if not settings.PUBLIC_CAREERS_ENABLED:
        raise HTTPException(404, 'Không khả dụng', headers={'Cache-Control': 'no-store'})
    db = SessionLocal()
    try:
        # UUID keyset pagination keeps all eligible jobs available beyond the
        # first page. No rubric gating: HR is responsible for public JD content.
        rows = db.execute(text("""
            SELECT p.position_id, p.position_code, p.title, p.org_unit, p.work_location,
                   p.work_mode, p.employment_type, p.application_deadline_at,
                   jd.content_text AS description
            FROM app_private.positions p
            LEFT JOIN LATERAL (
                SELECT content_text FROM app_private.jd_versions
                WHERE position_id=p.position_id ORDER BY version_number DESC LIMIT 1
            ) jd ON TRUE
            WHERE p.status='OPEN' AND p.application_deadline_at > statement_timestamp()
              AND (:cursor IS NULL OR p.position_id > CAST(:cursor AS uuid))
            ORDER BY p.position_id LIMIT :limit
        """), {'cursor': str(cursor) if cursor else None, 'limit': limit + 1}).mappings().all()
        page = rows[:limit]
        return {'items': [dict(row) for row in page],
                'next_cursor': str(page[-1]['position_id']) if len(rows) > limit else None}
    finally:
        db.close()
