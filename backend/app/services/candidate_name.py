"""Best-effort candidate name from the top of a CV. Rule based; when unsure it returns None
(never the file name, never invented). HR can always correct the name on the candidate page."""
import re

_PAGE_MARKER = re.compile(r"--- Page \d+ ---")
_NOT_A_NAME = re.compile(r"@|https?://|www\.|linkedin|github|\d")
# Section headings, job titles and place names that look like capitalised words but are not people.
_STOP_WORDS = {
    "curriculum", "vitae", "resume", "cv", "profile", "summary", "objective", "contact", "education", "experience",
    "skills", "projects", "references", "career", "history", "personal", "information", "details", "about",
    "engineer", "developer", "manager", "analyst", "designer", "senior", "junior", "lead", "intern", "specialist",
    "expert", "researcher", "owner", "tester", "consultant", "director", "architect", "scientist", "officer",
    "executive", "administrator", "backend", "frontend", "fullstack", "software", "data", "product", "business",
    "hanoi", "vietnam", "city", "email", "phone", "address", "mobile",
    "sơ", "lịch", "kỹ", "sư", "lập", "trình", "viên", "chuyên", "giám", "đốc", "trưởng",  # not "Lý", "Hồ", "Gia": real name parts
}
_STOP_PAIRS = {("ho", "chi"), ("chi", "minh"), ("hồ", "chí"), ("chí", "minh")}


def _words_ok(words: list[str]) -> bool:
    if not 2 <= len(words) <= 5:
        return False
    if not all(w.replace("-", "").replace("'", "").replace(".", "").isalpha() for w in words):
        return False
    lowered = [w.lower().strip(".") for w in words]
    if any(w in _STOP_WORDS for w in lowered):
        return False
    return not any(pair in _STOP_PAIRS for pair in zip(lowered, lowered[1:]))


def _title_case(words: list[str]) -> str:
    return " ".join(w[:1].upper() + w[1:].lower() if w == w.upper() else w for w in words)


def guess_candidate_name(cv_text: str | None, max_lines: int = 8) -> str | None:
    """The first of the top lines that looks like a person's name (2-5 words, no digits/contact/heading words)."""
    seen = 0
    for line in (cv_text or "").splitlines():
        candidate = re.sub(r"\s+", " ", line).strip(" \t|•·-–—:,")
        if not candidate or _PAGE_MARKER.fullmatch(candidate):
            continue
        seen += 1
        if seen > max_lines:
            break
        if len(candidate) > 60 or _NOT_A_NAME.search(candidate):
            continue
        words = candidate.split(" ")
        if _words_ok(words) and (candidate == candidate.upper() or all(w[:1].isupper() for w in words)):
            return _title_case(words)
    return None
