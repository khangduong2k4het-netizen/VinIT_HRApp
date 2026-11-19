"""Org-wide HR thresholds that HR may tune without a deploy.

Everything here is a product decision, not a technical constant. Each setting has
a named default, a sane range and a plain-language meaning, so a bad value fails
loudly at the API instead of silently producing an odd screen.

Reads are fail-soft: if the settings table is unreachable the shipped default is
used, because a missing row must never stop HR from seeing their work queue.
Writes are strict: an unknown key, a non-integer or an out-of-range value is a
400 with a message that names the setting.
"""
from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import text


@dataclass(frozen=True)
class SettingSpec:
    key: str
    default: int
    minimum: int
    maximum: int
    label: str
    description: str


SETTINGS: dict[str, SettingSpec] = {
    "deadline_soon_days": SettingSpec(
        key="deadline_soon_days",
        default=7,
        minimum=1,
        maximum=60,
        label="Số ngày báo trước khi hết hạn ứng tuyển",
        description=(
            "Vị trí còn ít hơn hoặc bằng số ngày này sẽ hiện việc "
            "\"Vị trí sắp hết hạn ứng tuyển\" trên Dashboard."
        ),
    ),
    "waiting_attention_days": SettingSpec(
        key="waiting_attention_days",
        default=7,
        minimum=1,
        maximum=90,
        label="Số ngày hồ sơ được tính là chờ lâu",
        description=(
            "Hồ sơ đang sàng lọc lâu hơn số ngày này được đếm vào dòng "
            "\"hồ sơ chờ quá N ngày\" trên Dashboard và được tô đậm trong danh sách ứng viên."
        ),
    ),
}


class SettingError(ValueError):
    """A setting key or value the API refuses to store."""


def load_settings(db) -> dict[str, int]:
    """Every known threshold, with defaults filling any row that is missing."""
    values = {spec.key: spec.default for spec in SETTINGS.values()}
    try:
        rows = db.execute(
            text("SELECT setting_key, value_int FROM app_private.app_settings")
        ).all()
    except Exception:  # noqa: BLE001 - a missing table must not break a read path
        return values
    for key, value in rows:
        spec = SETTINGS.get(key)
        if spec is not None and value is not None and spec.minimum <= value <= spec.maximum:
            values[key] = int(value)
    return values


def get_setting(db, key: str) -> int:
    return load_settings(db)[key]


def validated_value(key: str, value: object) -> int:
    """Return the value as an int, or raise with a message HR can act on."""
    spec = SETTINGS.get(key)
    if spec is None:
        raise SettingError(f"Không có cài đặt nào tên \"{key}\"")
    # bool is an int in Python; True would otherwise become 1 day.
    if isinstance(value, bool) or not isinstance(value, int):
        raise SettingError(f"\"{spec.label}\" phải là một số nguyên")
    if not spec.minimum <= value <= spec.maximum:
        raise SettingError(
            f"\"{spec.label}\" phải nằm trong khoảng {spec.minimum}–{spec.maximum} ngày"
        )
    return value


def save_setting(db, key: str, value: object, user_id: str) -> int:
    """Validate then upsert one setting; the caller commits and audits."""
    number = validated_value(key, value)
    db.execute(
        text(
            """
            INSERT INTO app_private.app_settings (setting_key, value_int, updated_at, updated_by)
            VALUES (:key, :value, now(), :user)
            ON CONFLICT (setting_key) DO UPDATE
            SET value_int = EXCLUDED.value_int,
                updated_at = EXCLUDED.updated_at,
                updated_by = EXCLUDED.updated_by
            """
        ),
        {"key": key, "value": number, "user": user_id},
    )
    return number


def public_payload(values: dict[str, int]) -> list[dict]:
    """Shape the settings screen renders: value, range and what it changes."""
    return [
        {
            "key": spec.key,
            "value": values[spec.key],
            "default": spec.default,
            "min": spec.minimum,
            "max": spec.maximum,
            "label": spec.label,
            "description": spec.description,
        }
        for spec in SETTINGS.values()
    ]
