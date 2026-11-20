"""Sinh NHÁP rubric mẫu từ JD của một vị trí.

Ba điều test này ghim, vì cả ba đều là chỗ dễ hỏng lặng lẽ:

1. Không lưu gì khi sinh — trả về nháp, người dùng phải bấm lưu.
2. Từ chối vị trí chưa có Nhóm vị trí, thay vì đoán một nhóm.
3. Cùng bộ chuẩn hoá với đường sinh tiêu chí cho vị trí: nhãn tiếng Việt
   ("Bắt buộc"), trọng số dạng "60%", và trọng số phải cộng đúng 100 mỗi nhóm.
"""
import uuid

import pytest

from app.services import rubric_normalizer as norm


def test_vietnamese_category_label_is_understood():
    """Model bản địa hoá theo ngôn ngữ JD — JD tiếng Việt hay sinh "Bắt buộc"."""
    assert norm.coerce_category('Bắt buộc') == 'MUST_HAVE'
    assert norm.coerce_category('Ưu tiên') == 'NICE_TO_HAVE'
    assert norm.coerce_category(' must-have ') == 'MUST_HAVE'
    assert norm.coerce_category('không rõ') is None


def test_weight_forms_the_model_actually_returns():
    assert norm.coerce_weight('60%') == 60.0
    assert norm.coerce_weight('0.6') == 0.6      # không được nhân 100
    assert norm.coerce_weight('60,5') == 60.5    # dấu phẩy thập phân
    assert norm.coerce_weight(True) is None      # bool không phải số
    assert norm.coerce_weight('abc') is None


def test_keywords_string_is_split_not_rejected():
    """Từ khoá chỉ là gợi ý bằng chứng — tách ra thay vì bỏ cả tiêu chí."""
    assert norm.coerce_keywords('Python, SQL') == ['Python', 'SQL']
    assert norm.coerce_keywords(['Python', ' SQL ']) == ['Python', 'SQL']


def test_weights_are_normalised_to_100_per_group():
    items = [
        {'name': 'a', 'category': 'MUST_HAVE', 'weight': 30},
        {'name': 'b', 'category': 'MUST_HAVE', 'weight': 30},
        {'name': 'c', 'category': 'NICE_TO_HAVE', 'weight': 10},
    ]
    out = norm.normalize_weights_in_group(items)
    assert sum(i['weight'] for i in out if i['category'] == 'MUST_HAVE') == pytest.approx(100)
    assert sum(i['weight'] for i in out if i['category'] == 'NICE_TO_HAVE') == pytest.approx(100)


def test_zero_weight_criterion_stays_zero():
    """Chia lại trọng số không được biến tiêu chí trọng số 0 thành có trọng số."""
    items = [
        {'name': 'a', 'category': 'MUST_HAVE', 'weight': 100},
        {'name': 'b', 'category': 'MUST_HAVE', 'weight': 0},
    ]
    out = norm.normalize_weights_in_group(items)
    assert out[1]['weight'] == 0


def test_position_without_family_is_rejected(monkeypatch):
    """Không đoán nhóm: rubric không nhóm thì không tái sử dụng được."""
    from fastapi import HTTPException
    from app.api import rubric_library

    class FakeDB:
        def execute(self, statement, params=None):
            sql = str(statement)
            if 'FROM app_private.positions p' in sql:
                return _Rows({'position_code': 'REQ-1', 'title': 'Backend', 'job_family_id': None, 'family_name': None})
            raise AssertionError(f'unexpected query: {sql[:60]}')
        def close(self): pass

    monkeypatch.setattr(rubric_library, 'SessionLocal', lambda: FakeDB())
    monkeypatch.setattr(rubric_library, '_require_directory', lambda *a, **k: ({'HR_RECRUITER'}, None))

    import asyncio
    # asyncio.run chứ không phải get_event_loop(): test khác trong bộ có thể đã
    # đóng loop mặc định, và get_event_loop() khi đó ném RuntimeError.
    with pytest.raises(HTTPException) as exc:
        asyncio.run(rubric_library.suggest_from_position(
            rubric_library.SuggestFromPosition(position_id=uuid.uuid4()), {'user_id': 'u1'}))
    assert exc.value.status_code == 400
    assert 'Nhóm vị trí' in exc.value.detail


class _Rows:
    def __init__(self, row): self._row = row
    def mappings(self): return self
    def first(self): return self._row


def test_suggestion_is_returned_as_draft_and_never_saved(monkeypatch):
    """Hàm này KHÔNG được INSERT gì — chỉ trả nháp về cho giao diện."""
    from app.api import rubric_library as rl

    statements = []

    class FakeDB:
        def execute(self, statement, params=None):
            sql = str(statement)
            statements.append(sql)
            if 'FROM app_private.positions p' in sql:
                return _Rows({'position_code': 'REQ-1', 'title': 'Backend Python',
                              'job_family_id': 'fam-1', 'family_name': 'IT & Digital'})
            if 'FROM app_private.jd_versions' in sql:
                return _Rows({'content_text': 'Kỹ sư Backend Python. Yêu cầu 4 năm kinh nghiệm.'})
            raise AssertionError(f'unexpected query: {sql[:60]}')
        def close(self): pass

    async def fake_extract(**kwargs):
        return {'criteria': [
            {'name': 'Kinh nghiệm Python', 'description': 'Tối thiểu 4 năm', 'category': 'Bắt buộc',
             'weight': '60%', 'expected_evidence_keywords': 'Python, Django'},
            {'name': 'Kubernetes', 'description': 'Có thì tốt', 'category': 'Ưu tiên', 'weight': 100,
             'expected_evidence_keywords': ['Kubernetes']},
            {'name': '', 'description': 'x', 'category': 'MUST_HAVE', 'weight': 1},   # bị loại
        ]}

    monkeypatch.setattr(rl, 'SessionLocal', lambda: FakeDB())
    monkeypatch.setattr(rl, '_require_directory', lambda *a, **k: ({'HR_RECRUITER'}, None))
    from app.services import llm_client as llm
    monkeypatch.setattr(llm.llm_client, 'extract_criteria_from_jd', fake_extract)

    import asyncio
    result = asyncio.run(
        rl.suggest_from_position(rl.SuggestFromPosition(position_id=uuid.uuid4()), {'user_id': 'u1'}))

    assert result['job_family_id'] == 'fam-1'
    assert len(result['items']) == 2
    assert result['rejected_items'] == 1
    assert result['items'][0]['category'] == 'MUST_HAVE'       # "Bắt buộc" đã chuẩn hoá
    assert result['items'][0]['expected_evidence_keywords'] == ['Python', 'Django']
    assert result['items'][1]['category'] == 'NICE_TO_HAVE'
    assert 'chưa lưu' in result['note']
    assert not any(s.strip().upper().startswith(('INSERT', 'UPDATE', 'DELETE')) for s in statements), \
        'sinh nháp không được ghi gì vào database'
