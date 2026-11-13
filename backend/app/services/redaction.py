"""Best-effort minimisation before model calls, not a guarantee of anonymity.

No values or reversible redaction map are logged or sent to the model.  Free
text can contain unlabelled names, addresses or other identifying information;
a private model and network-level egress controls are still required.
"""
import re
from typing import Any

REDACTED = "[REDACTED]"

# Labels are deliberately conservative: discard the entire line rather than
# accidentally preserving a sensitive value next to another delimiter.
_LABEL = re.compile(
    r"(?im)^\s*(?:full\s*name|candidate\s*name|name|họ\s*(?:và\s*)?tên|ho\s*(?:va\s*)?ten|"
    r"email|e-mail|điện\s*thoại|dien\s*thoai|số\s*điện\s*thoại|phone|mobile|tel|"
    r"date\s*of\s*birth|birth\s*date|dob|ngày\s*sinh|ngay\s*sinh|năm\s*sinh|age|tuổi|tuoi|"
    r"gender|sex|giới\s*tính|gioi\s*tinh|marital\s*status|tình\s*trạng\s*hôn\s*nhân|"
    r"nationality|citizenship|quốc\s*tịch|quoc\s*tich|ethnicity|race|religion|tôn\s*giáo|"
    r"disability|medical\s*(?:history|condition)|health|sức\s*khỏe|"
    r"address|residence|địa\s*chỉ|dia\s*chi|current\s*salary|expected\s*salary|salary|lương|"
    r"passport|identity\s*(?:card|number)|national\s*id|cccd|cmnd)\s*[:：-]\s*[^\n]*"
)
_NAME_LABEL = re.compile(
    r"(?im)^\s*(?:full\s*name|candidate\s*name|name|họ\s*(?:và\s*)?tên|ho\s*(?:va\s*)?ten)\s*[:：-]\s*([^\n|,;]+)"
)
_EMAIL = re.compile(r"(?i)(?<![\w.+-])[a-z0-9.!#$%&'*+/=?^_`{|}~-]+@[a-z0-9-]+(?:\.[a-z0-9-]+)+")
_URL = re.compile(r"(?i)\b(?:https?://|www\.)[^\s<>]+|\b(?:linkedin\.com|github\.com)/[^\s<>]+")
# Not right after "." or "/": "GPA 3.6/4.0 (2016 - 2020)" is not a phone number.
_NUMBER = re.compile(r"(?<![\w\d./])\+?\d[\d .()\-]{7,}\d(?![\w\d])")
# OCR often reads 0 as O/o and 1 as l/I/|. A run of digit-like characters is a
# phone/ID candidate only when most of it is real digits, so ordinary words
# are never touched.
_DIGITISH = re.compile(r"(?<![\w./])\+?[\dOoIl|][\dOoIl| .()\-]{7,}[\dOoIl|](?![\w])")
_YEAR_RANGE = re.compile(r"(?:19|20)\d{2}\s*[-–]\s*(?:19|20)\d{2}")
_OCR_DIGIT = str.maketrans({"O": "0", "o": "0", "I": "1", "l": "1", "|": "1"})
# Emails written to dodge filters or split by OCR: "a.b @ gmail . com",
# "a.b(at)gmail(dot)com", "a.b [at] gmail.com".
_EMAIL_LOOSE = re.compile(
    r"(?i)(?<![\w.+-])[a-z0-9._%+-]+\s*(?:@|\(at\)|\[at\]|\{at\})\s*[a-z0-9-]+"
    r"(?:\s*(?:\.|\(dot\)|\[dot\]|\{dot\})\s*[a-z0-9-]+)*\s*(?:\.|\(dot\)|\[dot\]|\{dot\})\s*[a-z]{2,10}\b"
)
# A date of birth without a "label:" prefix ("Sinh 01/01/1998", "born on 1.1.1998").
_BIRTH_DATE = re.compile(
    r"(?i)\b(sinh(?:\s+ngày)?|ngày\s+sinh|năm\s+sinh|DOB|born(?:\s+on)?|birth\s*(?:day|date)?)\b"
    r"([^\n\d]{0,12})(\d{1,2}\s*[/.\-]\s*\d{1,2}\s*[/.\-]\s*(?:19|20)\d{2}|(?:19|20)\d{2})"
)
# Unlabelled Vietnamese street addresses: a house number, then comma-separated
# parts ending in a city, or a ward/district/province word. Kept narrow so work
# locations such as "FPT Software, Hanoi" stay readable.
_CITY = (r"(?:Hà\s*Nội|Ha\s*Noi|Hanoi|Hồ\s*Chí\s*Minh|Ho\s*Chi\s*Minh|HCMC|TP\.?\s*HCM|Đà\s*Nẵng|Da\s*Nang|"
         r"Hải\s*Phòng|Hai\s*Phong|Cần\s*Thơ|Can\s*Tho|Việt\s*Nam|Viet\s*Nam|Vietnam)")
_HOUSE = (r"(?<![\w/.])(?:số\s*)?(?!(?:19|20)\d{2}\b)\d{1,5}[a-z]?(?:/\d{1,5}){0,3}"
          r"(?!\s*\+?\s*(?:years?|yrs?|năm|tháng|months?|weeks?|tuần|%|người|people|members?)\b)")
_STREET = r"(?:đường|phố|ngõ|ngách|hẻm|kiệt|street|st\.|road|rd\.|lane|alley|avenue|ave\.)"
_ADDRESS = re.compile(
    # "123 Nguyễn Trãi, Thanh Xuân, Hà Nội": at least two commas before the city
    r"(?i)" + _HOUSE + r"\s+[^\n,;:]{2,40}(?:,\s*[^\n,;:]{2,40}){1,3},\s*" + _CITY + r"\b"
    # "12 Tran Hung Dao Street, Hanoi": a street word, then the city
    + r"|" + _HOUSE + r"\s+[^\n,;:]{0,40}\b" + _STREET + r"[^\n,;:]{0,40},\s*(?:[^\n,;:]{2,40},\s*){0,2}" + _CITY + r"\b"
    # "Số 12/3 ngõ 45 ..., phường ..., quận ...": a ward/district/province word
    + r"|" + _HOUSE + r"\s+[^\n;:]{0,60}?\b(?:phường|quận|huyện|thị\s*xã|thị\s*trấn|tỉnh)\b[^\n;]{0,80}"
)


def _mask_numbers(text: str) -> str:
    """Phone and ID numbers (9+ digits), including OCR-garbled digits."""
    def plain(match: re.Match) -> str:
        value = match.group()
        if _YEAR_RANGE.search(value):
            return value
        return REDACTED if len(re.sub(r"\D", "", value)) >= 9 else value

    text = _NUMBER.sub(plain, text)

    def garbled(match: re.Match) -> str:
        value = match.group()
        if _YEAR_RANGE.search(value):
            return value
        real = sum(ch.isdigit() for ch in value)
        mapped = re.sub(r"\D", "", value.translate(_OCR_DIGIT))
        return REDACTED if len(mapped) >= 9 and real >= 0.6 * len(mapped) else value

    return _DIGITISH.sub(garbled, text)
_HEADING_WORDS = {"resume", "curriculum", "vitae", "profile", "engineer", "developer", "manager",
                  "experience", "education", "skills", "summary", "professional", "software", "candidate",
                  "hồ", "sơ", "ứng", "viên", "kinh", "nghiệm", "kỹ", "năng"}
_SENSITIVE_KEYS = re.compile(
    r"(?i)^(?:name|full_?name|candidate_?name|email|phone|mobile|address|dob|date_?of_?birth|"
    r"birth_?date|age|gender|sex|marital_?status|nationality|citizenship|race|ethnicity|religion|"
    r"disability|medical(?:_.*)?|health(?:_.*)?|photo|passport|national_?id|salary|"
    r"họ_?tên|địa_?chỉ|ngày_?sinh|giới_?tính|quốc_?tịch)$"
)


def _looks_like_name(value: str) -> bool:
    words = value.strip().split()
    return (2 <= len(words) <= 5 and len(value.strip()) >= 5
            and all(word.replace("-", "").replace("'", "").isalpha() for word in words)
            and not any(word.lower() in _HEADING_WORDS for word in words)
            and (value == value.upper() or all(word[0].isupper() for word in words)))


def redact_text(value: str, *, detect_first_line_name: bool = False) -> str:
    """Remove common labelled identifiers and contact details from free text.

    Existing page markers are kept intact for evidence verification.  Detection
    is imperfect, especially for unlabelled names, OCR errors and addresses.
    """
    if not value:
        return value
    names = [m.group(1).strip() for m in _NAME_LABEL.finditer(value)]
    # CVs often start with the person's name without a label. Only use a very
    # narrow heuristic; a real DLP/NER review is needed for stronger coverage.
    if detect_first_line_name:
        for line in value.splitlines():
            candidate = line.strip()
            if not candidate or re.fullmatch(r"--- Page \d+ ---", candidate):
                continue
            if _looks_like_name(candidate):
                names.append(candidate)
            break
    result = _LABEL.sub(REDACTED, value)
    result = _EMAIL.sub(REDACTED, result)
    result = _EMAIL_LOOSE.sub(REDACTED, result)
    result = _URL.sub(REDACTED, result)
    result = _BIRTH_DATE.sub(lambda m: f"{m.group(1)}{m.group(2)}{REDACTED}", result)
    result = _ADDRESS.sub(REDACTED, result)
    result = _mask_numbers(result)
    for name in sorted(set(names), key=len, reverse=True):
        if _looks_like_name(name):
            result = re.sub(r"(?<!\w)" + re.escape(name) + r"(?!\w)", REDACTED, result, flags=re.IGNORECASE)
    return result


def redact_payload(value: Any) -> Any:
    """Recursively minimise structured model inputs and outputs.

    ``name`` on a profile fact can mean a skill or qualification, so callers
    explicitly reconstruct an allowlisted profile rather than passing identities.
    """
    if isinstance(value, dict):
        return {str(k): redact_payload(v) for k, v in value.items() if not _SENSITIVE_KEYS.match(str(k))}
    if isinstance(value, list):
        return [redact_payload(item) for item in value]
    if isinstance(value, str):
        return redact_text(value)
    if value is None or isinstance(value, (int, float, bool)):
        return value
    return str(value)


def redact_professional_profile(value: Any) -> Any:
    """Minimise a structured profile while preserving known qualification names.

    The bare key ``name`` is ambiguous and remains forbidden everywhere in
    the generic sanitizer. Only the explicitly professional certification,
    language and project collections may carry it; identity-like fields in
    those objects are still dropped. These values are free text, so this is
    best-effort minimisation, not an anonymity guarantee.
    """
    clean = redact_payload(value)
    if not isinstance(value, dict) or not isinstance(clean, dict):
        return clean
    for section in ("certifications", "languages", "projects"):
        source, target = value.get(section), clean.get(section)
        if not isinstance(source, list) or not isinstance(target, list):
            continue
        for item, result in zip(source, target):
            if isinstance(item, dict) and isinstance(result, dict) and isinstance(item.get("name"), str):
                result["name"] = redact_text(item["name"])
    return clean
