from typing import Literal

from pydantic import BaseModel, ConfigDict, EmailStr, Field, SecretStr, field_validator

Role = Literal["ADMIN", "HR_LEAD", "HR_RECRUITER", "HIRING_MANAGER", "VIEWER"]
AccountStatus = Literal["ACTIVE", "INACTIVE", "SUSPENDED"]


def validate_password(value: SecretStr) -> SecretStr:
    password = value.get_secret_value()
    # Supabase's bcrypt implementation can have a 72-byte password limit.
    try:
        password_bytes = len(password.encode("utf-8"))
    except UnicodeError:
        raise ValueError("Password must be valid UTF-8") from None
    if len(password) < 12 or password_bytes > 72 or not password.strip():
        raise ValueError("Password must be at least 12 characters and at most 72 UTF-8 bytes")
    return value


class AccountIdentity(BaseModel):
    model_config = ConfigDict(extra="forbid")
    email: EmailStr
    display_name: str = Field(min_length=1, max_length=120)
    password: SecretStr

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Display name must not be blank")
        return name

    _password = field_validator("password")(validate_password)


class BootstrapRequest(AccountIdentity):
    setup_token: SecretStr = Field(min_length=1, max_length=256)


class AdminUserCreate(AccountIdentity):
    roles: list[Role] = Field(min_length=1, max_length=5)

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, roles: list[Role]) -> list[Role]:
        if len(set(roles)) != len(roles):
            raise ValueError("Roles must be unique")
        return roles


class AdminUserUpdate(BaseModel):
    model_config = ConfigDict(extra="forbid")
    display_name: str = Field(min_length=1, max_length=120)
    account_status: AccountStatus
    roles: list[Role] = Field(min_length=1, max_length=5)

    @field_validator("display_name")
    @classmethod
    def clean_name(cls, value: str) -> str:
        name = value.strip()
        if not name:
            raise ValueError("Display name must not be blank")
        return name

    @field_validator("roles")
    @classmethod
    def unique_roles(cls, roles: list[Role]) -> list[Role]:
        if len(set(roles)) != len(roles):
            raise ValueError("Roles must be unique")
        return roles


class PasswordChange(BaseModel):
    model_config = ConfigDict(extra="forbid")
    current_password: SecretStr = Field(min_length=1, max_length=256)
    new_password: SecretStr

    @field_validator("current_password")
    @classmethod
    def current_is_utf8(cls, value: SecretStr) -> SecretStr:
        try:
            if len(value.get_secret_value().encode("utf-8")) > 72:
                raise ValueError("Password is too long")
        except UnicodeError:
            raise ValueError("Password must be valid UTF-8") from None
        return value

    _password = field_validator("new_password")(validate_password)


class AdminPasswordReset(BaseModel):
    model_config = ConfigDict(extra="forbid")
    new_password: SecretStr

    _password = field_validator("new_password")(validate_password)
