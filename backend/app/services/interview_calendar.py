"""Interview calendar (.ics) builder and AI evidence-grounded prep brief synthesizer.

Both helpers are pure / deterministic:
- ``build_ics`` produces an RFC 5545 UTF-8 iCalendar payload ready for Outlook / Google Calendar.
  Candidate contact PII and CV text are never placed in the .ics file.
- ``build_prep_brief`` turns existing criterion assessment results into structured interview
  talking points (what to probe for UNCLEAR / needs_verification / NO_MATCH criteria, plus
  verified strengths) with zero extra LLM calls.
"""
from __future__ import annotations

import re
from datetime import datetime, timedelta, timezone
from typing import Any

VN_TZ = timezone(timedelta(hours=7))

FORMAT_LABELS = {
    "ONLINE": "Trực tuyến (Online)",
    "ONSITE": "Trực tiếp tại VinUni",
    "PHONE": "Điện thoại",
}


def _to_utc(dt: datetime) -> datetime:
    return dt.replace(tzinfo=timezone.utc) if dt.tzinfo is None else dt.astimezone(timezone.utc)


def format_vn_slot(starts_at: datetime, ends_at: datetime) -> str:
    """Human-readable Vietnam time slot used to prefill F3.05 {thoi_gian_pv}."""
    s = _to_utc(starts_at).astimezone(VN_TZ)
    e = _to_utc(ends_at).astimezone(VN_TZ)
    if s.date() == e.date():
        return f"{s.strftime('%H:%M')} - {e.strftime('%H:%M')}, {s.strftime('%d/%m/%Y')} (GMT+7)"
    return f"{s.strftime('%H:%M %d/%m/%Y')} - {e.strftime('%H:%M %d/%m/%Y')} (GMT+7)"


def _ics_escape(value: str) -> str:
    cleaned = value.replace("\r\n", "\n").replace("\r", "\n")
    return (
        cleaned.replace("\\", "\\\\")
        .replace(";", "\\;")
        .replace(",", "\\,")
        .replace("\n", "\\n")
    )


def _fold_line(line: str) -> str:
    """RFC 5545 line folding (<= 75 octets per line)."""
    raw = line.encode("utf-8")
    if len(raw) <= 75:
        return line
    parts: list[str] = []
    buf = bytearray()
    limit = 75
    for ch in line:
        enc = ch.encode("utf-8")
        if len(buf) + len(enc) > limit:
            parts.append(buf.decode("utf-8"))
            buf = bytearray(b" " + enc)
            limit = 75
        else:
            buf.extend(enc)
    if buf:
        parts.append(buf.decode("utf-8"))
    return "\r\n".join(parts)


def safe_ics_filename(position_code: str | None, round_no: int) -> str:
    code = re.sub(r"[^A-Za-z0-9_-]", "", (position_code or "HRA").upper())[:32] or "HRA"
    return f"interview-{code}-round-{int(round_no)}.ics"


def build_ics(
    *,
    session_id: str,
    position_code: str | None,
    position_title: str,
    round_no: int,
    title: str,
    starts_at: datetime,
    ends_at: datetime,
    fmt: str,
    location_or_link: str | None,
    prep_notes: str | None = None,
) -> bytes:
    start_utc = _to_utc(starts_at)
    end_utc = _to_utc(ends_at)
    now_utc = datetime.now(timezone.utc)
    code_prefix = f"[{position_code}] " if position_code else ""
    summary = f"{code_prefix}{title} (Vòng {round_no}) - {position_title}"
    location = (location_or_link or "").strip() or (
        "Trường Đại học VinUni" if fmt == "ONSITE" else FORMAT_LABELS.get(fmt, fmt)
    )
    desc_lines = [
        f"Vị trí: {position_title}" + (f" ({position_code})" if position_code else ""),
        f"Vòng phỏng vấn: {round_no}",
        f"Hình thức: {FORMAT_LABELS.get(fmt, fmt)}",
    ]
    if location_or_link:
        desc_lines.append(f"Địa điểm / Link: {location_or_link.strip()}")
    if prep_notes and prep_notes.strip():
        desc_lines.append(f"Ghi chú chuẩn bị: {prep_notes.strip()}")
    desc_lines.append("Tạo từ VinUni HRA — mở hồ sơ ứng viên trong hệ thống để xem bằng chứng CV và gợi ý câu hỏi.")

    lines = [
        "BEGIN:VCALENDAR",
        "VERSION:2.0",
        "PRODID:-//VinUniversity//HRA Interview Coordination//VI",
        "CALSCALE:GREGORIAN",
        "METHOD:PUBLISH",
        "BEGIN:VEVENT",
        f"UID:hra-interview-{session_id}@vinuni.edu.vn",
        f"DTSTAMP:{now_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTSTART:{start_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"DTEND:{end_utc.strftime('%Y%m%dT%H%M%SZ')}",
        f"SUMMARY:{_ics_escape(summary)}",
        f"LOCATION:{_ics_escape(location)}",
        f"DESCRIPTION:{_ics_escape(chr(10).join(desc_lines))}",
        "STATUS:CONFIRMED",
        "END:VEVENT",
        "END:VCALENDAR",
    ]
    return ("\r\n".join(_fold_line(line) for line in lines) + "\r\n").encode("utf-8")


def build_prep_brief(criterion_rows: list[dict[str, Any]]) -> dict[str, Any]:
    """Build an evidence-backed Interview Prep Brief from criterion assessment rows."""
    probe_points: list[dict[str, Any]] = []
    strengths: list[dict[str, Any]] = []

    for row in criterion_rows:
        outcome = str(row.get("outcome") or "").upper()
        needs_verify = bool(row.get("requires_verification"))
        name = str(row.get("criterion_name") or "").strip()
        if not name:
            continue
        category = str(row.get("category") or "MUST_HAVE")
        quote = (row.get("quote") or "").strip() or None
        page_number = row.get("page_number")

        if outcome in ("UNCLEAR", "NO_MATCH") or needs_verify:
            if outcome == "UNCLEAR":
                prompt = f"CV chưa nêu rõ bằng chứng cho tiêu chí “{name}” — đề nghị ứng viên trình bày ví dụ thực tế và phạm vi đảm nhận."
                priority = "HIGH" if category == "MUST_HAVE" else "MEDIUM"
            elif outcome == "NO_MATCH":
                prompt = f"Hồ sơ có dấu hiệu chưa đáp ứng “{name}” — xác minh lại kinh nghiệm tương đương hoặc khả năng bù đắp."
                priority = "HIGH" if category == "MUST_HAVE" else "MEDIUM"
            else:
                prompt = f"Bằng chứng cho “{name}” cần xác minh thêm độ sâu thực chiến trong buổi phỏng vấn."
                priority = "MEDIUM"
            probe_points.append({
                "criterion_id": str(row["criterion_id"]),
                "criterion_name": name,
                "category": category,
                "outcome": outcome,
                "requires_verification": needs_verify,
                "priority": priority,
                "suggested_question": prompt,
                "evidence_quote": quote,
                "page_number": page_number,
            })
        elif outcome in ("STRONG_MATCH", "MATCH"):
            strengths.append({
                "criterion_id": str(row["criterion_id"]),
                "criterion_name": name,
                "category": category,
                "outcome": outcome,
                "evidence_quote": quote,
                "page_number": page_number,
            })

    probe_points.sort(key=lambda item: (0 if item["priority"] == "HIGH" else 1, 0 if item["category"] == "MUST_HAVE" else 1))
    return {
        "probe_points": probe_points[:8],
        "strengths": strengths[:5],
        "probe_count": len(probe_points),
        "strength_count": len(strengths),
    }
