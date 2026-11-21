"""Sinh nháp rubric từ JD dán tay, và một bộ tiêu chí hiệu lực mỗi vị trí.

Hai thay đổi đi cùng nhau vì cùng một lý do: HR cần dựng rubric mẫu *trước* khi
mở vị trí, và khi đã có rubric mẫu thì vị trí không được phép giữ hai bộ tiêu
chí cùng hiệu lực.

Test ở đây đọc mã nguồn thay vì dựng DB: mọi chốt chặn đều là truy vấn SQL, và
một thay đổi làm mất chốt sẽ không kéo theo test nào khác đỏ.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
RUBRICS = (BACKEND / "app" / "api" / "rubric_library.py").read_text()
CRITERIA = (BACKEND / "app" / "api" / "criteria.py").read_text()
MIGRATION = (BACKEND.parent / "supabase" / "migrations" / "00037_criteria_superseded_status.sql").read_text()

SHARED_START = RUBRICS.index("async def _draft_from_jd_text")
SHARED_END = RUBRICS.index("@router.post('/suggest-from-position')")
SHARED = RUBRICS[SHARED_START:SHARED_END]

JD_START = RUBRICS.index("async def suggest_from_jd_text")
JD_BODY = RUBRICS[JD_START:]


# ---------------------------------------------------------------------------
# Sinh nháp từ JD dán tay
# ---------------------------------------------------------------------------


def test_pasted_jd_endpoint_writes_nothing():
    """Dán JD để lấy nháp — không được tạo vị trí, không được tạo JD.

    Nếu endpoint này ghi ``jd_versions``, mỗi lần HR thử một JD sẽ để lại một
    dòng rác gắn với một vị trí không tồn tại. Nháp phải là nháp.
    """
    for keyword in ("INSERT INTO", "UPDATE app_private", "DELETE FROM"):
        assert keyword not in JD_BODY, f"suggest-from-jd không được chứa {keyword}"


def test_pasted_jd_requires_a_family():
    """Rubric không nhóm thì không tái sử dụng được, mất nghĩa của thư viện."""
    assert "job_families WHERE job_family_id=:id" in JD_BODY
    assert "404" in JD_BODY


def test_pasted_jd_does_not_reuse_a_real_position_code():
    """Mã yêu cầu giả phải trông là giả, không được bịa mã như vị trí thật."""
    assert "PASTED-JD" in JD_BODY


def test_both_suggestion_paths_share_one_implementation():
    """Hai đường sinh nháp phải dùng chung một chỗ kiểm output.

    Lý do: model trả về cùng những kiểu sai (nhãn tiếng Việt, trọng số dạng
    chuỗi) ở cả hai đường. Tách làm hai bản sao thì sửa một bên là bên kia
    lặng lẽ khác đi.
    """
    assert RUBRICS.count("async def _draft_from_jd_text") == 1
    position_body = RUBRICS[RUBRICS.index("async def suggest_from_position"):JD_START]
    assert "_draft_from_jd_text(" in position_body
    assert "_draft_from_jd_text(" in JD_BODY
    # Không được tự gọi model trực tiếp ở một trong hai đường.
    assert "extract_criteria_from_jd" not in position_body
    assert "extract_criteria_from_jd" not in JD_BODY


def test_shared_draft_keeps_per_item_rejection_without_losing_the_batch():
    """Một tiêu chí hỏng không được làm hỏng cả bộ — nhưng phải đếm để báo lại."""
    assert "rejected += 1" in SHARED
    assert "return normalize_weights_in_group(items), rejected" in SHARED


def test_shared_draft_rejects_an_empty_batch():
    """Toàn bộ tiêu chí hỏng thì phải 502, không được trả danh sách rỗng."""
    assert "if not items:" in SHARED
    assert "502" in SHARED


def test_weights_are_normalised_to_100_per_group():
    assert "normalize_weights_in_group(items)" in SHARED


# ---------------------------------------------------------------------------
# Một bộ tiêu chí hiệu lực mỗi vị trí
# ---------------------------------------------------------------------------


def test_approving_a_version_supersedes_the_previous_one():
    """Không hạ bộ cũ thì vị trí có hai bộ APPROVED cho cùng một JD."""
    approve = CRITERIA[CRITERIA.index("new_status, reviewer_role = criteria_decision"):]
    approve = approve[: approve.index("updated = dict(")]
    assert "SET status = 'SUPERSEDED'" in approve
    assert "AND status = 'APPROVED'" in approve
    assert "criteria_version_id <> :cv_id" in approve, "phải loại trừ chính bộ đang duyệt"


def test_supersede_is_audited_with_the_replacement():
    """Truy được: bộ cũ nào, ai thay, bằng bộ nào."""
    assert "SUPERSEDE_CRITERIA_VERSION" in CRITERIA
    for field in ("superseded_by", "superseded_by_version", "version_number"):
        assert f'"{field}"' in CRITERIA


def test_supersede_happens_before_the_new_status_is_written():
    """Thứ tự quan trọng: hạ bộ cũ TRƯỚC khi ghi APPROVED cho bộ mới.

    Ngược lại thì có một khoảnh khắc hai bộ cùng APPROVED, và một request đọc
    xen vào giữa sẽ chọn sai bộ.
    """
    approve = CRITERIA[CRITERIA.index("new_status, reviewer_role = criteria_decision"):]
    supersede_at = approve.index("SET status = 'SUPERSEDED'")
    write_at = approve.index("SET status = :new_status")
    assert supersede_at < write_at


def test_superseded_is_a_distinct_status_not_an_alias():
    """Bộ bị thay thế KHÔNG được gộp vào nhãn "bị loại".

    Nó vẫn là bằng chứng đã duyệt và đã chấm ứng viên cũ. Gộp vào ARCHIVED
    nghĩa là sau này không phân biệt được "bộ này bị bỏ vì sai" với "bộ này
    đúng nhưng đã có bộ mới hơn".

    REJECTED vẫn phải còn trong constraint — đó là trạng thái có thật khi
    người duyệt từ chối một bộ.
    """
    constraint = MIGRATION.split("CHECK (status IN (")[1].split(")")[0]
    assert "SUPERSEDED" in constraint
    assert "REJECTED" in constraint, "REJECTED là trạng thái thật, không được làm mất"
    assert "APPROVED" in constraint
    assert "ARCHIVED" not in constraint, "criteria_versions không dùng ARCHIVED — đừng thêm vào"


def test_migration_is_idempotent():
    """Chạy lại phải không hỏng: repo này áp migration tay trên DB thật."""
    assert "DROP CONSTRAINT IF EXISTS" in MIGRATION
    assert "ADD CONSTRAINT" in MIGRATION
    assert "CREATE INDEX IF NOT EXISTS" in MIGRATION


def test_migration_does_not_touch_data():
    """Chỉ nới ràng buộc, không được UPDATE dữ liệu đang có."""
    assert "UPDATE " not in MIGRATION
    assert "DELETE " not in MIGRATION
    assert "INSERT " not in MIGRATION


# ---------------------------------------------------------------------------
# Nháp rubric trong trình duyệt: chống mất dữ liệu, nhưng không giữ quá lâu
# ---------------------------------------------------------------------------

RUBRIC_PAGE = (BACKEND.parent / "frontend" / "src" / "app" / "rubrics" / "page.tsx").read_text()
DRAFTS = (BACKEND.parent / "frontend" / "src" / "lib" / "localDrafts.ts").read_text()


def test_leaving_the_page_with_unsaved_rubric_asks_first():
    """Sinh nháp bằng AI mất hàng chục giây; đóng tab ngang là mất trắng."""
    assert "useUnsavedChangesGuard(dirty" in RUBRIC_PAGE


def test_draft_survives_a_hard_close():
    """Hộp thoại beforeunload không phải lúc nào cũng hiện, nên phải có lưu tạm."""
    assert "writeDraft(rubricDraftKey()" in RUBRIC_PAGE
    assert "readDraft<any>(rubricDraftKey())" in RUBRIC_PAGE


def test_one_draft_key_not_one_per_version():
    """Một khoá duy nhất: HR chỉ soạn một bản tại một thời điểm.

    Tách khoá theo phiên bản thì có thể tồn tại hai nháp cùng lúc và lúc khôi
    phục phải đoán cái nào mới hơn — đoán sai là mất bản mới.
    """
    assert "rubric:pending" in DRAFTS
    assert "rubricDraftKey(" in DRAFTS.split("export function rubricDraftKey")[1].split("}")[0].split("\n")[0] \
        or "export function rubricDraftKey(): string" in DRAFTS, "khoá không được nhận tham số"


def test_restoring_a_saved_versions_draft_reloads_selected():
    """Thiếu bước này thì Lưu gọi update(selected!.template_version_id) trên null."""
    restore = RUBRIC_PAGE[RUBRIC_PAGE.index("readDraft<any>(rubricDraftKey())") - 200:]
    restore = restore[: restore.index("}, [loading]);")]
    assert "rubricApi.getVersion(stored.selected_id)" in restore
    assert "setSelected(" in restore


def test_lost_access_deletes_the_local_draft():
    """Nháp nằm trong localStorage không mã hoá — không được giữ khi mất quyền."""
    assert "[403, 404].includes" in RUBRIC_PAGE
    assert RUBRIC_PAGE.count("purgeRubricDrafts()") >= 2


def test_draft_is_purged_once_saved_to_the_server():
    """Nháp trong trình duyệt không còn là bản mới nhất sau khi lưu."""
    save_block = RUBRIC_PAGE[RUBRIC_PAGE.index("const save = async"):]
    save_block = save_block[: save_block.index("const act = async")]
    assert "purgeRubricDrafts()" in save_block


def test_draft_does_not_contain_the_raw_jd():
    """localStorage không mã hoá. Nháp chỉ chứa rubric HR đang viết, không chứa JD."""
    snapshot = RUBRIC_PAGE[RUBRIC_PAGE.index("const currentDraft = () => ({"):]
    snapshot = snapshot[: snapshot.index("});")]
    assert "jd_text" not in snapshot, "nháp không được chứa JD gốc"
    assert "jdText" not in snapshot, "nháp không được chứa JD gốc"
