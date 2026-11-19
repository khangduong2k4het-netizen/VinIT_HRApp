"""F2.03 HR override classification (application level).

An override is an HR screening decision that contradicts the AI conclusion
shown at that moment:

* ADVANCED_DESPITE_AI — HR moves the application into SHORTLIST although the
  AI did not conclude MEETS_MANDATORY;
* REJECTED_DESPITE_AI — HR rejects at screening an application the AI marked
  MEETS_MANDATORY.

Applications without a usable AI conclusion (no assessment or NOT_ASSESSED)
are never overrides. Post-interview decisions are not compared with the AI.
"""
from __future__ import annotations

from typing import Optional

REASON_CODES: dict[str, str] = {
    "SYNONYM_TERMS": "CV dùng từ đồng nghĩa",
    "EQUIVALENT_CREDENTIAL": "Chứng chỉ/bằng tương đương",
    "IMPLICIT_EVIDENCE": "Bằng chứng ngầm định",
    "INTERVIEW_VERIFICATION": "Thông tin từ phỏng vấn/xác minh",
    "EXTRACTION_ERROR": "Lỗi trích xuất/OCR",
    "CRITERIA_MISFIT": "Tiêu chí chưa phù hợp",
    "OTHER": "Khác",
}

AI_CONCLUSIONS = ("NEEDS_HR_VERIFICATION", "POSSIBLE_MISMATCH", "MEETS_MANDATORY")


def classify_override(new_status: str, ai_matching_status: Optional[str]) -> Optional[str]:
    if ai_matching_status not in AI_CONCLUSIONS:
        return None
    if new_status == "SHORTLIST" and ai_matching_status != "MEETS_MANDATORY":
        return "ADVANCED_DESPITE_AI"
    if new_status == "REJECTED_SCREENING" and ai_matching_status == "MEETS_MANDATORY":
        return "REJECTED_DESPITE_AI"
    return None


def override_reason_error(direction: Optional[str], reason_code: Optional[str], note: Optional[str]) -> Optional[str]:
    """Why the submitted reason is unacceptable, or None."""
    if direction is None:
        return None
    if not reason_code:
        return "Quyết định này khác kết luận của AI. Vui lòng chọn lý do điều chỉnh."
    if reason_code not in REASON_CODES:
        return "Lý do điều chỉnh không hợp lệ."
    if reason_code == "OTHER" and not (note or "").strip():
        return "Vui lòng ghi chú khi chọn lý do “Khác”."
    return None
