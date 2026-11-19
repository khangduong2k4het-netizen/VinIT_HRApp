"""API dọn dữ liệu test cho ADMIN.

Tách khỏi ``admin.py`` vì đây là thao tác phá huỷ, cần đọc riêng mới thấy hết
ràng buộc. Mọi endpoint đều yêu cầu role ADMIN — không có ngoại lệ, kể cả
``preview`` (đếm dữ liệu cũng là thông tin nội bộ).
"""
from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field
from sqlalchemy import text

from app.core.permissions import require_admin_role
from app.db.database import SessionLocal
from app.services import test_data_purge as purge
from app.services.test_data_purge import PurgeError

router = APIRouter()


class PurgePreviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: list[str] = Field(min_length=1, max_length=10)


class PurgeExecuteRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scopes: list[str] = Field(min_length=1, max_length=10)
    # Bắt buộc: xoá hàng trăm dòng bằng một cú bấm phải có bước gõ lại.
    confirmation: str = Field(min_length=1, max_length=64)


def _raise(error: PurgeError) -> None:
    raise HTTPException(status_code=error.status_code, detail=error.detail) from None


@router.get("/scopes")
def list_scopes(current_user: dict = Depends(require_admin_role)):
    """Các nhóm dữ liệu có thể xoá. FE dựng checkbox từ đây, không hard-code."""
    return {
        "scopes": [
            {
                "code": code,
                "label": meta["label"],
                "description": meta["description"],
                "pulls_in": sorted(purge.IMPLIED.get(code, set())),
            }
            for code, meta in purge.SCOPES.items()
        ],
        "confirmation_phrase": purge.CONFIRMATION_PHRASE,
        "protected_tables": sorted(
            t.split('.', 1)[1] for t in purge.PROTECTED_TABLES if t.startswith('app_private.')
        ),
    }


@router.post("/preview")
def preview_purge(
    request: PurgePreviewRequest,
    current_user: dict = Depends(require_admin_role),
):
    """Đếm dữ liệu sẽ mất. Không thay đổi gì. Bước bắt buộc trước khi xoá."""
    db = SessionLocal()
    try:
        return purge.preview(db, request.scopes)
    except PurgeError as exc:
        _raise(exc)
    finally:
        db.close()


@router.post("/execute")
def execute_purge(
    request: PurgeExecuteRequest,
    current_user: dict = Depends(require_admin_role),
):
    """Xoá dữ liệu test. Transaction tường minh, không để trạng thái nửa vời."""
    db = SessionLocal()
    try:
        # Transaction tường minh ở tầng API, không ở service: service không được
        # tự commit, nhờ vậy mọi lỗi giữa chừng đều rollback cả lô.
        db.execute(text("SET LOCAL statement_timeout = '120s'"))

        try:
            result = purge.execute(
                db,
                scopes=request.scopes,
                confirmation=request.confirmation,
                actor_user_id=str(current_user["user_id"]),
            )
        except PurgeError:
            db.rollback()
            raise
        except Exception:
            # Không để lộ SQL/lỗi nội bộ ra response.
            db.rollback()
            raise HTTPException(
                status_code=500,
                detail="Không xoá được dữ liệu — đã huỷ toàn bộ, không có gì bị mất",
            ) from None

        # Commit TRƯỚC khi đụng Storage: nếu commit lỗi thì file vẫn còn.
        db.commit()

        # Storage không nguyên tử với PostgreSQL. Lỗi ở đây không làm thao tác
        # thất bại, nhưng phải báo để ADMIN biết còn file mồ côi.
        storage, storage_error = purge.delete_documents_from_storage(
            db,
            result.pop("storage_originals", []),
            result.pop("storage_extracted", []),
        )

        return {**result, "storage": storage, "storage_error": storage_error}
    finally:
        db.close()
