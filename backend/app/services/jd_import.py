"""Import a job description from a public job-posting web page.

HR pastes a link (for example a VinUni Talent posting); the backend fetches the
page, reads the schema.org ``JobPosting`` block when the site publishes one and
falls back to the page's visible text otherwise. The AI step only reorganises
that text into a JD *draft*: HR reviews and edits it before a position is
created, exactly like a JD typed by hand.

Safety: the URL comes from a user, so fetching it is a server-side request.
Only http(s) on the standard ports is allowed, every resolved address must be
public (no localhost, private, link-local or metadata ranges) and each redirect
is checked again. Responses are size- and time-limited and must be HTML. The
page content is untrusted data; nothing in it is followed as an instruction.
"""
from __future__ import annotations

import html as html_lib
import ipaddress
import json
import re
import socket
from dataclasses import dataclass, field
from html.parser import HTMLParser
from typing import Any
from urllib.parse import urljoin, urlsplit

import httpx

from app.core.config import settings

MAX_REDIRECTS = 3
USER_AGENT = "VinUni-HRA-JD-Import/1.0 (+internal recruiting tool)"


class JDImportError(Exception):
    """A user-facing reason the page could not be imported."""

    def __init__(self, code: str, message: str):
        super().__init__(message)
        self.code = code
        self.message = message


@dataclass
class JobPage:
    final_url: str
    title: str
    text: str
    source: str  # JSON_LD | HTML_TEXT
    metadata: dict[str, Any] = field(default_factory=dict)


# --------------------------------------------------------------------- URL safety

def _check_host(host: str) -> None:
    allowed = [h.strip().lower() for h in settings.JD_IMPORT_ALLOWED_HOSTS if h.strip()]
    if allowed and not any(host == h or host.endswith("." + h) for h in allowed):
        raise JDImportError("HOST_NOT_ALLOWED", "Trang web này không nằm trong danh sách được phép lấy JD")
    try:
        infos = socket.getaddrinfo(host, None, proto=socket.IPPROTO_TCP)
    except socket.gaierror as exc:
        raise JDImportError("DNS_FAILED", "Không tìm thấy trang web. Vui lòng kiểm tra lại đường dẫn") from exc
    addresses = {info[4][0] for info in infos}
    if not addresses:
        raise JDImportError("DNS_FAILED", "Không tìm thấy trang web. Vui lòng kiểm tra lại đường dẫn")
    for address in addresses:
        ip = ipaddress.ip_address(address.split("%")[0])
        if not ip.is_global or ip.is_multicast:
            raise JDImportError("PRIVATE_ADDRESS", "Chỉ lấy được JD từ trang web công khai trên Internet")


def validate_url(url: str) -> str:
    url = (url or "").strip()
    if len(url) > 2000:
        raise JDImportError("INVALID_URL", "Đường dẫn quá dài")
    parts = urlsplit(url)
    if parts.scheme not in ("http", "https") or not parts.hostname:
        raise JDImportError("INVALID_URL", "Đường dẫn phải bắt đầu bằng http:// hoặc https://")
    if parts.username or parts.password:
        raise JDImportError("INVALID_URL", "Đường dẫn không được chứa tên đăng nhập hoặc mật khẩu")
    if parts.port not in (None, 80, 443):
        raise JDImportError("INVALID_URL", "Chỉ hỗ trợ cổng web mặc định (80/443)")
    _check_host(parts.hostname.lower())
    return url


async def fetch_page(url: str, *, transport: httpx.AsyncBaseTransport | None = None) -> tuple[str, str]:
    """Return (final_url, html), re-validating every redirect hop."""
    current = validate_url(url)
    limit = settings.JD_IMPORT_MAX_BYTES
    async with httpx.AsyncClient(timeout=settings.JD_IMPORT_TIMEOUT_SECONDS, follow_redirects=False,
                                 headers={"User-Agent": USER_AGENT, "Accept": "text/html,application/xhtml+xml"},
                                 transport=transport) as client:
        for _ in range(MAX_REDIRECTS + 1):
            try:
                async with client.stream("GET", current) as response:
                    if response.status_code in (301, 302, 303, 307, 308):
                        location = response.headers.get("location")
                        if not location:
                            raise JDImportError("FETCH_FAILED", "Trang web chuyển hướng không hợp lệ")
                        current = validate_url(urljoin(current, location))
                        continue
                    if response.status_code != 200:
                        raise JDImportError("FETCH_FAILED", f"Trang web trả về lỗi {response.status_code}")
                    content_type = response.headers.get("content-type", "").lower()
                    if "html" not in content_type:
                        raise JDImportError("NOT_HTML", "Đường dẫn không phải là một trang web (HTML)")
                    body = bytearray()
                    async for chunk in response.aiter_bytes():
                        body.extend(chunk)
                        if len(body) > limit:
                            raise JDImportError("TOO_LARGE", "Trang web quá lớn để lấy JD")
                    charset = response.charset_encoding or "utf-8"
                    try:
                        return current, bytes(body).decode(charset, errors="replace")
                    except LookupError:
                        return current, bytes(body).decode("utf-8", errors="replace")
            except httpx.TimeoutException as exc:
                raise JDImportError("TIMEOUT", "Trang web phản hồi quá chậm") from exc
            except httpx.HTTPError as exc:
                raise JDImportError("FETCH_FAILED", "Không tải được trang web") from exc
    raise JDImportError("FETCH_FAILED", "Trang web chuyển hướng quá nhiều lần")


# --------------------------------------------------------------- HTML -> text

_BLOCK_TAGS = {"p", "div", "section", "article", "br", "tr", "table", "ul", "ol", "h1", "h2", "h3", "h4", "h5", "h6",
               "header", "footer", "li", "dd", "dt", "blockquote"}
_SKIP_TAGS = {"script", "style", "noscript", "svg", "template", "iframe", "nav", "form", "button", "select"}


class _TextExtractor(HTMLParser):
    """Readable text: block tags become line breaks, list items become bullets."""

    def __init__(self, skip_layout: bool):
        super().__init__(convert_charrefs=True)
        self.parts: list[str] = []
        self.skip_depth = 0
        self.skip = _SKIP_TAGS | ({"header", "footer", "aside"} if skip_layout else set())

    def handle_starttag(self, tag, attrs):
        if tag in self.skip:
            self.skip_depth += 1
        elif not self.skip_depth:
            if tag == "li":
                self.parts.append("\n- ")
            elif tag in _BLOCK_TAGS:
                self.parts.append("\n")

    def handle_endtag(self, tag):
        if tag in self.skip:
            self.skip_depth = max(0, self.skip_depth - 1)
        elif not self.skip_depth and tag in _BLOCK_TAGS:
            self.parts.append("\n")

    def handle_data(self, data):
        if not self.skip_depth:
            # As in a browser, line breaks inside a text node are just spaces;
            # only block tags start a new line.
            self.parts.append(re.sub(r"[\r\n\t]+", " ", data))


def html_to_text(fragment: str, *, skip_layout: bool = False) -> str:
    parser = _TextExtractor(skip_layout)
    parser.feed(fragment or "")
    parser.close()
    text = "".join(parser.parts).replace("\xa0", " ").replace("​", "")
    lines = [re.sub(r"[ \t\r\f\v]+", " ", line).strip() for line in text.split("\n")]
    out: list[str] = []
    for line in lines:
        if line in ("", "-"):
            if out and out[-1] != "":
                out.append("")
            continue
        out.append(line)
    return "\n".join(out).strip()


def _json_ld_blocks(page: str) -> list[Any]:
    blocks = []
    for raw in re.findall(r"<script[^>]*type=[\"']application/ld\+json[\"'][^>]*>(.*?)</script\s*>", page, re.S | re.I):
        raw = raw.strip()
        try:
            # Many sites put raw line breaks inside JSON strings or trailing junk.
            value, _ = json.JSONDecoder(strict=False).raw_decode(raw)
        except ValueError:
            continue
        blocks.append(value)
    return blocks


def _find_job_posting(value: Any) -> dict | None:
    if isinstance(value, list):
        for item in value:
            found = _find_job_posting(item)
            if found:
                return found
    elif isinstance(value, dict):
        kind = value.get("@type")
        kinds = kind if isinstance(kind, list) else [kind]
        if "JobPosting" in kinds:
            return value
        for key in ("@graph", "mainEntity", "itemListElement"):
            found = _find_job_posting(value.get(key))
            if found:
                return found
    return None


def _location(posting: dict) -> str | None:
    places = posting.get("jobLocation")
    places = places if isinstance(places, list) else [places]
    for place in places:
        address = (place or {}).get("address") if isinstance(place, dict) else None
        if isinstance(address, dict):
            parts = [address.get(k) for k in ("streetAddress", "addressLocality", "addressRegion", "addressCountry")]
            text = ", ".join(str(p) for p in parts if p)
            if text:
                return text
        elif isinstance(address, str) and address.strip():
            return address.strip()
    return None


def extract_job_page(page: str, final_url: str) -> JobPage:
    max_chars = settings.JD_IMPORT_MAX_TEXT_CHARS
    for block in _json_ld_blocks(page):
        posting = _find_job_posting(block)
        if not posting:
            continue
        description = html_to_text(html_lib.unescape(str(posting.get("description") or "")))
        if len(description) < 80:
            continue
        identifier = posting.get("identifier")
        metadata = {
            "employment_type": posting.get("employmentType"),
            "location": _location(posting),
            "date_posted": posting.get("datePosted"),
            "valid_through": posting.get("validThrough"),
            "posting_id": identifier.get("value") if isinstance(identifier, dict) else identifier,
            "organization": (posting.get("hiringOrganization") or {}).get("name")
            if isinstance(posting.get("hiringOrganization"), dict) else None,
        }
        return JobPage(final_url=final_url, title=html_lib.unescape(str(posting.get("title") or "")).strip(),
                       text=description[:max_chars], source="JSON_LD",
                       metadata={k: v for k, v in metadata.items() if v})

    title_match = re.search(r"<meta[^>]+property=[\"']og:title[\"'][^>]+content=[\"']([^\"']+)", page, re.I) \
        or re.search(r"<title[^>]*>(.*?)</title>", page, re.S | re.I)
    title = html_lib.unescape(title_match.group(1)).strip() if title_match else ""
    main = re.search(r"<(article|main)\b.*?</\1>", page, re.S | re.I)
    body = main.group(0) if main else page
    text = html_to_text(body, skip_layout=True)
    if len(text) < 200:
        raise JDImportError("NO_CONTENT", "Không tìm thấy nội dung tuyển dụng trên trang này")
    return JobPage(final_url=final_url, title=title[:200], text=text[:max_chars], source="HTML_TEXT")
