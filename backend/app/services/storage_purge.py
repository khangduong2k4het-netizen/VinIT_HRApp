"""Đối soát và dọn file mồ côi trên Storage.

Vì sao cần: xoá dòng trong ``application_documents`` **không** xoá file trên
Storage (hai hệ thống khác nhau, không nguyên tử). Nếu chỉ xoá theo đường dẫn đã
biết thì mọi file mà DB "quên" sẽ nằm lại vĩnh viễn — đúng tình trạng 25 file
mồ côi đã gặp sau migration 00035.

Cách làm ở đây là **đối soát**: liệt kê toàn bộ file trong bucket, so với tập
đường dẫn mà DB còn trỏ tới, rồi xoá phần dư. Cách này:

* dọn được cả file mồ côi *cũ* (không còn dòng DB nào),
* không phụ thuộc việc đoán cấu trúc thư mục,
* và tự lành sau mỗi lần DB và Storage lệch nhau.

Ba chốt an toàn:

1. Chỉ chạy khi **không còn operation nào đang xử lý** — tránh xoá file vừa
   upload xong nhưng chưa kịp ghi dòng DB.
2. **Bỏ qua file mới hơn ``MIN_AGE_SECONDS``** — lá chắn cho upload đang chạy.
3. Nếu **không liệt kê được** bucket thì dừng, không xoá gì. Thà còn rác hơn
   xoá nhầm.
"""
from __future__ import annotations

from datetime import datetime, timedelta, timezone
from typing import Any

from sqlalchemy import text

from app.core.config import settings
from app.core.logging import get_logger
from app.services.retention import extracted_storage_paths

logger = get_logger(__name__)

#: File tạo trong khoảng này được giữ lại, phòng trường hợp đang tải lên dở.
MIN_AGE_SECONDS = 15 * 60

#: Số đường dẫn xoá mỗi lần gọi API — tránh request quá lớn.
DELETE_BATCH = 100

#: Giới hạn đệ quy: cấu trúc thật chỉ 3–4 cấp, sâu hơn là dấu hiệu lỗi.
MAX_DEPTH = 8


class StoragePurgeError(Exception):
    """Không đối soát được. Không phải lỗi xoá dở."""


def _client():
    from app.db.supabase import get_supabase_client

    client = get_supabase_client()
    if not client:
        raise StoragePurgeError("Supabase storage chưa được cấu hình")
    return client


def list_bucket_files(bucket: str) -> list[dict[str, Any]]:
    """Liệt kê **đệ quy** mọi file trong bucket.

    ``storage3`` 2.x không có list phẳng: ``list()`` chỉ trả một cấp, nên phải tự
    đi xuống. Phần tử là thư mục khi ``id`` là ``None`` / ``metadata`` là ``None``.
    """
    client = _client()
    proxy = client.storage.from_(bucket)
    found: list[dict[str, Any]] = []

    def walk(prefix: str, depth: int) -> None:
        if depth > MAX_DEPTH:
            raise StoragePurgeError(
                f"Thư mục lồng quá {MAX_DEPTH} cấp trong bucket {bucket} — dừng để an toàn"
            )
        try:
            entries = proxy.list(prefix, {"limit": 1000, "offset": 0})
        except Exception as exc:  # noqa: BLE001
            # Lỗi mạng/HTTP của SDK phải thành "không đối soát được", KHÔNG lan
            # ra thành 500 và tuyệt đối không được coi là "bucket rỗng".
            raise StoragePurgeError(
                f"Không liệt kê được thư mục trong bucket {bucket}"
            ) from exc
        for entry in entries or []:
            name = entry.get("name")
            if not name:
                continue
            # Không dùng os.path.join: Storage luôn dùng '/'.
            full = f"{prefix}/{name}" if prefix else name
            is_folder = entry.get("id") is None or entry.get("metadata") is None
            if is_folder:
                walk(full, depth + 1)
            else:
                found.append({
                    "path": full,
                    "created_at": entry.get("created_at"),
                    "size": (entry.get("metadata") or {}).get("size"),
                })

    walk("", 1)
    return found


def _parse_created(value: Any) -> datetime | None:
    if not value:
        return None
    if isinstance(value, datetime):
        return value if value.tzinfo else value.replace(tzinfo=timezone.utc)
    try:
        text = str(value).replace("Z", "+00:00")
        parsed = datetime.fromisoformat(text)
        return parsed if parsed.tzinfo else parsed.replace(tzinfo=timezone.utc)
    except ValueError:
        return None


def known_paths(db) -> dict[str, set[str]]:
    """Tập đường dẫn mà DB **còn** trỏ tới, theo từng bucket."""
    originals: set[str] = set()
    for row in db.execute(text("""
        SELECT bucket, storage_path FROM app_private.application_documents
        WHERE bucket IS NOT NULL AND storage_path IS NOT NULL
    """)).mappings().all():
        originals.add(str(row["storage_path"]))

    extracted: set[str] = set()
    for row in db.execute(text("""
        SELECT extracted_text_storage_path FROM app_private.document_processing_runs
        WHERE extracted_text_storage_path IS NOT NULL
    """)).all():
        for path in extracted_storage_paths(str(row[0])):
            extracted.add(path)

    return {
        settings.SUPABASE_STORAGE_BUCKET_CV: originals,
        settings.SUPABASE_STORAGE_BUCKET_EXTRACTED: extracted,
    }


def count_orphans(db) -> dict[str, Any]:
    """Đếm file mồ côi (không xoá gì). Dùng cho bước xem trước."""
    if settings.STORAGE_BACKEND != "supabase":
        return {"supported": False, "reason": f"STORAGE_BACKEND={settings.STORAGE_BACKEND}"}

    known = known_paths(db)
    report: dict[str, Any] = {"supported": True, "buckets": [], "total_orphans": 0}
    try:
        for bucket, keep in known.items():
            files = list_bucket_files(bucket)
            orphans = [f["path"] for f in files if f["path"] not in keep]
            report["buckets"].append({
                "bucket": bucket,
                "objects": len(files),
                "orphans": len(orphans),
            })
            report["total_orphans"] += len(orphans)
    except StoragePurgeError as exc:
        return {"supported": True, "error": str(exc), "buckets": [], "total_orphans": 0}
    return report


def sweep_orphans(db, *, dry_run: bool = False) -> dict[str, Any]:
    """Xoá mọi file trong hai bucket CV mà DB không còn trỏ tới.

    Caller phải gọi **sau khi commit** thao tác xoá DB.
    """
    if settings.STORAGE_BACKEND != "supabase":
        return {"swept": False, "reason": f"STORAGE_BACKEND={settings.STORAGE_BACKEND}"}

    try:
        _assert_worker_idle(db)
        known = known_paths(db)
        client = _client()
    except StoragePurgeError as exc:
        return {"swept": False, "reason": str(exc)}

    cutoff = datetime.now(timezone.utc) - timedelta(seconds=MIN_AGE_SECONDS)
    result: dict[str, Any] = {"swept": True, "buckets": [], "deleted": 0, "kept_fresh": 0}

    for bucket, keep in known.items():
        try:
            files = list_bucket_files(bucket)
        except StoragePurgeError as exc:
            # Không liệt kê được thì bỏ qua bucket đó, không xoá gì.
            result["buckets"].append({"bucket": bucket, "error": str(exc), "deleted": 0})
            result["swept"] = False
            continue

        to_delete: list[str] = []
        fresh = 0
        for item in files:
            if item["path"] in keep:
                continue
            created = _parse_created(item.get("created_at"))
            if created is not None and created > cutoff:
                # Có thể đang được upload; lần dọn sau sẽ xử lý.
                fresh += 1
                continue
            to_delete.append(item["path"])

        deleted = 0
        for start in range(0, len(to_delete), DELETE_BATCH):
            chunk = to_delete[start:start + DELETE_BATCH]
            if dry_run:
                deleted += len(chunk)
                continue
            try:
                client.storage.from_(bucket).remove(chunk)
                deleted += len(chunk)
            except Exception as exc:  # noqa: BLE001 - không lộ path ra response
                logger.error(
                    "Không xoá được file mồ côi", bucket=bucket,
                    error_type=type(exc).__name__, count=len(chunk),
                )
                result["swept"] = False
                break

        result["buckets"].append({
            "bucket": bucket, "deleted": deleted, "kept_fresh": fresh,
            "orphans_found": len(to_delete) + fresh,
        })
        result["deleted"] += deleted
        result["kept_fresh"] += fresh

    return result


def _assert_worker_idle(db) -> None:
    busy = db.execute(text("""
        SELECT count(*) FROM app_private.operations
        WHERE status IN ('PENDING', 'PROCESSING')
    """)).scalar()
    if busy:
        raise StoragePurgeError(
            f"Còn {busy} operation đang chạy — không đối soát Storage lúc này"
        )
