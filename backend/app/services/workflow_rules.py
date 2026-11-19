"""Pure business rules for Phase 2 workflow core (F2.01 / F2.02).

Kept free of database access so they can be unit tested directly.
"""
from __future__ import annotations

from datetime import datetime, timedelta
from decimal import Decimal
from typing import Any, Iterable

from app.services.criteria_fairness import fairness_warnings

DEFAULT_SCORECARD_BUSINESS_DAYS = 3  # D-08
RECOMMENDATIONS = ("STRONG_YES", "YES", "NO", "STRONG_NO")  # D-06
INSUFFICIENT_EVIDENCE = "INSUFFICIENT_EVIDENCE"


def _decimal(value: Any) -> Decimal:
    return value if isinstance(value, Decimal) else Decimal(str(value))


def template_publish_errors(mandatory_total: Any, nice_total: Any, items: Iterable[dict]) -> list[str]:
    """Reasons a template version cannot be published (empty list = publishable).

    Rules (plan §4.1): the two group totals add up to 100; at least one weighted
    MUST_HAVE criterion; every category in use sums to exactly 100; no criterion
    may rely on non-job-related personal attributes (F1.02 guard).
    """
    items = list(items)
    errors: list[str] = []
    mandatory, nice = _decimal(mandatory_total), _decimal(nice_total)
    if mandatory <= 0 or nice < 0 or mandatory + nice != Decimal("100"):
        errors.append("Tổng trọng số nhóm Bắt buộc và Ưu tiên phải bằng 100%.")
    if not items:
        errors.append("Template phải có ít nhất một tiêu chí.")
        return errors
    if not any(item["category"] == "MUST_HAVE" and _decimal(item["weight_in_group"]) > 0 for item in items):
        errors.append("Cần ít nhất một tiêu chí Bắt buộc có trọng số lớn hơn 0.")
    for category, label in (("MUST_HAVE", "Bắt buộc"), ("NICE_TO_HAVE", "Ưu tiên")):
        weights = [_decimal(item["weight_in_group"]) for item in items if item["category"] == category]
        if weights and sum(weights) != Decimal("100"):
            errors.append(f"Tổng trọng số các tiêu chí nhóm {label} phải bằng 100% (hiện tại {sum(weights)}%).")
    if nice > 0 and not any(item["category"] == "NICE_TO_HAVE" for item in items):
        errors.append("Nhóm Ưu tiên có trọng số nhưng chưa có tiêu chí; đặt trọng số nhóm Ưu tiên về 0 hoặc thêm tiêu chí.")
    flagged = fairness_warnings(items)
    if flagged:
        names = ", ".join(str(w["name"]) for w in flagged[:5])
        errors.append(f"Tiêu chí dựa trên thông tin cá nhân không liên quan đến công việc: {names}.")
    return errors


def add_business_days(start: datetime, days: int = DEFAULT_SCORECARD_BUSINESS_DAYS) -> datetime:
    """Add working days, skipping Saturday and Sunday (public holidays are not modelled yet)."""
    if days < 0:
        raise ValueError("days must be non-negative")
    current = start
    remaining = days
    while remaining:
        current += timedelta(days=1)
        if current.weekday() < 5:
            remaining -= 1
    return current


def scorecard_completion_errors(criteria: Iterable[dict], overall_recommendation: str | None) -> list[str]:
    """Reasons a scorecard cannot be submitted (D-07)."""
    errors: list[str] = []
    criteria = list(criteria)
    if not criteria:
        errors.append("Scorecard chưa có tiêu chí để đánh giá.")
    missing = [c.get("name") or str(c.get("criterion_id")) for c in criteria
               if c.get("rating") is None and c.get("evidence_assessment") != INSUFFICIENT_EVIDENCE]
    if missing:
        errors.append("Chưa đánh giá tiêu chí: " + ", ".join(str(m) for m in missing[:5])
                      + (f" và {len(missing) - 5} tiêu chí khác" if len(missing) > 5 else "") + ".")
    if overall_recommendation not in RECOMMENDATIONS:
        errors.append("Vui lòng chọn khuyến nghị chung.")
    return errors
