"""Huỷ bản nháp tiêu chí để mở đường cho rubric mẫu.

Vì sao có endpoint này: tạo vị trí luôn sinh một bộ tiêu chí AI ở trạng thái
``DRAFT``, và ``rubric_library.apply_template`` từ chối (409) khi vị trí còn bộ
tiêu chí chưa xong. Không có lối huỷ thì HR muốn dùng rubric mẫu buộc phải đưa
bộ AI qua **cả** vòng duyệt HR → Hiring Manager chỉ để mở một cái nút, rồi bộ
AI đó nằm lại vĩnh viễn ở trạng thái ``APPROVED``.

Test ở đây ghim đúng những chốt chặn đã đặt trong ``discard_draft_criteria``,
bằng cách đọc mã nguồn thay vì dựng DB: các điều kiện đều là truy vấn SQL và
một thay đổi làm mất chốt sẽ không kéo theo test nào khác đỏ.

Bài học đã trả giá một lần trong repo này: test đọc mã nguồn phải khẳng định
đúng **thứ tự** thực thi, nếu không thì chỉ cần một dòng comment chứa cùng từ
khoá là test xanh trong khi logic đã đảo.
"""
import re
from pathlib import Path

SOURCE = (Path(__file__).resolve().parents[1] / "app" / "api" / "criteria.py").read_text()
START = SOURCE.index("async def discard_draft_criteria")
END = SOURCE.index('@router.get("/position/{position_id}/approved"')
BODY = SOURCE[START:END]


def test_only_draft_can_be_discarded():
    """PENDING_HR_REVIEW trở đi là đã có người khác xem và có ý kiến."""
    assert 'version["status"] != "DRAFT"' in BODY
    assert "409" in BODY


def test_requires_hr_scope_of_the_position():
    """Cùng lớp quyền với sửa tiêu chí: HR phụ trách vị trí, không phải ai cũng được."""
    assert "can_update_application_status(current_user[" in BODY
    assert "403" in BODY


def test_refuses_when_the_versions_was_already_scored():
    """FK từ assessment_runs không CASCADE: kiểm trước để trả lời giải thích được."""
    assert "assessment_runs" in BODY
    assert "criteria_version_id = :id" in BODY


def test_audit_is_written_before_the_delete():
    """Sau khi xoá thì không còn gì để truy lại số tiêu chí đã mất."""
    audit_at = BODY.index("DISCARD_CRITERIA_DRAFT")
    delete_at = BODY.index("DELETE FROM app_private.criteria_versions")
    assert audit_at < delete_at, "audit phải ghi TRƯỚC lệnh xoá"


def test_audit_keeps_what_would_otherwise_be_lost():
    for field in ("version_number", "origin", "item_count", "jd_version_id"):
        assert f'"{field}"' in BODY, f"audit thiếu {field} — không truy lại được sau khi xoá"


def test_no_hard_delete_of_other_positions_versions():
    """Xoá phải nhắm đúng một criteria_version_id, không quét theo vị trí."""
    delete_clause = BODY[BODY.index("DELETE FROM app_private.criteria_versions"):]
    delete_clause = delete_clause[: delete_clause.index(")")]
    assert "criteria_version_id = :id" in delete_clause
    assert "position_id" not in delete_clause


def test_role_check_happens_before_status_check():
    """Người không có quyền phải nhận 403, không phải 409 nói về trạng thái.

    409 trước 403 sẽ tiết lộ trạng thái tiêu chí của vị trí cho người không có
    quyền xem — không nguy hiểm lớn, nhưng là thứ tự sai.
    """
    role_at = BODY.index("can_update_application_status")
    status_at = BODY.index('version["status"] != "DRAFT"')
    assert role_at < status_at


# ---------------------------------------------------------------------------
# Cùng chủ đề, phía frontend: tải thư viện rubric mẫu ở trang tạo vị trí
# ---------------------------------------------------------------------------

NEW_PAGE = (Path(__file__).resolve().parents[2] / "frontend" / "src" / "app" / "positions" / "new" / "page.tsx").read_text()


def test_empty_rubric_library_does_not_retrigger_the_fetch():
    """Thư viện RỖNG là câu trả lời hợp lệ, không phải trạng thái "chưa tải".

    Dùng `templateVersions.length === 0` làm điều kiện dừng thì mỗi lần state
    đổi effect lại chạy và gọi API mãi mãi — kể cả khi máy chủ nói rõ là không
    có rubric nào. Điều kiện dừng phải là một cờ "đã hỏi rồi".
    """
    block = NEW_PAGE[NEW_PAGE.index("useEffect("):]
    block = block[: block.index("}, [criteriaSource]);")]
    assert "templatesLoaded.current" in block, "phải có cờ đã-hỏi, không dựa vào độ dài mảng"
    assert "templateVersions.length" not in block.split("setTemplatesLoading(true)")[0].split("return;")[0], \
        "điều kiện dừng không được dựa vào độ dài mảng (vòng lặp vô hạn khi thư viện rỗng)"


def test_template_branch_never_calls_ai_generation():
    """Chọn rubric mẫu thì không được sinh AI trước — bộ DRAFT sẽ chặn apply 409."""
    submit = NEW_PAGE[NEW_PAGE.index("const submit = async"):]
    submit = submit[: submit.index("const leave = ")]
    branch = submit[submit.index("if (criteriaSource === 'template' && templateId)"):]
    branch = branch[: branch.index("\n")]
    assert "runTemplateApply" in branch
    assert "runCriteriaGeneration" not in branch


def test_submit_is_blocked_until_a_template_is_chosen():
    """Bấm Tạo khi đã chọn rubric mẫu mà chưa chọn rubric thì phải bị chặn."""
    assert "(criteriaSource === 'template' && !templateId)" in NEW_PAGE
