"""Thông báo trong ứng dụng.

Phạm vi đã chốt: **trong app trước, email sau**. Module này vì vậy cố ý không có
khái niệm "đã gửi" — chỉ có "chưa đọc / đã đọc". Thêm `sent_at` bây giờ là thêm
một cột không ai cập nhật, và cột đó sẽ bị đọc như bằng chứng đã gửi thư.

Đọc và ghi đều giới hạn ở chính người dùng: `user_id = :actor` nằm trong **mọi**
câu, kể cả câu đánh dấu đã đọc. Không có endpoint nào cho ADMIN đọc hộ — không
cần, và mỗi endpoint như vậy là một chỗ nữa phải kiểm quyền.
"""
from datetime import datetime
from typing import Any
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.security import HTTPAuthorizationCredentials
from pydantic import BaseModel, Field
from sqlalchemy import text

from app.core.security import get_current_user
from app.db.database import SessionLocal

router = APIRouter()

# Giới hạn cứng: badge chỉ cần "còn bao nhiêu", và không màn nào cuộn quá 200 dòng.
MAX_ITEMS = 200


class MarkRead(BaseModel):
    notification_ids: list[UUID] = Field(default_factory=list, max_length=MAX_ITEMS)


def _require_active(db, actor: str) -> None:
    status = db.execute(text(
        "SELECT account_status FROM app_private.user_profiles WHERE user_id = :actor"
    ), {"actor": actor}).scalar_one_or_none()
    if status != "ACTIVE":
        raise HTTPException(403, "Tài khoản không hoạt động")


@router.get("")
def list_notifications(unread_only: bool = Query(False), limit: int = Query(50, ge=1, le=MAX_ITEMS),
                       user: dict = Depends(get_current_user)) -> dict[str, Any]:
    """Thông báo của chính người dùng, mới nhất trước, kèm số chưa đọc.

    `unread_count` trả **luôn** kể cả khi chỉ xin danh sách đã đọc: badge trên
    header cần con số này ở mọi lần tải, và gọi thêm một endpoint chỉ để lấy một
    số nguyên là hai lần chờ cho một màn hình.
    """
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        clauses = ["user_id = :actor"]
        if unread_only:
            clauses.append("read_at IS NULL")
        rows = db.execute(text(f"""
            SELECT n.notification_id, n.interview_id, n.kind, n.payload,
                   n.read_at, n.created_at, n.actor_user_id,
                   up.display_name AS actor_name,
                   i.round_number, i.starts_at, i.status AS interview_status,
                   p.position_code, p.title AS position_title
            FROM app_private.interview_notifications n
            JOIN app_private.interviews i ON i.interview_id = n.interview_id
            JOIN app_private.applications a ON a.application_id = i.application_id
            JOIN app_private.positions p ON p.position_id = a.position_id
            LEFT JOIN app_private.user_profiles up ON up.user_id = n.actor_user_id
            WHERE {' AND '.join(clauses)}
            ORDER BY n.created_at DESC, n.notification_id
            LIMIT :limit
        """), {"actor": actor, "limit": limit}).mappings().all()
        unread = db.execute(text("""
            SELECT count(*) FROM app_private.interview_notifications
            WHERE user_id = :actor AND read_at IS NULL
        """), {"actor": actor}).scalar_one()
        return {
            "unread_count": int(unread or 0),
            "items": [
                {**dict(row), "notification_id": str(row["notification_id"]),
                 "interview_id": str(row["interview_id"])}
                for row in rows
            ],
        }
    finally:
        db.close()


@router.post("/read")
def mark_read(payload: MarkRead, user: dict = Depends(get_current_user)) -> dict[str, int]:
    """Đánh dấu đã đọc một loạt. Không truyền id nào = đánh dấu **tất cả**.

    Vì sao cho phép "tất cả": người dùng mở chuông rồi bấm "đọc hết" là thao tác
    bình thường; bắt client gửi 200 id thì mỗi lần bấm là một request lớn và còn
    trượt nếu có thông báo mới chen vào giữa.
    """
    db = SessionLocal()
    try:
        actor = user["user_id"]
        _require_active(db, actor)
        if payload.notification_ids:
            ids = [str(x) for x in payload.notification_ids]
            result = db.execute(text("""
                UPDATE app_private.interview_notifications
                   SET read_at = now()
                 WHERE user_id = :actor AND read_at IS NULL
                   AND notification_id = ANY(CAST(:ids AS uuid[]))
            """), {"actor": actor, "ids": "{" + ",".join(ids) + "}"})
        else:
            result = db.execute(text("""
                UPDATE app_private.interview_notifications
                   SET read_at = now()
                 WHERE user_id = :actor AND read_at IS NULL
            """), {"actor": actor})
        db.commit()
        return {"marked": int(result.rowcount or 0)}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()
