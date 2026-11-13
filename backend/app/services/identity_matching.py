"""Conservative identity signals; never merges candidates or strips email aliases."""
import re
import unicodedata
from difflib import SequenceMatcher


_PHONE_CANDIDATE = re.compile(r"(?<![\w./])\+?\d[\d .()\-]{7,}\d(?![\w\d])")
_YEAR_RANGE = re.compile(r"(?:19|20)\d{2}\s*[-–—]\s*(?:19|20)\d{2}")


def extract_phone(text: str | None) -> str | None:
    """First phone-like number in CV text: 9-15 digits, never a year range.

    "B.Sc. (2016 - 2020)" used to be read as phone 20162020, which made every
    candidate with the same study years a "duplicate".
    """
    for match in _PHONE_CANDIDATE.finditer(text or ""):
        value = match.group(0)
        if _YEAR_RANGE.search(value):
            continue
        digits = re.sub(r"\D", "", value)
        if 9 <= len(digits) <= 15:
            return digits
    return None


def normalize_email(value: str | None) -> str:
    value = (value or "").strip().casefold()
    return value if re.fullmatch(r"[^\s@]+@[^\s@]+\.[^\s@]+", value) else ""


def normalize_phone(value: str | None) -> str:
    value = (value or "").strip()
    if not value or re.search(r"[^\d\s+().-]", value):
        return ""
    digits = re.sub(r"\D", "", value)
    if digits.startswith("0084"):
        digits = digits[2:]
    if len(digits) == 10 and digits.startswith("0"):
        digits = "84" + digits[1:]
    return digits if 9 <= len(digits) <= 15 else ""


def normalize_name(value: str | None) -> str:
    value = unicodedata.normalize("NFKD", (value or "").casefold().replace("đ", "d"))
    return " ".join(re.findall(r"[^\W\d_]+", "".join(c for c in value if not unicodedata.combining(c))))


def identity_signal(first: dict, second: dict) -> tuple[str, float] | None:
    """Exact contacts first; fuzzy names need independently similar career content."""
    email = normalize_email(first.get("email"))
    if email and email == normalize_email(second.get("email")):
        return "EMAIL_MATCH", 0.98
    phone = normalize_phone(first.get("phone"))
    if phone and phone == normalize_phone(second.get("phone")):
        return "PHONE_MATCH", 0.95
    a, b = normalize_name(first.get("display_name")), normalize_name(second.get("display_name"))
    if len(a.split()) < 2 or len(b.split()) < 2 or SequenceMatcher(None, a, b).ratio() < 0.92:
        return None
    tokens = lambda s: set(re.findall(r"\w{3,}", (s or "").casefold()))
    x, y = tokens(first.get("career_text")), tokens(second.get("career_text"))
    if min(len(x), len(y)) >= 20 and len(x & y) / len(x | y) >= 0.85:
        return "NAME_CONTENT_MATCH", 0.85
    return None
