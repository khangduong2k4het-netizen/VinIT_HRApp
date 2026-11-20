"""Chuẩn hoá dữ liệu tiêu chí do LLM trả về.

Tách ra khỏi ``app/api/criteria.py`` để dùng chung cho hai đường:

* sinh bộ tiêu chí cho **một vị trí** (``criteria.py``), sinh ra
  ``criteria_items`` để chấm điểm ứng viên;
* sinh **rubric mẫu** cho thư viện (``rubric_library.py``), để HR duyệt rồi
  tái sử dụng cho nhiều vị trí cùng nhóm.

Hai đường khác nhau về đích đến nhưng phải chịu cùng một mức kiểm tra, vì cùng
một model trả lời và cùng những kiểu sai: nhãn nhóm bản địa hoá ("BẮT BUỘC"),
trọng số dạng `"60%"`, từ khoá dạng chuỗi thay vì mảng, trọng số cộng không
bằng 100. Viết hai bản sao là chắc chắn có ngày lệch nhau.

Không hàm nào ở đây gọi mạng hay DB — vào là dict thô, ra là dict đã kiểm.
"""
from __future__ import annotations

import re
from decimal import Decimal, ROUND_HALF_UP
from typing import Optional

from app.services.deterministic_matching import deterministic_matcher

#: Nhãn nhóm mà model có thể trả về thay vì mã chuẩn. Model bản địa hoá theo
#: ngôn ngữ JD (JD tiếng Việt hay sinh "BẮT BUỘC"), hoặc viết hoa/thường khác.
_CATEGORY_ALIASES = {
    "must_have": "MUST_HAVE", "must have": "MUST_HAVE", "musthave": "MUST_HAVE",
    "mandatory": "MUST_HAVE", "required": "MUST_HAVE",
    "bắt buộc": "MUST_HAVE", "bat buoc": "MUST_HAVE", "yêu cầu bắt buộc": "MUST_HAVE",
    "nice_to_have": "NICE_TO_HAVE", "nice to have": "NICE_TO_HAVE", "nicetohave": "NICE_TO_HAVE",
    "preferred": "NICE_TO_HAVE", "optional": "NICE_TO_HAVE",
    "ưu tiên": "NICE_TO_HAVE", "uu tien": "NICE_TO_HAVE", "mong muốn": "NICE_TO_HAVE",
}


def stored_requirement_spec(item: dict) -> dict:
    """Materialize the engine's inferred draft in the stored JSONB shape."""
    spec = deterministic_matcher.build_requirement_spec(item)
    return {
        "kind": spec.kind,
        "terms": [term.label for term in spec.terms],
        "min_years": spec.min_years,
        "required_degree_level": spec.required_degree_level,
        "required_languages": list(spec.required_languages),
        "required_ielts": spec.required_ielts,
        "required_toeic": spec.required_toeic,
        "required_cefr": spec.required_cefr,
        "required_language_rank": spec.required_language_rank,
    }


def coerce_text(value) -> str:
    """Ép một trường văn bản về ``str`` đã cắt khoảng trắng, chịu được None."""
    if value is None:
        return ""
    return str(value).strip()


def coerce_category(value) -> Optional[str]:
    """Chuẩn hoá nhãn nhóm; trả ``None`` nếu không nhận ra.

    Khoá tra cứu bỏ khoảng trắng thừa và không phân biệt hoa thường, để
    " MUST_HAVE", "must-have" và "Bắt buộc" đều về đúng nhóm.
    """
    if not isinstance(value, str):
        return None
    key = re.sub(r"[\s\-_]+", " ", value.strip()).lower()
    if key.replace(" ", "_") in ("must_have", "nice_to_have"):
        return key.replace(" ", "_").upper()
    return _CATEGORY_ALIASES.get(key)


def coerce_weight(value) -> Optional[float]:
    """Ép trọng số về ``float``, hiểu được các kiểu model hay trả.

    Chấp nhận ``60``, ``"60"``, ``"60%"``, ``"0.6"``.  Trả ``None`` khi không
    đọc được, để nơi gọi quyết định từ chối.
    """
    if isinstance(value, bool) or value is None:
        return None
    if isinstance(value, (int, float)):
        return float(value)
    if isinstance(value, str):
        cleaned = value.strip().replace(",", ".")
        # "60%" -> 60; nhưng "0.6" phải giữ là 0.6 chứ không nhân 100.
        if cleaned.endswith("%"):
            cleaned = cleaned[:-1].strip()
        try:
            return float(cleaned)
        except ValueError:
            return None
    return None


def coerce_keywords(value) -> list[str]:
    """Chuẩn hoá danh sách từ khoá về ``list[str]``.

    Model đôi khi trả một chuỗi ``"Python, SQL"`` thay vì mảng. Tách theo dấu
    phẩy thay vì từ chối, vì từ khoá chỉ là gợi ý bằng chứng, không phải điểm.
    """
    if isinstance(value, str):
        return [part.strip() for part in value.split(",") if part.strip()]
    if isinstance(value, list):
        return [str(part).strip() for part in value if str(part).strip()]
    return []


def normalize_weights_in_group(items: list[dict]) -> list[dict]:
    """Scale AI/manual draft weights so every present category sums to 100.

    LLM output has historically mixed two meanings: share of the whole rubric
    and share inside a category. The database field is explicitly the latter,
    so generation normalizes it before storage. A zero criterion stays zero;
    the rounding remainder is assigned to the largest criterion in its group.
    """
    normalized = [dict(item) for item in items]
    categories = {str(item.get("category")) for item in normalized}
    for category in categories:
        group = [item for item in normalized if str(item.get("category")) == category]
        total = sum(
            Decimal(str(item.get("weight") if "weight" in item else item.get("weight_in_group") or 0))
            for item in group
        )
        if total <= 0:
            continue
        scaled: list[Decimal] = []
        for item in group:
            raw = Decimal(str(item.get("weight") if "weight" in item else item.get("weight_in_group") or 0))
            value = (raw * Decimal("100") / total).quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
            item["weight"] = float(value)
            if "weight_in_group" in item:
                item["weight_in_group"] = float(value)
            scaled.append(value)
        remainder = Decimal("100.00") - sum(scaled)
        if remainder != 0:
            # Cộng phần lẻ làm tròn vào tiêu chí lớn nhất để tổng vẫn đúng 100.
            biggest = max(group, key=lambda item: Decimal(str(item.get("weight") or 0)))
            adjusted = Decimal(str(biggest.get("weight"))) + remainder
            biggest["weight"] = float(adjusted)
            if "weight_in_group" in biggest:
                biggest["weight_in_group"] = float(adjusted)
    return normalized
