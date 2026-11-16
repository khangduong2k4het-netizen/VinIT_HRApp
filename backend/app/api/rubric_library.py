"""Position-independent rubric templates; publishing never approves a position."""
import json
from decimal import Decimal
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, Field, model_validator
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal
from app.schemas.criteria import RequirementSpec

router = APIRouter()


class Item(BaseModel):
    @model_validator(mode='after')
    def nonblank(self):
        if not self.name.strip() or not self.description.strip():
            raise ValueError('Tên và mô tả không được để trống')
        return self

    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    category: Literal['MUST_HAVE', 'NICE_TO_HAVE']
    weight_in_group: Decimal = Field(ge=0, le=100, decimal_places=2)
    expected_evidence_keywords: list[str] = Field(default_factory=list, max_length=50)
    requirement_spec: RequirementSpec | None = None
    evidence_guidance: str | None = Field(default=None, max_length=4000)


class Draft(BaseModel):
    mandatory_weight_total: Decimal = Field(default=Decimal('70'), ge=0, le=100, decimal_places=2)
    nice_to_have_weight_total: Decimal = Field(default=Decimal('30'), ge=0, le=100, decimal_places=2)
    items: list[Item] = Field(default_factory=list, max_length=100)

    @model_validator(mode='after')
    def validate_weights(self):
        if self.mandatory_weight_total <= 0 or self.mandatory_weight_total + self.nice_to_have_weight_total != 100:
            raise ValueError('Tổng trọng số hai nhóm phải bằng 100')
        return self


class NewTemplate(Draft):
    @model_validator(mode='after')
    def nonblank_title(self):
        if not self.title.strip():
            raise ValueError('Tên rubric không được để trống')
        return self

    job_family_id: UUID
    title: str = Field(min_length=1, max_length=200)
    level_band: str | None = Field(default=None, max_length=100)


class UpdateDraft(Draft):
    expected_revision: int = Field(ge=1)


class PublishTemplate(BaseModel):
    expected_revision: int = Field(ge=1)


class ApplyTemplate(BaseModel):
    template_version_id: UUID


def _roles(db, actor: str, lock: bool = False):
    account = db.execute(text('SELECT account_status FROM app_private.user_profiles WHERE user_id=:id' + (' FOR SHARE' if lock else '')), {'id': actor}).scalar_one_or_none()
    if account != 'ACTIVE':
        raise HTTPException(403, 'Tài khoản không hoạt động')
    roles = set(db.execute(text('SELECT role_code FROM app_private.user_role_assignments WHERE user_id=:id AND revoked_at IS NULL' + (' FOR SHARE' if lock else '')), {'id': actor}).scalars())
    assigned = bool(db.execute(text("SELECT 1 FROM app_private.position_assignments WHERE user_id=:id AND position_role IN ('HR_RECRUITER','HR_LEAD') AND revoked_at IS NULL LIMIT 1" + (' FOR SHARE' if lock else '')), {'id': actor}).first())
    return roles, assigned


def _require_directory(db, actor, lock=False):
    roles, assigned = _roles(db, actor, lock)
    if not assigned and not roles.intersection({'ADMIN', 'HR_LEAD', 'HR_RECRUITER'}):
        raise HTTPException(403, 'Chỉ HR được truy cập thư viện rubric')
    return roles, assigned


def _require_editor(db, actor, owner=None):
    roles, assigned = _require_directory(db, actor, lock=True)
    if 'HR_LEAD' not in roles and not ((assigned or 'HR_RECRUITER' in roles) and (owner is None or str(owner) == actor)):
        raise HTTPException(403, 'Chỉ HR tạo bản nháp hoặc HR Lead được chỉnh sửa')
    return roles


def _replace_items(db, version_id, items):
    db.execute(text('DELETE FROM app_private.rubric_template_items WHERE template_version_id=:id'), {'id': version_id})
    for i, item in enumerate(items):
        db.execute(text('''INSERT INTO app_private.rubric_template_items
            (template_version_id,name,description,category,weight_in_group,expected_evidence_keywords,requirement_spec,evidence_guidance,display_order)
            VALUES (:id,:name,:description,:category,:weight,CAST(:keywords AS jsonb),CAST(:spec AS jsonb),:guidance,:order)'''),
            {'id': version_id, 'name': item.name.strip(), 'description': item.description.strip(), 'category': item.category,
             'weight': item.weight_in_group, 'keywords': json.dumps(item.expected_evidence_keywords),
             'spec': json.dumps(item.requirement_spec.model_dump()) if item.requirement_spec else None,
             'guidance': item.evidence_guidance, 'order': i})


def _version(db, version_id):
    row = db.execute(text('''SELECT v.*,t.title,t.job_family_id,t.level_band FROM app_private.rubric_template_versions v
        JOIN app_private.rubric_templates t ON t.template_id=v.template_id WHERE v.template_version_id=:id'''), {'id': str(version_id)}).mappings().first()
    if not row:
        raise HTTPException(404, 'Không tìm thấy rubric')
    result = dict(row)
    result['items'] = [dict(r) for r in db.execute(text('SELECT * FROM app_private.rubric_template_items WHERE template_version_id=:id ORDER BY display_order,template_item_id'), {'id': str(version_id)}).mappings()]
    return result


def _audit(db, actor, action, obj, position=None):
    db.execute(text('''INSERT INTO app_private.audit_events (actor_user_id,action_type,object_type,object_id,position_id,outcome)
        VALUES (:actor,:action,'RUBRIC_TEMPLATE_VERSION',:id,:position,'SUCCESS')'''),
        {'actor': actor, 'action': action, 'id': str(obj), 'position': str(position) if position else None})


@router.get('/capabilities')
def capabilities(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        roles, assigned = _require_directory(db, user['user_id'])
        return {'can_create': bool(assigned or roles.intersection({'HR_RECRUITER', 'HR_LEAD'})),
                'can_publish': 'HR_LEAD' in roles, 'user_id': user['user_id']}
    finally:
        db.close()


@router.get('/families')
def families(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_directory(db, user['user_id'])
        return [dict(r) for r in db.execute(text('SELECT * FROM app_private.job_families WHERE is_active ORDER BY name')).mappings()]
    finally: db.close()


@router.get('/templates')
def templates(user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        roles, _ = _require_directory(db, user['user_id'])
        rows = db.execute(text('''SELECT v.template_version_id,v.template_id,v.version_number,v.status,v.created_by,
            v.revision,t.title,t.level_band,t.job_family_id,f.name AS family_name
            FROM app_private.rubric_template_versions v JOIN app_private.rubric_templates t ON t.template_id=v.template_id
            JOIN app_private.job_families f ON f.job_family_id=t.job_family_id
            WHERE v.status='PUBLISHED' OR v.created_by=:actor OR :lead
            ORDER BY t.title,v.version_number DESC'''), {'actor': user['user_id'], 'lead': 'HR_LEAD' in roles}).mappings().all()
        return [dict(row) for row in rows]
    finally: db.close()


@router.get('/versions/{version_id}')
def get_version(version_id: UUID, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        roles, _ = _require_directory(db, user['user_id'])
        data = _version(db, version_id)
        if data['status'] != 'PUBLISHED' and str(data['created_by']) != user['user_id'] and 'HR_LEAD' not in roles:
            raise HTTPException(403, 'Không có quyền xem bản nháp')
        return data
    finally: db.close()


@router.post('/templates', status_code=201)
def create_template(request: NewTemplate, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        _require_editor(db, user['user_id'])
        if not db.execute(text('SELECT 1 FROM app_private.job_families WHERE job_family_id=:id AND is_active'), {'id': str(request.job_family_id)}).first():
            raise HTTPException(400, 'Nhóm vị trí không hoạt động')
        template = db.execute(text('''INSERT INTO app_private.rubric_templates(job_family_id,title,level_band,created_by)
            VALUES (:family,:title,:level,:actor) RETURNING template_id'''),
            {'family': str(request.job_family_id), 'title': request.title.strip(), 'level': request.level_band, 'actor': user['user_id']}).scalar_one()
        version = db.execute(text('''INSERT INTO app_private.rubric_template_versions(template_id,version_number,created_by,mandatory_weight_total,nice_to_have_weight_total)
            VALUES (:template,1,:actor,:mandatory,:nice) RETURNING template_version_id'''),
            {'template': template, 'actor': user['user_id'], 'mandatory': request.mandatory_weight_total, 'nice': request.nice_to_have_weight_total}).scalar_one()
        _replace_items(db, version, request.items)
        _audit(db, user['user_id'], 'CREATE_RUBRIC_DRAFT', version)
        data = _version(db, version); db.commit(); return data
    except Exception: db.rollback(); raise
    finally: db.close()


@router.put('/versions/{version_id}')
def update_draft(version_id: UUID, request: UpdateDraft, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        row = db.execute(text('SELECT * FROM app_private.rubric_template_versions WHERE template_version_id=:id FOR UPDATE'), {'id': str(version_id)}).mappings().first()
        if not row: raise HTTPException(404, 'Không tìm thấy rubric')
        _require_editor(db, user['user_id'], row['created_by'])
        if row['status'] != 'DRAFT' or row['revision'] != request.expected_revision:
            raise HTTPException(409, 'Rubric đã thay đổi hoặc không còn là bản nháp')
        db.execute(text('''UPDATE app_private.rubric_template_versions SET mandatory_weight_total=:mandatory,
            nice_to_have_weight_total=:nice,revision=revision+1 WHERE template_version_id=:id'''),
            {'id': str(version_id), 'mandatory': request.mandatory_weight_total, 'nice': request.nice_to_have_weight_total})
        _replace_items(db, version_id, request.items)
        _audit(db, user['user_id'], 'UPDATE_RUBRIC_DRAFT', version_id)
        data = _version(db, version_id); db.commit(); return data
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post('/versions/{version_id}/publish')
def publish(version_id: UUID, request: PublishTemplate, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        row = db.execute(text('SELECT * FROM app_private.rubric_template_versions WHERE template_version_id=:id'), {'id': str(version_id)}).mappings().first()
        if not row: raise HTTPException(404, 'Không tìm thấy rubric')
        db.execute(text('SELECT 1 FROM app_private.rubric_templates WHERE template_id=:id FOR UPDATE'), {'id': row['template_id']})
        row = db.execute(text('SELECT * FROM app_private.rubric_template_versions WHERE template_version_id=:id FOR UPDATE'), {'id': str(version_id)}).mappings().one()
        roles, _ = _require_directory(db, user['user_id'], lock=True)
        if 'HR_LEAD' not in roles: raise HTTPException(403, 'Chỉ HR Lead được xuất bản rubric')
        if row['status'] != 'DRAFT' or row['revision'] != request.expected_revision: raise HTTPException(409, 'Bản nháp đã thay đổi hoặc không còn hiệu lực')
        groups = db.execute(text('''SELECT category,SUM(weight_in_group) AS total, MAX(weight_in_group) AS max_weight
            FROM app_private.rubric_template_items WHERE template_version_id=:id GROUP BY category'''), {'id': str(version_id)}).mappings().all()
        if not any(r['category'] == 'MUST_HAVE' and r['max_weight'] > 0 for r in groups) or any(r['total'] != 100 for r in groups):
            raise HTTPException(400, 'Cần tiêu chí bắt buộc và tổng trọng số mỗi nhóm bằng 100')
        archived = db.execute(text("UPDATE app_private.rubric_template_versions SET status='ARCHIVED' WHERE template_id=:template AND status='PUBLISHED' RETURNING template_version_id"), {'template': row['template_id']}).scalars().all()
        for old_version in archived:
            _audit(db, user['user_id'], 'ARCHIVE_RUBRIC_VERSION', old_version)
        db.execute(text("UPDATE app_private.rubric_template_versions SET status='PUBLISHED', published_by=:actor,published_at=now() WHERE template_version_id=:id"), {'id': str(version_id), 'actor': user['user_id']})
        _audit(db, user['user_id'], 'PUBLISH_RUBRIC', version_id)
        data = _version(db, version_id); db.commit(); return data
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post('/versions/{version_id}/clone', status_code=201)
def clone_version(version_id: UUID, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        source = _version(db, version_id)
        db.execute(text('SELECT 1 FROM app_private.rubric_templates WHERE template_id=:id FOR UPDATE'), {'id': source['template_id']})
        source = _version(db, version_id)
        _require_editor(db, user['user_id'])
        if source['status'] != 'PUBLISHED': raise HTTPException(409, 'Chỉ sao chép phiên bản đã xuất bản')
        if db.execute(text("SELECT 1 FROM app_private.rubric_template_versions WHERE template_id=:id AND status='DRAFT'"), {'id': source['template_id']}).first():
            raise HTTPException(409, 'Rubric đã có bản nháp')
        version = db.execute(text('''INSERT INTO app_private.rubric_template_versions(template_id,version_number,created_by,mandatory_weight_total,nice_to_have_weight_total)
            SELECT :template,COALESCE(MAX(version_number),0)+1,:actor,:mandatory,:nice FROM app_private.rubric_template_versions WHERE template_id=:template RETURNING template_version_id'''),
            {'template': source['template_id'], 'actor': user['user_id'], 'mandatory': source['mandatory_weight_total'], 'nice': source['nice_to_have_weight_total']}).scalar_one()
        db.execute(text('''INSERT INTO app_private.rubric_template_items(template_version_id,name,description,category,weight_in_group,expected_evidence_keywords,requirement_spec,evidence_guidance,display_order)
            SELECT :new,name,description,category,weight_in_group,expected_evidence_keywords,requirement_spec,evidence_guidance,display_order
            FROM app_private.rubric_template_items WHERE template_version_id=:old'''), {'new': version, 'old': str(version_id)})
        _audit(db, user['user_id'], 'CLONE_RUBRIC_VERSION', version)
        data = _version(db, version); db.commit(); return data
    except Exception: db.rollback(); raise
    finally: db.close()


@router.post('/positions/{position_id}/apply', status_code=201)
def apply_template(position_id: UUID, request: ApplyTemplate, user: dict = Depends(get_current_user)):
    db = SessionLocal()
    try:
        if not db.execute(text('SELECT 1 FROM app_private.positions WHERE position_id=:id FOR UPDATE'), {'id': str(position_id)}).first():
            raise HTTPException(404, 'Không tìm thấy vị trí')
        roles, _ = _require_directory(db, user['user_id'], lock=True)
        assigned = db.execute(text("SELECT 1 FROM app_private.position_assignments WHERE position_id=:position AND user_id=:actor AND position_role IN ('HR_RECRUITER','HR_LEAD') AND revoked_at IS NULL FOR SHARE"), {'position': str(position_id), 'actor': user['user_id']}).first()
        if not assigned and not roles.intersection({'HR_LEAD','ADMIN'}): raise HTTPException(403, 'Chỉ HR phụ trách được áp dụng rubric')
        db.execute(text('SELECT 1 FROM app_private.rubric_template_versions WHERE template_version_id=:id FOR SHARE'), {'id': str(request.template_version_id)})
        source = _version(db, request.template_version_id)
        if source['status'] != 'PUBLISHED': raise HTTPException(409, 'Chỉ dùng rubric đã xuất bản')
        jd = db.execute(text('SELECT jd_version_id FROM app_private.jd_versions WHERE position_id=:id ORDER BY version_number DESC LIMIT 1'), {'id': str(position_id)}).scalar_one_or_none()
        if not jd: raise HTTPException(400, 'Vị trí chưa có JD')
        if db.execute(text("SELECT 1 FROM app_private.criteria_versions WHERE position_id=:pos AND jd_version_id=:jd AND status IN ('DRAFT','PENDING_HR_REVIEW','PENDING_HM_APPROVAL')"), {'pos': str(position_id), 'jd': jd}).first():
            raise HTTPException(409, 'Vị trí đã có tiêu chí đang xử lý')
        version = db.execute(text('''INSERT INTO app_private.criteria_versions(position_id,jd_version_id,version_number,origin,status,mandatory_weight_total,nice_to_have_weight_total,source_template_version_id)
            SELECT :pos,:jd,COALESCE(MAX(version_number),0)+1,'TEMPLATE_CLONE','DRAFT',:mandatory,:nice,:source
            FROM app_private.criteria_versions WHERE position_id=:pos RETURNING criteria_version_id'''),
            {'pos': str(position_id), 'jd': jd, 'mandatory': source['mandatory_weight_total'], 'nice': source['nice_to_have_weight_total'], 'source': str(request.template_version_id)}).scalar_one()
        db.execute(text('''INSERT INTO app_private.criteria_items(criteria_version_id,name,description,category,weight_in_group,expected_evidence_keywords,requirement_spec,evidence_guidance,display_order,source_template_item_id)
            SELECT :version,name,description,category,weight_in_group,expected_evidence_keywords,requirement_spec,evidence_guidance,display_order,template_item_id
            FROM app_private.rubric_template_items WHERE template_version_id=:source'''), {'version': version, 'source': str(request.template_version_id)})
        _audit(db, user['user_id'], 'APPLY_RUBRIC_TEMPLATE', request.template_version_id, position_id)
        db.commit(); return {'criteria_version_id': version, 'status': 'DRAFT'}
    except Exception: db.rollback(); raise
    finally: db.close()
