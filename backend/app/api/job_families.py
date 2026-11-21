"""Nhóm vị trí (job_families) — API quản trị.

Vì sao cần: nhóm vị trí là sợi dây nối vị trí với thư viện rubric. Trước module
này, thêm một nhóm mới phải chạy SQL tay trên DB thật — nghĩa là chỉ người có
quyền vào database mới mở được một ngành tuyển dụng mới.

Ba quyết định, đều cố ý:

* **Không xoá được, chỉ tắt.** Một nhóm đã có rubric mẫu hoặc vị trí thì xoá sẽ
  kéo theo dữ liệu lịch sử; xoá cứng còn làm `positions.job_family_id` thành
  NULL và vị trí mất chỗ đứng trong thư viện. Cùng lý do với phòng ban: tắt thay
  vì xoá. Khác một điểm — ở đây **không có** endpoint DELETE, để không ai phải
  nhớ "đừng bấm nút này"; không có nút thì không bấm nhầm.
* **`code` bất biến sau khi tạo.** Nó là khoá nghiệp vụ mà rubric mẫu và báo
  cáo có thể tham chiếu; đổi mã của một nhóm đang dùng là đổi nghĩa dữ liệu cũ.
  Tên (`name`) thì đổi được — tên là để hiển thị.
* **`code` chuẩn hoá thành CHỮ_HOA_CÓ_GẠCH.** Nhóm có sẵn dùng dạng
  `IT_DIGITAL`, `ADMIN_OPERATIONS`; cho nhập tự do thì hai nhóm sẽ có mã gần
  giống nhau và không ai tra nổi.
"""
import re
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query, status
from pydantic import BaseModel, Field
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()

_CODE_PATTERN = re.compile(r"^[A-Z][A-Z0-9_]{1,49}$")


class JobFamily(BaseModel):
    job_family_id: UUID
    code: str
    name: str
    is_active: bool
    position_count: int = 0
    template_count: int = 0


class JobFamilyCreate(BaseModel):
    code: str = Field(min_length=2, max_length=50)
    name: str = Field(min_length=1, max_length=200)


class JobFamilyUpdate(BaseModel):
    """Chỉ tên và trạng thái. `code` không có trong đây — xem docstring module."""
    name: str | None = Field(default=None, min_length=1, max_length=200)
    is_active: bool | None = None


def _require_admin_write(db, user_id: str) -> None:
    """Kiểm lại quyền ADMIN bên trong transaction ghi.

    Cùng khuôn với `departments.py`: token còn hạn không có nghĩa là quyền còn.
    Đọc lại trong transaction thì một lần thu hồi quyền đang diễn ra không chen
    được vào giữa bước kiểm và bước ghi.
    """
    account = db.execute(text("""
        SELECT account_status FROM app_private.user_profiles
        WHERE user_id = :user_id FOR SHARE
    """), {"user_id": user_id}).scalar_one_or_none()
    roles = db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id = :user_id AND role_code = 'ADMIN' AND revoked_at IS NULL FOR SHARE
    """), {"user_id": user_id}).scalars().all()
    if account != "ACTIVE" or not roles:
        raise HTTPException(status_code=403, detail="Chỉ Admin được quản lý nhóm vị trí")


def normalize_code(value: str) -> str:
    """`IT Digital` / `it-digital` / ` IT_DIGITAL ` → `IT_DIGITAL`."""
    cleaned = re.sub(r"[^A-Za-z0-9]+", "_", (value or "").strip()).strip("_").upper()
    if not _CODE_PATTERN.match(cleaned):
        raise HTTPException(
            status_code=400,
            detail="Mã nhóm phải bắt đầu bằng chữ và chỉ gồm chữ, số, dấu gạch dưới (2–50 ký tự).",
        )
    return cleaned


def _normalize_payload(values: dict) -> dict:
    normalized = dict(values)
    if normalized.get("name") is not None:
        normalized["name"] = " ".join(str(normalized["name"]).split())
        if not normalized["name"]:
            raise HTTPException(status_code=400, detail="Tên nhóm không được để trống")
    if normalized.get("code") is not None:
        normalized["code"] = normalize_code(normalized["code"])
    return normalized


def _audit(db, user_id: str, action: str, family_id: str, extra: dict | None = None) -> None:
    import json
    db.execute(text("""
        INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome, metadata)
        VALUES (:user_id, :action, 'JOB_FAMILY', :id, 'SUCCESS', CAST(:metadata AS jsonb))
    """), {"user_id": user_id, "action": action, "id": str(family_id),
           "metadata": json.dumps(extra or {})})


@router.get("", response_model=list[JobFamily])
def list_job_families(
    include_inactive: bool = Query(False),
    current_user: dict = Depends(get_current_user),
):
    """Danh sách nhóm vị trí kèm số vị trí và số rubric mẫu.

    Hai con số đếm không phải để trang trí: chúng là thứ duy nhất cho biết tắt
    một nhóm có ảnh hưởng gì. Nhóm 0 vị trí, 0 rubric thì tắt vô hại.
    """
    db = SessionLocal()
    try:
        if include_inactive:
            _require_admin_write(db, current_user["user_id"])
        rows = db.execute(text("""
            SELECT f.*,
                   (SELECT count(*) FROM app_private.positions p
                     WHERE p.job_family_id = f.job_family_id) AS position_count,
                   (SELECT count(*) FROM app_private.rubric_templates t
                     WHERE t.job_family_id = f.job_family_id) AS template_count
            FROM app_private.job_families f
            WHERE (:include_inactive OR f.is_active)
            ORDER BY f.name, f.job_family_id
        """), {"include_inactive": include_inactive}).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("", response_model=JobFamily, status_code=status.HTTP_201_CREATED)
def create_job_family(payload: JobFamilyCreate, current_user: dict = Depends(get_current_user)):
    values = _normalize_payload(payload.model_dump())
    db = SessionLocal()
    try:
        _require_admin_write(db, current_user["user_id"])
        row = db.execute(text("""
            INSERT INTO app_private.job_families (code, name, is_active)
            VALUES (:code, :name, true) RETURNING *
        """), values).mappings().one()
        _audit(db, current_user["user_id"], "CREATE_JOB_FAMILY", row["job_family_id"],
               {"code": row["code"], "name": row["name"]})
        db.commit()
        return {**dict(row), "position_count": 0, "template_count": 0}
    except IntegrityError:
        db.rollback()
        raise HTTPException(status_code=409, detail="Mã nhóm đã tồn tại") from None
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.patch("/{job_family_id}", response_model=JobFamily)
def update_job_family(job_family_id: UUID, payload: JobFamilyUpdate,
                      current_user: dict = Depends(get_current_user)):
    values = _normalize_payload(payload.model_dump(exclude_unset=True))
    # `is_active` phải đi qua kể cả khi bằng False — lọc `is not None` như phòng
    # ban là đúng cho chuỗi, nhưng ở đây tắt một nhóm chính là giá trị False.
    values = {k: v for k, v in values.items() if v is not None or k == "is_active"}
    if not values:
        raise HTTPException(status_code=400, detail="Không có nội dung cần cập nhật")
    db = SessionLocal()
    try:
        _require_admin_write(db, current_user["user_id"])
        if not db.execute(text(
            "SELECT 1 FROM app_private.job_families WHERE job_family_id=:id FOR UPDATE"
        ), {"id": str(job_family_id)}).first():
            raise HTTPException(status_code=404, detail="Không tìm thấy nhóm vị trí")
        if values.get("is_active") is False:
            # Không chặn cứng: một nhóm lỡ tạo cần tắt được. Nhưng phải biết
            # tắt nó ảnh hưởng gì — vị trí đang dùng nhóm này sẽ không chọn
            # được nhóm nữa ở form tạo/sửa (kiểm is_active), nên nếu còn vị trí
            # đang dùng thì trả 409 kèm số lượng, thay vì im lặng tắt.
            in_use = db.execute(text("""
                SELECT count(*) FROM app_private.positions
                WHERE job_family_id = :id
            """), {"id": str(job_family_id)}).scalar_one()
            if in_use:
                raise HTTPException(
                    status_code=409,
                    detail=f"Nhóm vị trí đang được {in_use} vị trí dùng. Chuyển các vị trí đó sang nhóm khác trước khi tắt.",
                )
        sets = ", ".join(f"{k} = :{k}" for k in values)
        row = db.execute(text(f"""
            UPDATE app_private.job_families SET {sets}
            WHERE job_family_id = :id RETURNING *
        """), {**values, "id": str(job_family_id)}).mappings().one()
        if "name" in values:
            # ``positions.job_family`` là bản sao tên nhóm lúc gán, không phải
            # nguồn đọc (``/careers`` và mọi bộ lọc đã chuyển sang bảng). Nhưng
            # để nó lệch lại còn tệ hơn không có: báo cáo cũ đọc cột này sẽ ra
            # một cái tên không còn tồn tại ở đâu khác. Cập nhật trong cùng
            # transaction với lần đổi tên để hai chỗ không bao giờ lệch nhau.
            db.execute(text("""
                UPDATE app_private.positions SET job_family = :name
                WHERE job_family_id = :id
            """), {"name": row["name"], "id": str(job_family_id)})
        _audit(db, current_user["user_id"], "UPDATE_JOB_FAMILY", job_family_id,
               {"fields": sorted(values), "is_active": row["is_active"]})
        db.commit()
        counts = db.execute(text("""
            SELECT (SELECT count(*) FROM app_private.positions WHERE job_family_id = :id) AS position_count,
                   (SELECT count(*) FROM app_private.rubric_templates WHERE job_family_id = :id) AS template_count
        """), {"id": str(job_family_id)}).mappings().one()
        return {**dict(row), **dict(counts)}
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
