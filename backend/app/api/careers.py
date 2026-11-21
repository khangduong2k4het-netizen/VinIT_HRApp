"""Public listing, explicitly enabled only after HR reviews the OPEN JDs.

Router này chỉ ĐỌC. Việc nhận hồ sơ nằm ở ``careers_intake.py``, và chỉ những
vị trí trả về ở đây với ``accepting_applications=true`` mới thực sự nhận được.
"""
from uuid import UUID

from fastapi import APIRouter, HTTPException, Query, Response
from sqlalchemy import text

from app.core.config import settings
from app.db.database import SessionLocal

router = APIRouter()


@router.get('/jobs')
def jobs(response: Response, cursor: UUID | None = None, limit: int = Query(25, ge=1, le=100),
         employment_type: str | None = Query(None, max_length=60),
         job_family: str | None = Query(None, max_length=120)):
    """Danh sách việc đang tuyển. Chỉ trả về vị trí THỰC SỰ nhận được hồ sơ.

    Vì sao phải lọc chứ không trả hết rồi để giao diện làm mờ nút: một tin đăng
    hiện ra trên trang tuyển dụng mà ứng viên bấm vào lại không nộp được là lỗi
    nghiêm trọng hơn nhiều so với việc tin đó không hiện. Ứng viên không quan
    tâm tin đó "sắp mở" hay "thiếu rubric" — với họ, hệ thống chỉ đơn giản là
    hỏng. Nên điều kiện nhận hồ sơ được kiểm ở đây, trước khi trả về.

    Hai lớp điều kiện, cố ý tách rời:

    * Điều kiện nghiệp vụ (luôn áp dụng): vị trí OPEN, còn hạn, và có rubric đã
      duyệt cho đúng phiên bản JD đang hiển thị. Không có rubric thì HR cũng
      không chấm được hồ sơ nhận vào, nên nhận hồ sơ lúc đó là nhận rồi để đó.
    * Điều kiện vận hành: cờ PUBLIC_CAREERS_TEST_INTAKE_ENABLED **và** có khả
      năng quét tệp. Chưa đạt thì trả danh sách RỖNG kèm lý do
      `INTAKE_NOT_OPEN` — không phải trả tin rồi làm mờ nút gửi. Chính sách đã
      chốt: chưa mở nhận hồ sơ thì trang không mời nộp.

    Giao diện dựa vào `accepting_applications` để biết có hiện nút ứng tuyển hay
    không, thay vì tự suy ra từ cờ cấu hình.
    """
    response.headers['Cache-Control'] = 'no-store'
    if not settings.PUBLIC_CAREERS_ENABLED:
        raise HTTPException(404, 'Không khả dụng', headers={'Cache-Control': 'no-store'})
    db = SessionLocal()
    try:
        # UUID keyset pagination keeps all eligible jobs available beyond the
        # first page.
        rows = db.execute(text("""
            SELECT p.position_id, p.position_code, p.title, p.org_unit, p.work_location,
                   p.work_mode, p.employment_type, p.application_deadline_at,
                   p.job_family,
                   jd.content_text AS description,
                   EXISTS (SELECT 1 FROM app_private.criteria_versions c
                     WHERE c.position_id=p.position_id AND c.status='APPROVED'
                       AND c.jd_version_id=jd.jd_version_id) AS rubric_approved
            FROM app_private.positions p
            LEFT JOIN LATERAL (
                SELECT jd_version_id, content_text FROM app_private.jd_versions
                WHERE position_id=p.position_id ORDER BY version_number DESC LIMIT 1
            ) jd ON TRUE
            WHERE p.status='OPEN' AND p.application_deadline_at > statement_timestamp()
              -- Chỉ tin có JD thật: tin không có JD thì ứng viên bấm vào cũng
              -- không biết mình ứng tuyển cho việc gì.
              AND jd.content_text IS NOT NULL AND btrim(jd.content_text) <> ''
              -- Rubric đã duyệt cho đúng phiên bản JD đang hiển thị.
              AND EXISTS (SELECT 1 FROM app_private.criteria_versions c
                            WHERE c.position_id=p.position_id AND c.status='APPROVED'
                              AND c.jd_version_id=jd.jd_version_id)
              AND (:employment_type IS NULL OR p.employment_type = :employment_type)
              AND (:job_family IS NULL OR p.job_family = :job_family)
              AND (:cursor IS NULL OR p.position_id > CAST(:cursor AS uuid))
            ORDER BY p.position_id LIMIT :limit
        """), {'cursor': str(cursor) if cursor else None, 'limit': limit + 1,
               'employment_type': employment_type, 'job_family': job_family}).mappings().all()
        page = rows[:limit]
        # Máy quét hỏng thì không nhận được tệp, nên cũng không mời nộp.
        intake_ready = bool(
            settings.PUBLIC_CAREERS_TEST_INTAKE_ENABLED
            and (settings.CLAMAV_UNIX_SOCKET.startswith('/')
                 or settings.PUBLIC_CAREERS_UNSCANNED_FILES_ENABLED)
        )
        if not intake_ready:
            # Chưa mở nhận hồ sơ thì KHÔNG hiện tin nào. Một trang tuyển dụng
            # liệt kê việc mà bấm vào không nộp được là trang hỏng, không phải
            # trang "đang cập nhật" — ứng viên không đọc thông báo, họ chỉ thấy
            # nút chết. Trả danh sách rỗng kèm lý do để giao diện giải thích.
            return {'items': [], 'next_cursor': None, 'accepting_applications': False,
                    'reason': 'INTAKE_NOT_OPEN'}
        items = []
        for row in page:
            item = dict(row)
            item['accepting_applications'] = intake_ready
            item['can_apply_test'] = intake_ready          # giữ tên cũ cho FE đang dùng
            item.pop('rubric_approved', None)
            items.append(item)
        return {'items': items,
                'next_cursor': str(page[-1]['position_id']) if len(rows) > limit else None}
    finally:
        db.close()


@router.get('/filters')
def filters(response: Response):
    """Giá trị lọc có thật trong dữ liệu — không bày ra bộ lọc rỗng.

    Trang tham khảo của VinUni có cột "Jobs type" và "Field/Industry". Chỉ trả
    về những giá trị đang có ít nhất một tin còn hạn, để ứng viên không bấm vào
    một bộ lọc rồi nhận danh sách trống.
    """
    response.headers['Cache-Control'] = 'no-store'
    if not settings.PUBLIC_CAREERS_ENABLED:
        raise HTTPException(404, 'Không khả dụng', headers={'Cache-Control': 'no-store'})
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT p.employment_type, p.job_family, count(*) AS n
            FROM app_private.positions p
            WHERE p.status='OPEN' AND p.application_deadline_at > statement_timestamp()
            GROUP BY p.employment_type, p.job_family
        """)).mappings().all()
        types: dict[str, int] = {}
        families: dict[str, int] = {}
        for row in rows:
            if row['employment_type']:
                types[row['employment_type']] = types.get(row['employment_type'], 0) + int(row['n'])
            if row['job_family']:
                families[row['job_family']] = families.get(row['job_family'], 0) + int(row['n'])
        return {
            'employment_types': [{'value': k, 'count': v} for k, v in sorted(types.items())],
            'job_families': [{'value': k, 'count': v} for k, v in sorted(families.items())],
        }
    finally:
        db.close()
