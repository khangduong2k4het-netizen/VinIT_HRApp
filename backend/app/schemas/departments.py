from uuid import UUID

from pydantic import Field

from .common import BaseSchema, TimestampMixin


class DepartmentCreate(BaseSchema):
    name: str = Field(min_length=1, max_length=160)
    code_format: str = Field(min_length=3, max_length=80)
    is_active: bool = True


class DepartmentUpdate(BaseSchema):
    name: str | None = Field(default=None, min_length=1, max_length=160)
    code_format: str | None = Field(default=None, min_length=3, max_length=80)
    is_active: bool | None = None


class Department(DepartmentCreate, TimestampMixin):
    department_id: UUID
    next_sequence: int = 1
    position_count: int = 0
    created_by: UUID | None = None
