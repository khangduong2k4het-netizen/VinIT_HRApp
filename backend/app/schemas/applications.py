from pydantic import Field, model_validator
from datetime import datetime
from typing import List, Literal, Optional
from uuid import UUID
from enum import Enum
from .common import BaseSchema, TimestampMixin


class ApplicationStatus(str, Enum):
    NEW = "NEW"
    IN_REVIEW = "IN_REVIEW"
    SHORTLIST = "SHORTLIST"
    REJECTED_SCREENING = "REJECTED_SCREENING"
    INTERVIEW = "INTERVIEW"
    REJECTED_INTERVIEW = "REJECTED_INTERVIEW"
    OFFERED = "OFFERED"
    ACCEPTED = "ACCEPTED"


class FileProcessingStatus(str, Enum):
    RECEIVED = "RECEIVED"
    PROCESSING = "PROCESSING"
    COMPLETED = "COMPLETED"
    NEEDS_HR_REVIEW = "NEEDS_HR_REVIEW"
    ERROR_UNSUPPORTED = "ERROR_UNSUPPORTED"


class MatchingStatus(str, Enum):
    NOT_ASSESSED = "NOT_ASSESSED"
    NEEDS_HR_VERIFICATION = "NEEDS_HR_VERIFICATION"
    POSSIBLE_MISMATCH = "POSSIBLE_MISMATCH"
    MEETS_MANDATORY = "MEETS_MANDATORY"


class CVUploadItem(BaseSchema):
    filename: str
    content_type: str
    size_bytes: int


class CVBatchCreate(BaseSchema):
    position_id: UUID
    files: List[CVUploadItem]


class CVBatch(BaseSchema, TimestampMixin):
    batch_id: UUID
    position_id: UUID
    uploaded_by: UUID
    status: str  # pending, processing, completed, partially_completed, failed
    total_files: int
    total_size_bytes: int
    processed_files: int = 0
    failed_files: int = 0


class ApplicationIdentity(BaseSchema):
    display_name: Optional[str] = None
    email: Optional[str] = None
    phone: Optional[str] = None


class ApplicationBase(BaseSchema):
    position_id: UUID


class Application(ApplicationBase, TimestampMixin):
    application_id: UUID
    source_code: str = "DIRECT_UPLOAD"
    application_status: ApplicationStatus
    identity: Optional[ApplicationIdentity] = None
    # Ai đang giữ hồ sơ. NULL = chưa ai nhận; tên chỉ để hiển thị, quyết định
    # quyền vẫn nằm ở position_assignments.
    assigned_to: Optional[UUID] = None
    assigned_to_name: Optional[str] = None
    assigned_at: Optional[datetime] = None


class ApplicationDocument(BaseSchema, TimestampMixin):
    document_id: UUID
    application_id: UUID
    original_filename: str
    mime_type: str
    size_bytes: int
    storage_path: str
    document_type: str = "CV"
    file_processing_status: FileProcessingStatus
    processing_error: Optional[str] = None


class EvidenceItem(BaseSchema):
    evidence_id: UUID
    verbatim_quote: str
    page_number: Optional[int] = None
    verification_status: Optional[str] = None


class HrCriterionReviewOut(BaseSchema):
    review_id: UUID
    decision: str
    comment: Optional[str] = None
    reviewer_user_id: UUID
    reviewer_name: Optional[str] = None
    created_at: datetime


class HrCriterionReviewCreate(BaseSchema):
    decision: Literal["CONFIRMED", "REJECTED"]
    comment: Optional[str] = Field(default=None, max_length=1000)

    @model_validator(mode="after")
    def rejection_needs_reason(self):
        # Enforced again in the database: a rejection without a reason is a click,
        # not a review, and the next person to open the profile cannot use it.
        if self.decision == "REJECTED" and not (self.comment or "").strip():
            raise ValueError("Cần nêu lý do khi đánh dấu bằng chứng không đúng")
        return self


class CriterionResult(BaseSchema):
    # Needed by the review endpoint; without it the profile page cannot address
    # the decision the reviewer just took.
    result_id: Optional[UUID] = None
    criterion_id: UUID
    criterion_name: str
    category: str
    outcome: str
    score: Optional[float] = None
    confidence: Optional[float] = None
    confidence_band: Optional[str] = None
    reasoning: Optional[str] = None
    requires_verification: bool = False
    decision_source: str | None = None
    evidence_strength: float | None = None
    evidence_chunk_id: str | None = None
    rule_version: str | None = None
    verbatim_quote: Optional[str] = None
    page_number: Optional[int] = None
    evidence: List[EvidenceItem] = Field(default_factory=list)
    # Reviewer decisions, newest first. Present so the profile page can show
    # "you confirmed this" without a second request per criterion.
    hr_reviews: List[HrCriterionReviewOut] = Field(default_factory=list)


class AssessmentRun(BaseSchema, TimestampMixin):
    assessment_id: UUID
    position_id: UUID
    application_id: UUID
    criteria_version_id: UUID
    status: str
    matching_status: MatchingStatus
    matching_score: Optional[float] = None
    evidence_coverage: Optional[float] = None
    confidence: Optional[float] = None
    summary: Optional[str] = None
    assessment_fingerprint: str | None = None
    matching_policy_version: str | None = None
    prompt_version: str | None = None
    provider_model_snapshot: dict | None = None
    criterion_results: List[CriterionResult] = Field(default_factory=list)


class ApplicationStatusUpdate(BaseSchema):
    new_status: ApplicationStatus
    reason: Optional[str] = Field(default=None, max_length=1000)
    note: Optional[str] = Field(default=None, max_length=2000)


class ApplicationAssignmentUpdate(BaseSchema):
    """`None` trả hồ sơ về "chưa ai nhận" — không phải lỗi."""

    assigned_to_user_id: Optional[UUID] = None


class ApplicationCapabilities(BaseSchema):
    """One flag per action, each mirroring the gate of the endpoint it calls.

    The three flags on ``ApplicationWithAssessment`` are kept for older clients;
    this object is what the profile screen reads.
    """

    view_cv: bool = False
    view_evidence: bool = False
    update_status: bool = False
    review_evidence: bool = False
    manage_hr_notes: bool = False
    edit_profile: bool = False
    view_status_history: bool = False
    reprocess_cv: bool = False


class ApplicationWithAssessment(Application):
    latest_assessment: Optional[AssessmentRun] = None
    documents: List[ApplicationDocument] = Field(default_factory=list)
    rank_number: Optional[int] = None
    file_processing_status: str = "UNKNOWN"
    file_error: Optional[str] = None
    has_duplicate_warning: bool = False
    can_view_cv: bool = False
    can_view_assessment_evidence: bool = False
    can_update_status: bool = False
    can_manage_hr_notes: bool = False
    capabilities: ApplicationCapabilities = Field(default_factory=ApplicationCapabilities)


class RankingCriterionResult(BaseSchema):
    """Per-criterion summary shown next to a ranking row.

    ``effective_weight`` is the criterion's share of the whole rubric in
    percent (group total x weight inside the group), so HR can see why a
    partial score only covers part of the rubric.
    """

    criterion_id: UUID
    criterion_name: str
    category: str
    outcome: str
    score: Optional[float] = None
    effective_weight: Optional[float] = None
    requires_verification: bool = False


class RankingItem(BaseSchema):
    rank_number: Optional[int]
    application_id: UUID
    candidate_name: Optional[str]
    matching_status: MatchingStatus
    matching_score: Optional[float]
    evidence_coverage: Optional[float]
    ltr_score: Optional[float] = None
    needs_verification: bool
    has_mismatch: bool
    criterion_results: List[RankingCriterionResult] = Field(default_factory=list)
