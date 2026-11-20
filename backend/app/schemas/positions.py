from pydantic import BaseModel, Field
from datetime import datetime
from typing import Optional, List
from uuid import UUID
from enum import Enum
from .common import BaseSchema, TimestampMixin


class PositionStatus(str, Enum):
    OPEN = "OPEN"
    PAUSED = "PAUSED"
    CLOSED = "CLOSED"


class PositionRole(str, Enum):
    HR_RECRUITER = "HR_RECRUITER"
    HIRING_MANAGER = "HIRING_MANAGER"
    HR_LEAD = "HR_LEAD"
    VIEWER = "VIEWER"


class PositionBase(BaseSchema):
    position_code: str = Field(..., description="Unique position code, e.g. REQ-IT-001")
    title: str
    job_family: Optional[str] = None  # e.g. Software Engineering, QA
    job_family_id: Optional[UUID] = None  # F2.01 taxonomy; job_family text is kept in sync
    org_unit: Optional[str] = None
    level: Optional[str] = None  # e.g. Junior, Mid, Senior
    work_location: Optional[str] = None
    work_mode: Optional[str] = None  # Remote, Hybrid, On-site
    employment_type: Optional[str] = None  # Full-time, Contract, etc.
    headcount: Optional[int] = Field(default=1, ge=1)
    # F3.03: candidate-facing posting text (intro, benefits, deadline). Shown on the
    # candidate website next to the JD; never used for screening.
    posting_content: Optional[str] = Field(default=None, max_length=20000)


class PositionCreate(PositionBase):
    # New positions choose a department; the backend generates position_code
    # from that department's code_format (for example REQ-IT-001).
    department_id: UUID
    position_code: Optional[str] = Field(default=None, max_length=100)  # Deprecated: ignored, generated server-side
    org_unit: Optional[str] = Field(default=None, max_length=255)  # Deprecated: snapshot comes from the department
    jd_content: str = Field(..., description="Job Description text content in English")
    hiring_manager_user_id: Optional[UUID] = Field(
        None,
        description="User ID of the Hiring Manager responsible for this position (will auto-assign HIRING_MANAGER role)"
    )


class PositionUpdate(BaseSchema):
    title: Optional[str] = None
    status: Optional[PositionStatus] = None
    # Stored on the status-change history; required when pausing or closing.
    status_reason: Optional[str] = Field(default=None, max_length=1000)
    job_family_id: Optional[UUID] = None
    level: Optional[str] = Field(default=None, max_length=100)
    work_location: Optional[str] = None
    work_mode: Optional[str] = None
    posting_content: Optional[str] = Field(default=None, max_length=20000)


class PositionStatusEvent(BaseModel):
    event_id: UUID
    position_id: UUID
    previous_status: Optional[str] = None
    new_status: str
    changed_by: UUID
    changed_by_name: Optional[str] = None
    reason: Optional[str] = None
    changed_at: datetime


class Position(PositionBase, TimestampMixin):
    position_id: UUID
    department_id: Optional[UUID] = None
    department_name: Optional[str] = None
    department_code_format: Optional[str] = None
    department_sequence: Optional[int] = None
    status: PositionStatus
    created_by: UUID
    opened_at: Optional[datetime] = None
    closed_at: Optional[datetime] = None
    # P3-3: shown on the public /apply portal (HR opt-in per position).
    public_apply_enabled: bool = False


class PositionWithStats(Position):
    total_applications: int = 0
    new_applications: int = 0
    in_review: int = 0
    shortlisted: int = 0
    criteria_approved: bool = False
    criteria_status: Optional[str] = None  # Latest version, which can be newer than the approved version.
    public_apply_enabled: bool = False  # This position accepts CVs from the public /apply form.
    public_intake_enabled: bool = False  # The /apply portal itself is switched on (PUBLIC_INTAKE_ENABLED).


class JDVersionCreate(BaseModel):
    content_text: str = Field(min_length=1, max_length=100_000)
    # F1.01: JDs are English by default; Vietnamese is still accepted.
    language_code: str = Field(default="en", pattern="^(vi|en)$")
    expected_jd_version_id: UUID
