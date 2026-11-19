"""Flag rubric criteria that rely on non-job-related personal attributes.

F1.02 forbids criteria based on age, gender, appearance, marital status,
personality or "culture fit". AI drafts are asked not to produce them, but HR
edits and model mistakes still need a deterministic guard before approval.

This is a keyword screen, not a classifier: it errs towards flagging so a human
reviews the wording. Terms that commonly appear in legitimate technical JDs
("race condition", "single sign-on", "weight" of a criterion, "Việt Nam") are
deliberately not matched.
"""
from __future__ import annotations

import re
import unicodedata
from typing import Any, Iterable

# (attribute code, English patterns matched on word boundaries)
_ENGLISH_PATTERNS: list[tuple[str, str]] = [
    ("AGE", r"\bage[sd]?\b|\byears? old\b|\byoung\b|\bdate of birth\b|\bbirth ?year\b"),
    ("GENDER", r"\bgender\b|\bmale\b|\bfemale\b|\bsex\b|\bwoman\b|\bwomen\b|\bpregnan\w*"),
    ("APPEARANCE", r"\bappearance\b|\bgood[- ]looking\b|\battractive\b|\bphoto\b|\bheight\b|\bbody weight\b|\bbeauty\b|\bpresentable\b"),
    ("MARITAL_STATUS", r"\bmarital\b|\bmarried\b|\bunmarried\b|\bspouse\b|\bchildren\b|\bfamily status\b"),
    ("PERSONALITY", r"\bpersonality\b|\bintrovert\w*|\bextrovert\w*|\btemperament\b"),
    ("CULTURE_FIT", r"\bcultur(?:e|al)[- ]fit\b|\bfits? (?:our|the) culture\b"),
    ("NATIONALITY_ETHNICITY", r"\bnationality\b|\bethnic\w*|\bracial\b|\bnative[- ]born\b"),
    ("RELIGION", r"\breligio\w*"),
]

# Vietnamese phrases are matched on the accent-preserving lowercase text.
_VIETNAMESE_PHRASES: list[tuple[str, tuple[str, ...]]] = [
    ("AGE", ("độ tuổi", "tuổi", "năm sinh", "ngày sinh")),
    ("GENDER", ("giới tính", "nam giới", "nữ giới", "phụ nữ", "đàn ông", "mang thai", "có thai")),
    ("APPEARANCE", ("ngoại hình", "chiều cao", "cân nặng", "ưa nhìn", "xinh", "đẹp trai", "ảnh chân dung")),
    ("MARITAL_STATUS", ("hôn nhân", "kết hôn", "độc thân", "đã có gia đình", "con nhỏ")),
    ("PERSONALITY", ("tính cách", "cá tính", "hướng nội", "hướng ngoại")),
    ("CULTURE_FIT", ("phù hợp văn hóa", "phù hợp với văn hóa", "hợp văn hóa")),
    ("NATIONALITY_ETHNICITY", ("quốc tịch", "dân tộc", "chủng tộc", "quê quán")),
    ("RELIGION", ("tôn giáo", "tín ngưỡng")),
]

_COMPILED = [(code, re.compile(pattern, re.IGNORECASE)) for code, pattern in _ENGLISH_PATTERNS]


def _normalise(value: str) -> str:
    return unicodedata.normalize("NFC", value or "").lower()


def _text_of(criterion: dict[str, Any]) -> str:
    keywords = criterion.get("expected_evidence_keywords") or []
    if not isinstance(keywords, list):
        keywords = []
    parts: Iterable[Any] = (
        criterion.get("name"), criterion.get("description"), criterion.get("evidence_guidance"), *keywords,
    )
    return _normalise(" \n ".join(str(part) for part in parts if part))


def detect_protected_attributes(criterion: dict[str, Any]) -> list[str]:
    """Return the sorted attribute codes a single criterion appears to rely on."""
    text = _text_of(criterion)
    if not text:
        return []
    found = {code for code, pattern in _COMPILED if pattern.search(text)}
    for code, phrases in _VIETNAMESE_PHRASES:
        if any(re.search(rf"(?<!\w){re.escape(phrase)}(?!\w)", text) for phrase in phrases):
            found.add(code)
    return sorted(found)


def fairness_warnings(criteria: Iterable[dict[str, Any]]) -> list[dict[str, Any]]:
    """One warning per flagged criterion, in rubric order."""
    warnings = []
    for criterion in criteria:
        attributes = detect_protected_attributes(criterion)
        if attributes:
            warnings.append({
                "criterion_id": str(criterion.get("criterion_id")) if criterion.get("criterion_id") else None,
                "name": criterion.get("name"),
                "attributes": attributes,
            })
    return warnings
