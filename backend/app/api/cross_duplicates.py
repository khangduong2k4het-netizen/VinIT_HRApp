from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.services.cross_duplicates import refresh_application, warnings
from app.services.review_access import audit, has_scope, require_scope

router = APIRouter()


class DuplicateReview(BaseModel):
    model_config = ConfigDict(extra='forbid')
    decision: Literal['CONFIRMED', 'DISMISSED']


def _application(db, application_id: UUID, user_id: str):
    position = db.execute(text('SELECT position_id FROM app_private.applications WHERE application_id=:id'),
                          {'id': str(application_id)}).scalar_one_or_none()
    if not position:
        raise HTTPException(404, 'Không tìm thấy hồ sơ')
    require_scope(db, user_id, str(position))
    return str(position)


@router.get('/applications/{application_id}')
def list_warnings(application_id: UUID, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        position = _application(db, application_id, user['user_id'])
        result = warnings(db, str(application_id), user['user_id'])
        audit(db, user['user_id'], 'VIEW_CROSS_DUPLICATES', 'APPLICATION', str(application_id), position)
        return result


@router.post('/applications/{application_id}/scan')
def scan(application_id: UUID, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        position = _application(db, application_id, user['user_id'])
        refresh_application(db, str(application_id))
        audit(db, user['user_id'], 'SCAN_CROSS_DUPLICATES', 'APPLICATION', str(application_id), position)
        return warnings(db, str(application_id), user['user_id'])


@router.post('/signals/{signal_id}/review')
def review(signal_id: UUID, request: DuplicateReview, user: dict = Depends(get_current_user)):
    with SessionLocal.begin() as db:
        # Same lock order as detector/identity edits.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtext('hra:cross-duplicates'))"))
        row = db.execute(text("""
            SELECT s.*,a.position_id AS first_position,b.position_id AS second_position
            FROM app_private.cross_position_duplicates s JOIN app_private.applications a ON a.application_id=s.application_id_1
            JOIN app_private.applications b ON b.application_id=s.application_id_2
            WHERE s.signal_id=:id FOR UPDATE OF s
        """), {'id': str(signal_id)}).mappings().first()
        if not row or not all(has_scope(db, user['user_id'], str(row[key])) for key in ('first_position','second_position')):
            raise HTTPException(404, 'Không tìm thấy cảnh báo trong phạm vi được phép')
        if row['review_status'] != 'PENDING':
            raise HTTPException(409, 'Cảnh báo đã được xử lý hoặc thông tin hồ sơ đã thay đổi')
        for key in ('first_position', 'second_position'):
            require_scope(db, user['user_id'], str(row[key]))
        db.execute(text("UPDATE app_private.cross_position_duplicates SET review_status=:s,reviewed_by=:u,reviewed_at=NOW() WHERE signal_id=:id"),
                   {'id': str(signal_id), 's': request.decision, 'u': user['user_id']})
        audit(db, user['user_id'], 'REVIEW_CROSS_DUPLICATE', 'CROSS_DUPLICATE', str(signal_id), str(row['first_position']))
        return {'review_status': request.decision}
