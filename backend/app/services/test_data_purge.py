"""Dọn dữ liệu test (CV / JD / vị trí) cho môi trường phát triển.

Vì sao cần module này thay vì để ADMIN chạy SQL tay:

* Xoá tay dễ sai thứ tự khoá ngoại. Ba chỗ đã từng sai khi làm thủ công:
  ``shortlist_share_items`` chặn ``ranking_items``, ``audit_events`` chặn
  ``positions``, ``assessment_runs`` chặn ``operations``.
* ``audit_events`` có trigger ``prevent_audit_event_mutation()`` chặn MỌI
  DELETE/UPDATE, **kể cả với role ``postgres``** (không phải superuser trên
  Supabase). Nên không thể vừa "xoá sạch" vừa "giữ log kiểm toán" trong cùng
  một transaction: xoá hết audit thì không còn dòng nào để ghi lại việc xoá.

Quyết định thiết kế: **xoá audit trước, ghi lại một sự kiện kiểm toán sau khi
xoá, và bắt buộc việc xoá phải diễn ra trong transaction tường minh.** Nếu bước
xoá thất bại, transaction rollback và log cũ còn nguyên — không có trạng thái
nửa vời.

Phạm vi: những gì là *dữ liệu test* (CV, JD, vị trí, chấm điểm, xếp hạng,
shortlist, vận hành). Giữ nguyên tài khoản, phòng ban, job family, cấu hình AI,
cấu hình ngưỡng — xoá những thứ đó thì phải dựng lại bằng Supabase Auth/dashboard,
không phải việc của một nút trong app.
"""
from __future__ import annotations

import json
from typing import Any

from sqlalchemy import text

from app.services.retention import delete_storage_objects

#: Nhóm dữ liệu ADMIN có thể chọn xoá. Mỗi nhóm là một tập bảng *đóng*: chọn
#: nhóm con thì phải kèm mọi nhóm mà nó phụ thuộc, nếu không FK sẽ chặn. Thay vì
#: để người dùng đoán, service tự mở rộng phạm vi và trả về danh sách đã mở rộng.
SCOPES: dict[str, dict[str, Any]] = {
    "CV": {
        "label": "Hồ sơ ứng viên và CV",
        "description": (
            "Toàn bộ hồ sơ ứng tuyển, tài liệu CV, text trích xuất, profile, "
            "bằng chứng, chấm điểm, xếp hạng và shortlist đi kèm."
        ),
        "requires": [],
    },
    "JD": {
        "label": "JD và rubric",
        "description": "JD, phiên bản tiêu chí, tiêu chí và lịch sử duyệt rubric.",
        "requires": [],
    },
    "POSITIONS": {
        "label": "Vị trí tuyển dụng",
        "description": "Vị trí, phân công, quyền truy cập, lịch sử trạng thái, yêu cầu tạo.",
        "requires": [],
    },
    "OPERATIONS": {
        "label": "Vận hành và kiểm toán",
        "description": (
            "Operation nền, lần xử lý tài liệu, batch CV, retention case, "
            "deletion job và log kiểm toán."
        ),
        "requires": [],
    },
}

#: Thứ tự xoá cố định: con trước, cha sau. Đây là *thứ tự duy nhất đã được kiểm
#: chứng chạy đúng* trên schema hiện tại; đừng sắp xếp lại theo alphabet.
DELETE_ORDER: list[tuple[str, str]] = [
    # (scope, table) — một bảng có thể xuất hiện một lần duy nhất ở đây.
    ("CV", "shortlist_scorecard_criteria"),
    ("CV", "scorecard_reopen_events"),
    ("CV", "shortlist_scorecards"),
    ("CV", "shortlist_feedback"),
    ("CV", "shortlist_share_items"),
    ("CV", "shortlist_shares"),
    ("CV", "ranking_items"),
    ("CV", "ranking_runs"),
    ("CV", "evidence_items"),
    ("CV", "hr_criterion_reviews"),
    ("CV", "criterion_assessment_results"),
    ("CV", "assessment_runs"),
    ("CV", "cv_chunk_embeddings"),
    ("CV", "profile_facts"),
    ("CV", "profile_versions"),
    ("CV", "application_documents"),
    ("CV", "duplicate_signals"),
    ("CV", "gmail_test_messages"),
    ("CV", "careers_intake_receipts"),
    ("CV", "talent_pool_consents"),
    ("CV", "application_private_notes"),
    ("CV", "application_status_events"),
    ("CV", "application_identities"),
    ("CV", "deletion_jobs"),
    ("CV", "deletion_events"),
    ("CV", "application_retention_cases"),
    ("CV", "applications"),
    ("OPERATIONS", "cv_batch_items"),
    ("OPERATIONS", "cv_batches"),
    ("OPERATIONS", "document_processing_runs"),
    ("OPERATIONS", "operation_recovery_events"),
    ("OPERATIONS", "operations"),
    ("JD", "criteria_approval_events"),
    ("JD", "criteria_items"),
    ("JD", "criteria_versions"),
    ("JD", "jd_versions"),
    ("POSITIONS", "position_create_requests"),
    ("POSITIONS", "position_access_grants"),
    ("POSITIONS", "position_assignments"),
    ("POSITIONS", "position_status_events"),
    # audit_events -> positions là NO ACTION: phải xoá audit TRƯỚC positions.
    ("OPERATIONS", "audit_events"),
    ("POSITIONS", "positions"),
]

#: Nhóm phụ thuộc kéo theo. Xoá JD mà còn vị trí trỏ tới JD đó thì FK chặn, nên
#: JD kéo theo POSITIONS; POSITIONS kéo theo JD (vì positions có FK tới jd_versions
#: ở chiều ngược lại thông qua assessment_runs/criteria_versions). Nói cách khác
#: hai nhóm này thực tế không tách rời được — service nói thẳng điều đó ra.
#:
#: POSITIONS cũng kéo theo OPERATIONS. Không phải vì "tiện tay": có 11 bảng
#: tham chiếu ``positions`` mà FK **không** CASCADE, trong đó có
#: ``audit_events``, ``applications``, ``assessment_runs``, ``cv_batches``,
#: ``duplicate_signals``, ``ranking_runs``/``ranking_items``,
#: ``shortlist_shares``/``shortlist_share_items`` và
#: ``careers_intake_receipts``. Chọn chỉ POSITIONS thì những bảng đó còn dòng và
#: PostgreSQL chặn ``DELETE FROM positions``. Đã kiểm từng FK trong
#: ``supabase/migrations``; thiếu ràng buộc này là lỗi thật, không phải phòng xa.
#:
#: Vì vậy thực tế không có đường tắt: hễ chạm tới vị trí là phải xoá CV, JD và
#: vận hành cùng lúc. Trước đây người dùng chọn "Vị trí" rồi nhận một lỗi FK khó
#: hiểu; nay service tự mở rộng phạm vi và ``preview`` nói rõ nhóm nào bị kéo
#: theo, để ADMIN thấy trước khi bấm xoá.
IMPLIED: dict[str, set[str]] = {
    "JD": {"POSITIONS", "OPERATIONS", "CV"},
    "POSITIONS": {"JD", "OPERATIONS", "CV"},
}

#: Tập đóng nhỏ nhất mà một lượt xoá chạy được. ``CV`` một mình vẫn hợp lệ (dữ
#: liệu CV không cần vị trí để bị xoá), nên đây chỉ là kiểm tra chéo cho test.
_REQUIRED_WITH_POSITIONS = frozenset({
    "applications", "assessment_runs", "careers_intake_receipts", "duplicate_signals",
    "ranking_items", "ranking_runs", "shortlist_share_items", "shortlist_shares",
    "audit_events", "cv_batches", "cv_batch_items", "position_create_requests",
    "position_assignments", "position_access_grants", "position_status_events",
    "document_processing_runs", "operations",
})

#: Những bảng *không bao giờ* chạm tới trong tính năng này.
PROTECTED_TABLES = frozenset({
    "auth.users",
    "app_private.user_profiles",
    "app_private.user_role_assignments",
    "app_private.departments",
    "app_private.job_families",
    "app_private.app_settings",
    "app_private.ai_configuration_versions",
    "app_private.ai_policy_versions",
    "app_private.assessment_policy_versions",
    "app_private.retention_policy_versions",
})

#: Chuỗi xác nhận ADMIN phải gõ đúng. Ngắn có chủ ý: người dùng đã yêu cầu đổi
#: từ "XOA DU LIEU TEST" sang "OK" cho đỡ vướng khi test trên VPS.
#:
#: Rào chắn thật nằm ở chỗ khác, không phải độ dài chuỗi: phải là ADMIN, phải
#: bấm "Đếm dữ liệu sẽ xoá" trước (UI khoá nút xoá), phạm vi luôn được mở rộng
#: tới tập đóng theo khoá ngoại, và toàn bộ chạy trong một transaction có rollback.
CONFIRMATION_PHRASE = "OK"


class PurgeError(Exception):
    """Lỗi có status code để API map sang HTTP, không lộ chi tiết nội bộ."""

    def __init__(self, detail: str, status_code: int = 400) -> None:
        super().__init__(detail)
        self.detail = detail
        self.status_code = status_code


def expand_scopes(scopes: list[str]) -> set[str]:
    """Mở rộng phạm vi đã chọn thành tập đóng theo phụ thuộc."""
    unknown = [s for s in scopes if s not in SCOPES]
    if unknown:
        raise PurgeError(f"Nhóm dữ liệu không hợp lệ: {', '.join(sorted(unknown))}", 422)
    if not scopes:
        raise PurgeError("Chưa chọn nhóm dữ liệu nào để xoá", 422)

    result = set(scopes)
    changed = True
    while changed:
        changed = False
        for scope in list(result):
            for implied in IMPLIED.get(scope, set()):
                if implied not in result:
                    result.add(implied)
                    changed = True
    return result


def tables_for(scopes: set[str]) -> list[str]:
    """Danh sách bảng sẽ xoá, theo đúng thứ tự, không trùng."""
    return [table for scope, table in DELETE_ORDER if scope in scopes]


def preview(db, scopes: list[str]) -> dict:
    """Đếm trước khi xoá. Không thay đổi dữ liệu.

    Đây là bước bắt buộc: một cú bấm xoá hàng trăm dòng mà không cho biết sẽ mất
    gì là thiết kế tồi, kể cả trên môi trường test.
    """
    chosen = expand_scopes(scopes)
    requested = set(scopes)
    implied = sorted(chosen - requested)

    tables = tables_for(chosen)
    counts: dict[str, int] = {}
    total = 0
    for table in tables:
        # Tên bảng lấy từ hằng số trong module này, không từ input người dùng.
        value = db.execute(text(f"SELECT count(*) FROM app_private.{table}")).scalar()
        n = int(value or 0)
        if n:
            counts[table] = n
            total += n

    storage = _storage_manifest(db, chosen)
    # Đối soát thật với Storage: file nào DB không còn trỏ tới sẽ bị dọn.
    # Đây là thứ khiến lần purge sau tự dọn được cả file mồ côi cũ.
    if "CV" in chosen:
        from app.services.storage_purge import count_orphans

        storage["orphans"] = count_orphans(db)

    return {
        "requested_scopes": sorted(requested),
        "effective_scopes": sorted(chosen),
        "implied_scopes": implied,
        # Câu giải thích cho người bấm nút: vì sao phạm vi bị mở rộng. Không có
        # câu này thì ADMIN chọn "Vị trí" và tự hỏi tại sao CV cũng mất.
        "scope_note": _scope_note(requested, chosen),
        "tables": [{"name": t, "rows": counts.get(t, 0)} for t in tables],
        "total_rows": total,
        "storage": storage,
        "protected": _protected_counts(db),
    }


def _scope_note(requested: set[str], chosen: set[str]) -> str | None:
    """Vì sao phạm vi đã chọn bị mở rộng — hiện ngay trên màn xác nhận."""
    pulled = sorted(chosen - requested)
    if not pulled:
        return None
    labels = ", ".join(SCOPES[code]["label"] for code in pulled if code in SCOPES)
    if "CV" in pulled:
        return (
            f"Phạm vi được mở rộng sang: {labels}. Bắt buộc vì hồ sơ ứng viên, "
            "chấm điểm, xếp hạng và shortlist đều tham chiếu tới vị trí — xoá vị "
            "trí mà giữ chúng sẽ bị khoá ngoại chặn. Nói cách khác: muốn xoá vị "
            "trí thì phải xoá cả dữ liệu CV đi kèm."
        )
    return f"Phạm vi được mở rộng sang: {labels} do ràng buộc khoá ngoại."


def _protected_counts(db) -> list[dict[str, Any]]:
    """Cho ADMIN thấy cái gì sẽ *không* mất — câu hỏi đầu tiên của mọi người."""
    rows = []
    for table in sorted(PROTECTED_TABLES):
        if not table.startswith("app_private."):
            # auth.users cần quyền riêng; đếm được qua app_private.user_profiles
            # là đủ và không phải đụng schema auth.
            continue
        bare = table.split(".", 1)[1]
        value = db.execute(text(f"SELECT count(*) FROM app_private.{bare}")).scalar()
        rows.append({"table": bare, "rows": int(value or 0)})
    return rows


def _storage_manifest(db, scopes: set[str]) -> dict[str, Any]:
    """File CV sẽ bị xoá khỏi Storage. Chỉ tính khi phạm vi có chạm tới tài liệu."""
    if "CV" not in scopes:
        return {"buckets": [], "objects": 0, "note": "Phạm vi này không xoá CV."}

    rows = db.execute(text("""
        SELECT bucket, count(*) AS n
        FROM app_private.application_documents
        WHERE bucket IS NOT NULL
        GROUP BY bucket ORDER BY bucket
    """)).mappings().all()
    buckets = [{"bucket": r["bucket"], "documents": int(r["n"])} for r in rows]
    total = sum(b["documents"] for b in buckets)
    return {
        "buckets": buckets,
        "objects": total,
        "note": (
            "Mỗi tài liệu có thể có 1 file gốc và 2 file text trích xuất "
            "(extracted.txt, pages.json). Số thực tế trên Storage có thể cao "
            "hơn số tài liệu."
        ),
    }


def execute(db, *, scopes: list[str], confirmation: str, actor_user_id: str) -> dict:
    """Xoá dữ liệu test. Caller phải đang trong transaction tường minh.

    Không tự ``commit``/``rollback``: để API quyết định, nhờ vậy lỗi ở bất kỳ
    bảng nào cũng rollback toàn bộ, kể cả ``audit_events`` đã bị xoá.
    """
    # So không phân biệt hoa/thường và bỏ khoảng trắng hai đầu: gõ "ok", "Ok",
    # " OK " đều được. Chuỗi đã ngắn thì bắt đúng kiểu chữ chỉ gây bực mình mà
    # không thêm an toàn nào — an toàn đến từ quyền ADMIN và bước đếm trước.
    if confirmation.strip().upper() != CONFIRMATION_PHRASE:
        raise PurgeError(
            f"Chuỗi xác nhận không đúng. Gõ chính xác: {CONFIRMATION_PHRASE}", 422
        )

    chosen = expand_scopes(scopes)
    tables = tables_for(chosen)

    if "CV" in chosen:
        _refuse_if_busy(db)

    # Thu thập đường dẫn Storage TRƯỚC vòng DELETE. Bắt buộc: application_documents
    # bị xoá ngay trong vòng lặp (và bị CASCADE từ applications), nên đọc sau sẽ
    # không còn dòng nào — file trên Storage thành mồ côi vĩnh viễn.
    originals: list[dict[str, Any]] = []
    extracted_paths: list[str] = []
    if "CV" in chosen:
        originals = [
            dict(r) for r in db.execute(text("""
                SELECT bucket, storage_path FROM app_private.application_documents
                WHERE bucket IS NOT NULL AND storage_path IS NOT NULL
            """)).mappings().all()
        ]
        # Tên cột thật là extracted_text_storage_path (không phải
        # storage_path hay extracted_text_path) — đã đối chiếu
        # information_schema, đừng đổi lại.
        extracted_paths = [
            str(r[0]) for r in db.execute(text("""
                SELECT extracted_text_storage_path
                  FROM app_private.document_processing_runs
                 WHERE extracted_text_storage_path IS NOT NULL
            """)).all()
            if r[0]
        ]

    # Snapshot trước khi xoá: số dòng sẽ mất, để ghi vào audit *sau* khi xoá.
    before: dict[str, int] = {}
    for table in tables:
        value = db.execute(text(f"SELECT count(*) FROM app_private.{table}")).scalar()
        before[table] = int(value or 0)

    # audit_events là append-only; phải tắt trigger trong chính transaction này.
    # Trigger ở đây là BEFORE DELETE trên bảng, nên chỉ cần tắt khi có xoá.
    audit_in_scope = "audit_events" in tables
    if audit_in_scope:
        db.execute(text(
            "ALTER TABLE app_private.audit_events DISABLE TRIGGER audit_events_append_only"
        ))

    # Bảng nào không tồn tại thì bỏ qua thay vì đổ vỡ cả thao tác: môi trường có
    # thể lệch migration. Nhưng phải báo lại để không im lặng.
    skipped: list[str] = []
    for table in tables:
        exists = db.execute(text("""
            SELECT 1 FROM information_schema.tables
            WHERE table_schema = 'app_private' AND table_name = :t
        """), {"t": table}).first()
        if not exists:
            skipped.append(table)
            continue
        db.execute(text(f"DELETE FROM app_private.{table}"))

    if audit_in_scope:
        db.execute(text(
            "ALTER TABLE app_private.audit_events ENABLE TRIGGER audit_events_append_only"
        ))
        state = db.execute(text("""
            SELECT tgenabled FROM pg_trigger
            WHERE tgname = 'audit_events_append_only'
              AND tgrelid = 'app_private.audit_events'::regclass
        """)).scalar()
        if state != "O":
            raise PurgeError(
                "Không bật lại được trigger bảo vệ audit — đã huỷ toàn bộ thao tác",
                500,
            )

    # Đánh số lại để dữ liệu mới không nhảy cóc.
    db.execute(text("UPDATE app_private.departments SET next_sequence = 1"))

    # Vì sao phải DROP DEFAULT rồi SET DEFAULT, không chỉ RESTART:
    #
    # Cột `chain_sequence` có DEFAULT nextval(...) VÀ trigger set_audit_event_hash()
    # cũng gọi nextval(...). Một lần INSERT tiêu HAI số của sequence.
    # RESTART WITH 1 + is_called=false khiến DEFAULT lấy 1, rồi trigger lấy 2 —
    # dòng đầu tiên của chuỗi mới mang chain_sequence=2 dù đáng lẽ là 1.
    # Đã kiểm chứng trên DB thật: RESTART một mình cho ra 2; DROP DEFAULT cho ra 1.
    #
    # Với DEFAULT đã bỏ, trigger là nguồn duy nhất cấp số, nên chuỗi mới bắt đầu
    # đúng ở 1 và liền mạch.
    db.execute(text("ALTER TABLE app_private.audit_events ALTER COLUMN chain_sequence DROP DEFAULT"))
    db.execute(text("ALTER SEQUENCE app_private.audit_event_chain_seq RESTART WITH 1"))

    # Ghi lại việc xoá. Đây là dòng audit ĐẦU TIÊN của chuỗi mới, nên
    # chain_sequence = 1 và previous_event_hash = NULL — chuỗi bắt đầu sạch.
    deleted_total = sum(before.values())
    db.execute(text("""
        INSERT INTO app_private.audit_events
            (actor_user_id, action_type, object_type, outcome, metadata)
        VALUES (:actor, 'TEST_DATA_PURGE', 'SYSTEM', 'SUCCESS', CAST(:metadata AS jsonb))
    """), {
        "actor": actor_user_id,
        "metadata": json.dumps({
            "requested_scopes": sorted(set(scopes)),
            "effective_scopes": sorted(chosen),
            "rows_deleted": before,
            "rows_total": deleted_total,
            "storage_targets": len(originals),
            "skipped_tables": skipped,
        }, ensure_ascii=False),
    })

    # KHÔNG xoá Storage ở đây. Hàm này chạy bên trong transaction của caller;
    # nếu xoá file trước khi commit rồi commit thất bại, file đã mất mà dòng DB
    # vẫn còn. API gọi purge_storage() *sau* khi commit thành công.
    return {
        "effective_scopes": sorted(chosen),
        "rows_deleted": {t: n for t, n in before.items() if n},
        "rows_total": deleted_total,
        "skipped_tables": skipped,
        "storage_originals": originals,
        "storage_extracted": extracted_paths,
    }


def delete_documents_from_storage(
    db, originals: list[dict[str, Any]], extracted_paths: list[str]
) -> tuple[dict[str, Any], str | None]:
    """Dọn Storage sau khi DB đã commit. Trả về (kết quả, lỗi).

    Hai bước, cố ý:

    1. Xoá theo đường dẫn đã thu thập — nhanh, đúng ngay cả khi Storage tạm
       không liệt kê được.
    2. **Đối soát toàn bucket**: liệt kê mọi file, xoá những file DB không còn
       trỏ tới. Đây là bước dọn được file mồ côi *cũ* (từ những lần xoá trước
       chưa có tính năng này), và tự lành mỗi khi DB/Storage lệch nhau.

    Lỗi được trả về thay vì ném ra: DB đã commit, nên lỗi Storage không được
    phép biến thao tác đã-thành-công thành thất bại. Nhưng cũng không im lặng.
    """
    direct: dict[str, Any] = {"skipped": True}
    direct_error: str | None = None
    if originals or extracted_paths:
        try:
            direct = delete_storage_objects(originals, extracted_paths)
        except Exception as exc:  # noqa: BLE001 - không lộ path/secret
            direct = {"skipped": False, "error": True}
            direct_error = str(getattr(exc, "detail", "Không xoá được file trên Storage"))

    from app.services.storage_purge import sweep_orphans

    sweep = sweep_orphans(db)

    combined = {**direct, "sweep": sweep}
    # Chỉ coi là lỗi khi CẢ HAI đường đều không dọn được.
    if direct_error and not sweep.get("swept"):
        return combined, direct_error
    if not direct_error and sweep.get("swept") is False and sweep.get("reason"):
        return combined, str(sweep["reason"])
    return combined, None


def collect_storage_targets(db, scopes: list[str]) -> tuple[list[dict[str, Any]], list[str]]:
    """Thu thập đường dẫn Storage khi chưa xoá gì. Dùng cho preview."""
    chosen = expand_scopes(scopes)
    if "CV" not in chosen:
        return [], []
    originals = [
        dict(r) for r in db.execute(text("""
            SELECT bucket, storage_path FROM app_private.application_documents
            WHERE bucket IS NOT NULL AND storage_path IS NOT NULL
        """)).mappings().all()
    ]
    extracted_paths = [
        str(r[0]) for r in db.execute(text("""
            SELECT extracted_text_storage_path FROM app_private.document_processing_runs
            WHERE extracted_text_storage_path IS NOT NULL
        """)).all() if r[0]
    ]
    return originals, extracted_paths


def _refuse_if_busy(db) -> None:
    """Không xoá khi worker đang xử lý: sẽ ghi vào bảng vừa bị xoá dòng."""
    busy = db.execute(text("""
        SELECT count(*) FROM app_private.operations
        WHERE status IN ('PENDING', 'PROCESSING')
    """)).scalar()
    if busy:
        raise PurgeError(
            f"Còn {busy} operation đang chạy — chờ xử lý xong rồi mới xoá", 409
        )
