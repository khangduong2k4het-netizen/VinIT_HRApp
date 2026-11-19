"""Bounded JD previews. No writes; remote source is a single public site."""
import http.client
import io
import ipaddress
import re
import socket
import ssl
import threading
import time
import zipfile
from html.parser import HTMLParser
from urllib.parse import urlsplit

from docx import Document
from docx.table import Table
from docx.text.paragraph import Paragraph
from docx.oxml.ns import qn

MAX_FILE = 2_000_000
MAX_HTML = 2_000_000
MAX_TEXT = 100_000
HOST = 'careerportalvinuni.talent.vn'
PATH = re.compile(r'^/job/[a-z0-9-]+-\d+/?$')
_FETCH_SLOTS = threading.BoundedSemaphore(2)
# Total allowance for DNS, TCP, TLS, headers and body. Kept below the API's
# 20s response timeout so a slow source cannot hold a slot after the client gives up.
FETCH_BUDGET = 15


class ImportErrorDetail(ValueError):
    pass


def validate_source_url(url: str) -> str:
    try:
        p = urlsplit(url.strip())
        if (p.scheme != 'https' or p.hostname != HOST or p.username or p.password
                or p.port not in (None, 443) or p.query or p.fragment or not PATH.fullmatch(p.path)):
            raise ValueError
    except (ValueError, AttributeError):
        raise ImportErrorDetail('Chỉ hỗ trợ link https của trang việc làm careerportalvinuni.talent.vn.') from None
    return p.path


class JobParser(HTMLParser):
    def __init__(self):
        super().__init__(convert_charrefs=True)
        self.lines = []
        self.buf = []
        self.hidden = 0

    def flush(self):
        line = re.sub(r'\s+', ' ', ''.join(self.buf)).strip()
        if line:
            self.lines.append(line)
        self.buf = []

    def handle_starttag(self, tag, attrs):
        if tag in ('script', 'style', 'noscript', 'svg', 'iframe', 'template'):
            self.hidden += 1
        if self.hidden:
            return
        if tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li', 'br', 'form', 'tr'):
            self.flush()
        if tag == 'form':
            self.lines.append('__FORM__')
        if tag == 'li':
            self.buf.append('• ')

    def handle_endtag(self, tag):
        if tag in ('script', 'style', 'noscript', 'svg', 'iframe', 'template') and self.hidden:
            self.hidden -= 1
            return
        if not self.hidden and tag in ('h1', 'h2', 'h3', 'h4', 'h5', 'h6', 'p', 'div', 'li', 'tr'):
            self.flush()

    def handle_data(self, data):
        if not self.hidden:
            self.buf.append(data)


def extract_job_html(html: str) -> str:
    parser = JobParser()
    parser.feed(html)
    parser.flush()
    lines = parser.lines
    starts = [i for i, line in enumerate(lines) if line.strip().casefold() == 'job description']
    if len(starts) != 1:
        raise ImportErrorDetail('Không xác định được phần Job Description. Hãy dán JD thủ công.')
    start = starts[0] + 1
    ends = [i for i in range(start, len(lines)) if lines[i] == '__FORM__' or lines[i].strip().casefold() == 'application tracking form']
    if not ends:
        raise ImportErrorDetail('Không xác định được điểm kết thúc JD. Hãy dán JD thủ công.')
    result = '\n'.join(lines[start:ends[0]]).strip()
    if len(result) < 40 or len(result) > MAX_TEXT:
        raise ImportErrorDetail('Nội dung JD trống hoặc quá dài. Hãy dán JD thủ công.')
    return result


def fetch_job(url: str) -> str:
    path = validate_source_url(url)
    if not _FETCH_SLOTS.acquire(blocking=False):
        raise ImportErrorDetail('Đang có yêu cầu nhập JD; hãy thử lại sau.')
    try:
        return _fetch_job(path)
    finally:
        _FETCH_SLOTS.release()


def _fetch_job(path: str) -> str:
    # Resolve once, reject all non-global answers, connect to that exact address
    # and retain the host for TLS certificate verification/SNI. No redirects/proxy.
    # Every phase (DNS, TCP, TLS, headers, body) must fit in FETCH_BUDGET, so a
    # stuck resolver/header cannot occupy one of the two fetch slots for long.
    budget = time.monotonic() + FETCH_BUDGET

    def remaining():
        left = budget - time.monotonic()
        if left <= 0:
            raise TimeoutError
        return left

    try:
        answers = socket.getaddrinfo(HOST, 443, type=socket.SOCK_STREAM)
        addresses = list(dict.fromkeys(x[4][0] for x in answers))
        if not addresses or any(not ipaddress.ip_address(ip).is_global for ip in addresses):
            raise ImportErrorDetail('Không thể kết nối an toàn tới nguồn JD.')
        ip = addresses[0]
        remaining()

        class PinnedHTTPS(http.client.HTTPSConnection):
            def connect(self):
                sock = socket.create_connection((ip, 443), timeout=min(8, remaining()))
                try:
                    sock.settimeout(min(8, remaining()))
                    self.sock = ssl.create_default_context().wrap_socket(sock, server_hostname=HOST)
                except Exception:
                    sock.close()
                    raise

        conn = PinnedHTTPS(HOST, timeout=min(8, remaining()))
        try:
            conn.request('GET', path, headers={'Host': HOST, 'Accept': 'text/html', 'Accept-Encoding': 'identity', 'User-Agent': 'HRA-JD-Preview/1.0'})
            response = conn.getresponse()
            if response.status != 200 or response.getheader('Content-Type', '').split(';')[0].strip().lower() != 'text/html':
                raise ImportErrorDetail('Không đọc được trang JD. Hãy dán nội dung thủ công.')
            if response.getheader('Content-Encoding', 'identity').lower() not in ('', 'identity'):
                raise ImportErrorDetail('Trang JD có định dạng không hỗ trợ.')
            chunks = bytearray()
            while len(chunks) <= MAX_HTML:
                if response.isclosed():
                    break
                response.fp.raw._sock.settimeout(min(8, remaining()))
                chunk = response.read1(min(65536, MAX_HTML + 1 - len(chunks)))
                if not chunk:
                    break
                chunks.extend(chunk)
            if len(chunks) > MAX_HTML:
                raise ImportErrorDetail('Trang JD quá lớn.')
            html = bytes(chunks).decode('utf-8', errors='strict')
        finally:
            conn.close()
    except ImportErrorDetail:
        raise
    except TimeoutError:
        raise
    except (OSError, ValueError, UnicodeError, AttributeError, http.client.HTTPException):
        raise ImportErrorDetail('Không thể đọc trang JD. Hãy thử lại hoặc dán thủ công.') from None
    return extract_job_html(html)


def extract_file(data: bytes, filename: str) -> str:
    name = filename.lower()
    if not data or len(data) > MAX_FILE:
        raise ImportErrorDetail('Tệp rỗng hoặc lớn hơn 2 MB.')
    if name.endswith('.txt'):
        try:
            value = data.decode('utf-8-sig')
        except UnicodeDecodeError:
            raise ImportErrorDetail('Tệp TXT cần được lưu bằng UTF-8.') from None
        if '\x00' in value:
            raise ImportErrorDetail('Tệp TXT không hợp lệ.')
    elif name.endswith('.docx'):
        try:
            with zipfile.ZipFile(io.BytesIO(data)) as z:
                infos = z.infolist()
                names = set(z.namelist())
                if (len(infos) > 2000 or sum(i.file_size for i in infos) > 20_000_000
                        or not {'[Content_Types].xml', 'word/document.xml'} <= names
                        or any('vbaproject' in n.lower() for n in names)):
                    raise ValueError
            doc = Document(io.BytesIO(data))
            lines = []
            for child in doc.element.body.iterchildren():
                if child.tag == qn('w:p'):
                    lines.append(Paragraph(child, doc).text)
                elif child.tag == qn('w:tbl'):
                    for row in Table(child, doc).rows:
                        lines.append(' | '.join(cell.text.replace('\n', ' ') for cell in row.cells))
            value = '\n'.join(line for line in lines if line.strip())
        except Exception:
            raise ImportErrorDetail('Không đọc được DOCX; hãy kiểm tra tệp hoặc dán JD.') from None
    else:
        raise ImportErrorDetail('Chỉ hỗ trợ .docx và .txt; hãy chuyển .doc sang .docx.')
    value = value.strip()
    if not value or len(value) > MAX_TEXT:
        raise ImportErrorDetail('Nội dung JD trống hoặc quá dài (tối đa 100.000 ký tự).')
    return value
