"""Request models for the F2.01 rubric library and F2.02 scorecards."""
from datetime import datetime
from decimal import Decimal
from typing import List, Literal, Optional
from uuid import UUID

from pydantic import BaseModel, Field, model_validator

from .criteria import CriteriaCategory


class JobFamilyCreate(BaseModel):
    code: str = Field(pattern=r"^[A-Za-z][A-Za-z0-9_]{1,49}$")
    name: str = Field(min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    display_order: int = Field(default=0, ge=0, le=10_000)


class JobFamilyUpdate(BaseModel):
    name: Optional[str] = Field(default=None, min_length=1, max_length=200)
    description: Optional[str] = Field(default=None, max_length=2000)
    status: Optional[Literal["ACTIVE", "INACTIVE"]] = None
    display_order: Optional[int] = Field(default=None, ge=0, le=10_000)


class TemplateCreate(BaseModel):
    job_family_id: UUID
    title: str = Field(min_length=1, max_length=200)
    level_band: Optional[str] = Field(default=None, max_length=100)
    change_note: Optional[str] = Field(default=None, max_length=2000)


class TemplateVersionCreate(BaseModel):
    source_version_id: Optional[UUID] = None
    change_note: Optional[str] = Field(default=None, max_length=2000)


class TemplateVersionUpdate(BaseModel):
    mandatory_weight_total: Optional[Decimal] = Field(default=None, gt=0, le=100, max_digits=5, decimal_places=2)
    nice_to_have_weight_total: Optional[Decimal] = Field(default=None, ge=0, le=100, max_digits=5, decimal_places=2)
    change_note: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def weights_together(self):
        given = [self.mandatory_weight_total is not None, self.nice_to_have_weight_total is not None]
        if any(given) and not all(given):
            raise ValueError("Cần gửi cả hai trọng số nhóm")
        if all(given) and self.mandatory_weight_total + self.nice_to_have_weight_total != Decimal("100"):
            raise ValueError("Tổng trọng số hai nhóm phải bằng 100%")
        return self


class TemplateItemCreate(BaseModel):
    name: str = Field(min_length=1, max_length=200)
    description: str = Field(min_length=1, max_length=4000)
    category: CriteriaCategory
    weight_in_group: float = Field(ge=0, le=100)
    expected_evidence_keywords: List[str] = Field(default_factory=list, max_length=20)
    evidence_guidance: Optional[str] = Field(default=None, max_length=4000)


class TemplateItemUpdate(BaseModel):
    name: Optional[str] = Field(default=None, max_length=200)
    description: Optional[str] = Field(default=None, max_length=4000)
    category: Optional[CriteriaCategory] = None
    weight_in_group: Optional[float] = Field(default=None, ge=0, le=100)
    expected_evidence_keywords: Optional[List[str]] = Field(default=None, max_length=20)
    evidence_guidance: Optional[str] = Field(default=None, max_length=4000)
    display_order: Optional[int] = Field(default=None, ge=0, le=10_000)


class TemplateReviewRequest(BaseModel):
    comment: Optional[str] = Field(default=None, max_length=2000)


class ApplyTemplateRequest(BaseModel):
    template_version_id: UUID


# ---------- F2.02 scorecards ----------

Recommendation = Literal["STRONG_YES", "YES", "NO", "STRONG_NO"]


class ScorecardCriterionInput(BaseModel):
    criterion_id: UUID
    rating: Optional[int] = Field(default=None, ge=1, le=5)
    insufficient_evidence: bool = False
    comment: Optional[str] = Field(default=None, max_length=2000)

    @model_validator(mode="after")
    def single_answer(self):
        if self.rating is not None and self.insufficient_evidence:
            raise ValueError("Mỗi tiêu chí chỉ chọn điểm 1–5 hoặc thiếu bằng chứng")
        return self


class ScorecardUpdate(BaseModel):
    criteria: List[ScorecardCriterionInput] = Field(default_factory=list, max_length=100)
    overall_recommendation: Optional[Recommendation] = None
    strengths: Optional[str] = Field(default=None, max_length=4000)
    concerns: Optional[str] = Field(default=None, max_length=4000)


class ScorecardReopenRequest(BaseModel):
    reason: str = Field(min_length=1, max_length=2000)


class ShareDueAt(BaseModel):
    due_at: Optional[datetime] = None
