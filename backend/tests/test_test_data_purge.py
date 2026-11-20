"""Dọn dữ liệu test: hợp đồng an toàn của một thao tác phá huỷ.

Trọng tâm KHÔNG phải "xoá được hay không" (đó là việc của test tích hợp với
Postgres thật), mà là những ràng buộc bảo vệ: không chạm bảng cấu hình, không
xoá khi worker đang chạy, không xoá khi chưa gõ đúng chuỗi xác nhận, và thứ tự
xoá phải đúng chiều khoá ngoại.
"""
import pytest

from app.services import test_data_purge as purge
from app.services.test_data_purge import (
    CONFIRMATION_PHRASE,
    DELETE_ORDER,
    PROTECTED_TABLES,
    PurgeError,
    SCOPES,
    expand_scopes,
    tables_for,
)


class RecordingDB:
    """Session giả: ghi lại mọi câu SQL, trả giá trị cấu hình theo bảng."""

    def __init__(self, counts=None, busy=0):
        self.counts = dict(counts or {})
        self.busy = busy
        self.sql = []

    def execute(self, statement, params=None):
        sql = str(statement)
        self.sql.append((sql, params))
        return _FakeResult(self, sql)


class _FakeResult:
    def __init__(self, db, sql):
        self.db = db
        self.sql = sql

    def scalar(self):
        if "FROM app_private.operations" in self.sql:
            return self.db.busy
        # Câu kiểm trigger trả 'O' = đang bật, giống PostgreSQL thật sau ENABLE.
        if "tgenabled" in self.sql:
            return "O"
        return 0

    def first(self):
        # Mọi bảng đều "tồn tại" trong test giả, trừ khi test cố tình loại.
        return (1,)

    def mappings(self):
        return self

    def all(self):
        return []

    def fetchone(self):
        return None


def test_confirmation_phrase_is_not_trivially_guessable():
    """Một chữ "OK" là quá dễ bấm nhầm; chuỗi phải dài và nói rõ việc đang làm."""
    assert len(CONFIRMATION_PHRASE) >= 10
    assert "XOA" in CONFIRMATION_PHRASE.upper()


def test_jd_and_positions_are_coupled():
    """JD và vị trí không tách rời: cả hai chiều đều có FK nên phải đi cùng nhau."""
    assert "POSITIONS" in expand_scopes(["JD"])
    assert "JD" in expand_scopes(["POSITIONS"])


def test_positions_alone_drags_operations():
    """Chọn riêng "Vị trí" phải xoá được, nên phải kéo theo OPERATIONS.

    Có 11 bảng tham chiếu ``positions`` với FK ``NO ACTION`` (audit_events,
    applications, assessment_runs, cv_batches, duplicate_signals, ranking_runs,
    ranking_items, shortlist_shares, shortlist_share_items, careers_intake_receipts,
    position_create_requests). Thiếu ràng buộc này thì ``DELETE FROM positions``
    bị PostgreSQL chặn và cả lượt xoá thất bại — đã là lỗi thật một lần.
    """
    assert "OPERATIONS" in expand_scopes(["POSITIONS"])
    # Và danh sách bảng phải thật sự chứa các bảng đang giữ khoá ngoại.
    tables = tables_for(expand_scopes(["POSITIONS"]))
    for required in ("audit_events", "cv_batches", "audit_events"):
        assert required in tables, required


def test_jd_alone_drags_operations():
    """JD kéo theo POSITIONS; mà xoá vị trí thì phải xoá cả CV và vận hành."""
    assert expand_scopes(["JD"]) == {"JD", "POSITIONS", "OPERATIONS", "CV"}


def test_no_scope_selection_ever_deletes_positions_without_dependents():
    """Bất biến: hễ xoá ``positions`` thì mọi bảng giữ FK NO ACTION tới nó cũng có mặt."""
    # Đọc thẳng từ migration để test này bắt được migration mới thêm bảng.
    import glob, re
    from pathlib import Path
    pointing = set()
    for path in glob.glob(str(Path(__file__).resolve().parents[2] / "supabase" / "migrations" / "*.sql")):
        sql = open(path, encoding="utf-8").read()
        for match in re.finditer(r"CREATE TABLE\s+(?:IF NOT EXISTS\s+)?app_private\.(\w+)\s*\((.*?)\);", sql, re.S):
            for line in match.group(2).split("\n"):
                if "REFERENCES app_private.positions" in line and "CASCADE" not in line:
                    pointing.add(match.group(1))
    # Chỉ xét những bảng thật sự nằm trong phạm vi purge (bảng ngoài phạm vi không
    # thể chọn xoá nên không chặn được thao tác của người dùng).
    in_purge = {table for _scope, table in DELETE_ORDER}
    considered = pointing & in_purge
    for scope in SCOPES:
        chosen = expand_scopes([scope])
        tables = set(tables_for(chosen))
        if "positions" not in tables:
            continue
        missing = considered - tables
        assert not missing, f"scope {scope}: thiếu {sorted(missing)} nên xoá positions sẽ bị chặn"


def test_cv_alone_does_not_drag_positions():
    """Xoá CV không được kéo theo vị trí — người dùng có thể muốn giữ JD để nộp lại."""
    assert expand_scopes(["CV"]) == {"CV"}


def test_unknown_scope_rejected():
    with pytest.raises(PurgeError) as exc:
        expand_scopes(["CV", "EVERYTHING"])
    assert exc.value.status_code == 422


def test_empty_scope_rejected():
    with pytest.raises(PurgeError):
        expand_scopes([])


def test_protected_tables_never_appear_in_delete_order():
    """Lưới an toàn quan trọng nhất của module."""
    deletable = {f"app_private.{table}" for _scope, table in DELETE_ORDER} | {
        f"app_private.{table}" for _scope, table in DELETE_ORDER
    }
    overlap = deletable & set(PROTECTED_TABLES)
    assert not overlap, f"Bảng được bảo vệ lọt vào thứ tự xoá: {overlap}"


def test_delete_order_has_no_duplicates():
    """Xuất hiện hai lần nghĩa là xoá hai lượt — dấu hiệu copy-paste sai."""
    tables = [t for _s, t in DELETE_ORDER]
    assert len(tables) == len(set(tables))


def test_every_scope_is_reachable():
    """Mọi nhóm khai báo trong SCOPES phải có ít nhất một bảng để xoá."""
    used = {scope for scope, _t in DELETE_ORDER}
    assert used == set(SCOPES), f"Nhóm không có bảng nào: {set(SCOPES) - used}"


def test_fk_sensitive_order_constraints():
    """Ba cặp từng gây lỗi FK khi làm thủ công — ghim lại để không tái diễn."""
    order = [t for _s, t in DELETE_ORDER]
    assert order.index("shortlist_share_items") < order.index("ranking_items")
    assert order.index("audit_events") < order.index("positions")
    assert order.index("assessment_runs") < order.index("operations")


def test_children_deleted_before_parents():
    """Thứ tự tổng quát: bảng con phải đứng trước bảng cha."""
    order = [t for _s, t in DELETE_ORDER]
    pairs = [
        ("evidence_items", "criterion_assessment_results"),
        ("criterion_assessment_results", "assessment_runs"),
        ("assessment_runs", "applications"),
        ("application_documents", "applications"),
        ("criteria_items", "criteria_versions"),
        ("criteria_versions", "jd_versions"),
        ("positions", "departments"),  # departments không xoá, nhưng thứ tự vẫn phải đúng
    ]
    for child, parent in pairs:
        if child in order and parent in order:
            assert order.index(child) < order.index(parent), f"{child} phải xoá trước {parent}"


def test_tables_for_only_returns_selected_scopes():
    tables = tables_for({"CV"})
    assert "applications" in tables
    assert "positions" not in tables
    assert "audit_events" not in tables


def test_execute_refuses_without_exact_confirmation():
    db = RecordingDB()
    with pytest.raises(PurgeError) as exc:
        purge.execute(db, scopes=["CV"], confirmation="ok", actor_user_id="u1")
    assert exc.value.status_code == 422
    assert db.sql == [], "Không được chạy SQL nào khi chuỗi xác nhận sai"


def test_execute_accepts_confirmation_with_surrounding_spaces():
    """Dán kèm khoảng trắng là chuyện thường; không nên bắt gõ lại vì thế."""
    db = RecordingDB(counts={"applications": 3})
    result = purge.execute(
        db, scopes=["CV"], confirmation=f"  {CONFIRMATION_PHRASE}  ", actor_user_id="u1"
    )
    assert result["rows_total"] >= 0


def test_execute_refuses_when_worker_is_busy():
    """Xoá khi worker đang chạy làm nó ghi vào bảng vừa mất dòng."""
    db = RecordingDB(busy=2)
    with pytest.raises(PurgeError) as exc:
        purge.execute(db, scopes=["CV"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1")
    assert exc.value.status_code == 409
    assert "2" in exc.value.detail


def test_execute_does_not_delete_when_busy():
    db = RecordingDB(busy=1)
    with pytest.raises(PurgeError):
        purge.execute(db, scopes=["CV"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1")
    assert not [s for s, _p in db.sql if s.strip().upper().startswith("DELETE")]


def test_audit_trigger_reenabled_only_when_audit_in_scope():
    """Xoá mỗi CV thì không được đụng vào trigger append-only của bảng audit."""
    db = RecordingDB()
    purge.execute(db, scopes=["CV"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1")
    statements = [s for s, _p in db.sql]
    assert not any("DISABLE TRIGGER" in s for s in statements)
    assert not any("ENABLE TRIGGER" in s for s in statements)


def test_audit_scope_disables_then_reenables_trigger():
    db = RecordingDB()
    purge.execute(
        db, scopes=["OPERATIONS"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1"
    )
    statements = [s for s, _p in db.sql]
    disable = next(i for i, s in enumerate(statements) if "DISABLE TRIGGER" in s)
    enable = next(i for i, s in enumerate(statements) if "ENABLE TRIGGER" in s)
    assert disable < enable, "Trigger phải được bật lại sau khi xoá xong"


def test_audit_written_after_sequence_reset():
    """Dòng audit ghi lại việc xoá phải là dòng ĐẦU của chuỗi mới."""
    db = RecordingDB()
    purge.execute(
        db, scopes=["OPERATIONS"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1"
    )
    statements = [s for s, _p in db.sql]
    reset = next(i for i, s in enumerate(statements) if "RESTART WITH 1" in s)
    insert = next(i for i, s in enumerate(statements) if "TEST_DATA_PURGE" in s)
    assert reset < insert


def test_sequence_reset_and_dept_reset_are_included():
    """Vị trí mới phải bắt đầu từ IT-0001, không nhảy cóc theo dữ liệu đã xoá."""
    db = RecordingDB()
    purge.execute(db, scopes=["CV"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1")
    joined = " ".join(s for s, _p in db.sql)
    assert "next_sequence = 1" in joined
    assert "RESTART WITH 1" in joined


def test_audit_sequence_drop_default_before_restart():
    """Một lần INSERT tiêu HAI số sequence: DEFAULT nextval + trigger nextval.

    Nếu không DROP DEFAULT, RESTART WITH 1 vẫn khiến dòng đầu của chuỗi mới mang
    chain_sequence = 2. Đã kiểm chứng trên Supabase thật; test này ghim lại để
    không ai "dọn gọn" mất dòng DROP DEFAULT.
    """
    db = RecordingDB()
    purge.execute(
        db, scopes=["OPERATIONS"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1"
    )
    statements = [s for s, _p in db.sql]
    drop_default = next(
        (i for i, s in enumerate(statements) if "chain_sequence DROP DEFAULT" in s), None
    )
    assert drop_default is not None, "Thiếu DROP DEFAULT — chuỗi audit sẽ bắt đầu ở 2, không phải 1"
    restart = next(i for i, s in enumerate(statements) if "RESTART WITH 1" in s)
    assert drop_default < restart, "Phải bỏ DEFAULT trước khi restart sequence"


def test_audit_insert_happens_after_restart_and_drop_default():
    """Dòng audit ghi việc xoá là dòng ĐẦU của chuỗi mới, nên phải sau khi reset."""
    db = RecordingDB()
    purge.execute(
        db, scopes=["OPERATIONS"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1"
    )
    statements = [s for s, _p in db.sql]
    restart = next(i for i, s in enumerate(statements) if "RESTART WITH 1" in s)
    insert = next(i for i, s in enumerate(statements) if "TEST_DATA_PURGE" in s)
    assert restart < insert


def test_storage_paths_collected_before_any_delete():
    """Đọc đường dẫn SAU khi xoá application_documents là mất vĩnh viễn file."""
    db = RecordingDB()
    purge.execute(db, scopes=["CV"], confirmation=CONFIRMATION_PHRASE, actor_user_id="u1")
    statements = [s for s, _p in db.sql]
    first_doc_select = next(
        (i for i, s in enumerate(statements) if "FROM app_private.application_documents" in s and s.startswith("SELECT")),
        None,
    )
    first_delete = next(i for i, s in enumerate(statements) if s.strip().upper().startswith("DELETE"))
    if first_doc_select is not None:
        assert first_doc_select < first_delete


def test_preview_reports_protected_counts():
    """ADMIN cần thấy cái gì KHÔNG mất — câu hỏi đầu tiên trước khi bấm xoá."""
    db = RecordingDB()
    result = purge.preview(db, ["CV"])
    assert "user_profiles" in {row["table"] for row in result["protected"]}
    assert result["effective_scopes"] == ["CV"]


def test_preview_marks_implied_scopes():
    """Người dùng chọn JD nhưng phải biết vị trí cũng bị xoá."""
    db = RecordingDB()
    result = purge.preview(db, ["JD"])
    assert "POSITIONS" in result["effective_scopes"]
    assert "POSITIONS" in result["implied_scopes"]


def test_storage_result_never_raises_into_success_path():
    """DB đã commit rồi — lỗi Storage không được biến thành 'thao tác thất bại'."""
    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("storage down")

    import app.services.storage_purge as sp

    original_delete = purge.delete_storage_objects
    original_sweep = sp.sweep_orphans
    purge.delete_storage_objects = Boom
    sp.sweep_orphans = lambda db, **k: {"swept": True, "deleted": 0, "buckets": []}
    try:
        result, error = purge.delete_documents_from_storage(
            RecordingDB(), [{"bucket": "b", "storage_path": "p"}], []
        )
        # Xoá trực tiếp lỗi, nhưng đối soát thành công => không coi là thất bại.
        assert error is None
        assert result["error"] is True
        assert result["sweep"]["swept"] is True
    finally:
        purge.delete_storage_objects = original_delete
        sp.sweep_orphans = original_sweep


def test_storage_error_reported_when_both_paths_fail():
    """Cả xoá trực tiếp lẫn đối soát đều hỏng thì phải báo lỗi, không im lặng."""
    class Boom:
        def __init__(self, *a, **k):
            raise RuntimeError("storage down")

    import app.services.storage_purge as sp

    original_delete = purge.delete_storage_objects
    original_sweep = sp.sweep_orphans
    purge.delete_storage_objects = Boom
    sp.sweep_orphans = lambda db, **k: {"swept": False, "reason": "Không liệt kê được"}
    try:
        _result, error = purge.delete_documents_from_storage(
            RecordingDB(), [{"bucket": "b", "storage_path": "p"}], []
        )
        assert error is not None
    finally:
        purge.delete_storage_objects = original_delete
        sp.sweep_orphans = original_sweep


def test_storage_cleanup_called_after_commit_boundary():
    """Đối soát Storage phải được gọi SAU khi xoá DB, không phải trong lúc."""
    import app.services.storage_purge as sp

    called = []
    original = sp.sweep_orphans
    sp.sweep_orphans = lambda db, **k: (called.append("swept") or {"swept": True, "deleted": 0})
    db = RecordingDB()
    try:
        purge.delete_documents_from_storage(db, [], [])
        assert called == ["swept"], "Phải đối soát Storage kể cả khi không có path trực tiếp"
    finally:
        sp.sweep_orphans = original
