import os
from typing import Tuple
from enum import Enum
from pypdf import PdfReader
from pdf2image import convert_from_bytes
import pytesseract
from docx import Document
from docx.opc.constants import RELATIONSHIP_TYPE as RT
from docx.table import Table
from docx.text.paragraph import Paragraph
from PIL import Image, ImageFilter, ImageOps, UnidentifiedImageError
import io
import zipfile
import numpy as np
from app.core.config import settings
from app.core.logging import get_logger
from app.core.exceptions import FileValidationError

logger = get_logger(__name__)

DOCX_MIME = "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
IMAGE_MIME_TYPES = {"image/jpeg", "image/png"}
# Extension stored for each accepted MIME type (upload storage path).
MIME_EXTENSIONS = {
    "application/pdf": ".pdf",
    DOCX_MIME: ".docx",
    "image/jpeg": ".jpg",
    "image/png": ".png",
}
_A4_SHORT_SIDE_INCHES = 210 / 25.4
# Images are normalised to this short side before measuring sharpness so the
# score does not depend on the original pixel count.
_SHARPNESS_SHORT_SIDE = 1000
_DESKEW_MAX_DEGREES = 10.0
_DESKEW_STEP_DEGREES = 0.5


class DocumentType(str, Enum):
    PDF_TEXT = "PDF_TEXT"
    PDF_SCANNED = "PDF_SCANNED"
    DOCX = "DOCX"
    IMAGE = "IMAGE"
    UNSUPPORTED = "UNSUPPORTED"


class DocumentQualityError(FileValidationError):
    """The file is valid but too poor to read reliably (F2.06).

    The worker moves such documents to the HR manual queue
    (NEEDS_HR_REVIEW) with ``code`` as the processing error code. The message
    is safe to show: it never contains CV text.
    """

    MESSAGES = {
        "IMAGE_LOW_RESOLUTION": "Ảnh có độ phân giải thấp (dưới {min_dpi} DPI); HR cần kiểm tra thủ công hoặc yêu cầu bản rõ hơn",
        "IMAGE_BLURRY": "Ảnh bị mờ, không đủ rõ để nhận dạng chữ; HR cần kiểm tra thủ công",
        "IMAGE_NO_TEXT": "Không nhận dạng được đủ chữ trong ảnh; HR cần kiểm tra thủ công",
        "DOCX_IMAGES_LOW_QUALITY": "DOCX chủ yếu là ảnh và ảnh không đủ rõ để nhận dạng; HR cần kiểm tra thủ công",
        "PDF_TOO_MANY_PAGES": "PDF có quá nhiều trang (tối đa {max_pages} trang); HR cần kiểm tra thủ công",
    }

    def __init__(self, code: str, quality: dict | None = None):
        template = self.MESSAGES.get(code, "Tài liệu không đủ chất lượng để xử lý tự động; HR cần kiểm tra thủ công")
        super().__init__(template.format(min_dpi=settings.OCR_MIN_DPI, max_pages=settings.MAX_DOCUMENT_PAGES))
        self.code = code
        self.quality = quality or {}


def _image_mime(file_content: bytes, extension: str) -> str | None:
    if extension in (".jpg", ".jpeg") and file_content.startswith(b"\xff\xd8\xff"):
        return "image/jpeg"
    if extension == ".png" and file_content.startswith(b"\x89PNG\r\n\x1a\n"):
        return "image/png"
    return None


def _open_image(data: bytes) -> Image.Image:
    """Open an image after checking its declared size against the pixel cap.

    ``Image.open`` reads only the header, so the size check happens before any
    pixel data is decoded (decompression-bomb guard).
    """
    try:
        image = Image.open(io.BytesIO(data))
    except (UnidentifiedImageError, OSError, ValueError) as exc:
        raise FileValidationError("Không đọc được ảnh") from exc
    width, height = image.size
    if width <= 0 or height <= 0 or width * height > settings.OCR_MAX_IMAGE_PIXELS:
        raise FileValidationError("Ảnh quá lớn hoặc kích thước không hợp lệ")
    try:
        image.load()
    except (OSError, ValueError, Image.DecompressionBombError) as exc:
        raise FileValidationError("Không đọc được ảnh") from exc
    return image


def _to_grayscale(image: Image.Image) -> Image.Image:
    image = ImageOps.exif_transpose(image)
    if image.mode in ("RGBA", "LA") or (image.mode == "P" and "transparency" in image.info):
        rgba = image.convert("RGBA")
        background = Image.new("RGBA", rgba.size, (255, 255, 255, 255))
        image = Image.alpha_composite(background, rgba)
    return image.convert("L")


def estimate_dpi(image: Image.Image) -> float:
    """Effective resolution assuming the image is one A4 CV page.

    DPI metadata is ignored on purpose: screenshots and exports often carry
    a default 72/96 DPI regardless of how many pixels the page really has.
    """
    return float(round(min(image.size) / _A4_SHORT_SIDE_INCHES))


def _resize_short_side(gray: Image.Image, short_side: int) -> Image.Image:
    width, height = gray.size
    scale = short_side / float(min(width, height))
    if abs(scale - 1.0) < 1e-3:
        return gray
    return gray.resize((max(1, round(width * scale)), max(1, round(height * scale))), Image.LANCZOS)


def sharpness_score(gray: Image.Image) -> float:
    """Variance of the 4-neighbour Laplacian on a size-normalised image."""
    pixels = np.asarray(_resize_short_side(gray, _SHARPNESS_SHORT_SIDE), dtype=np.float64)
    if pixels.shape[0] < 3 or pixels.shape[1] < 3:
        return 0.0
    laplacian = (
        pixels[:-2, 1:-1] + pixels[2:, 1:-1] + pixels[1:-1, :-2] + pixels[1:-1, 2:]
        - 4.0 * pixels[1:-1, 1:-1]
    )
    return round(float(laplacian.var()), 2)


def estimate_skew_angle(gray: Image.Image) -> float:
    """Small-angle skew estimate by maximising horizontal projection variance."""
    small = _resize_short_side(gray, 800)
    pixels = np.asarray(small, dtype=np.float64)
    threshold = pixels.mean() - 0.5 * pixels.std()
    ink = Image.fromarray(((pixels < threshold) * 255).astype(np.uint8))
    best_angle, best_score = 0.0, -1.0
    steps = int(_DESKEW_MAX_DEGREES / _DESKEW_STEP_DEGREES)
    for index in range(-steps, steps + 1):
        angle = index * _DESKEW_STEP_DEGREES
        rotated = np.asarray(ink.rotate(angle, resample=Image.NEAREST, expand=False, fillcolor=0), dtype=np.float64)
        score = float(rotated.sum(axis=1).var())
        if score > best_score + 1e-6:
            best_angle, best_score = angle, score
    return best_angle


def _orientation_rotation(gray: Image.Image) -> int:
    """90/180/270-degree page rotation reported by Tesseract OSD, else 0."""
    try:
        osd = pytesseract.image_to_osd(gray, output_type=pytesseract.Output.DICT)
        rotate = int(osd.get("rotate", 0) or 0)
        confidence = float(osd.get("orientation_conf", 0) or 0)
    except Exception:
        # OSD fails on images with little text; keep the original orientation.
        return 0
    return rotate if rotate in (90, 180, 270) and confidence >= 2.0 else 0


def prepare_image_for_ocr(image: Image.Image) -> Tuple[Image.Image, dict]:
    """Grayscale, orientation, deskew, contrast and denoise before OCR.

    Returns the processed image and numeric quality metrics only (no text).
    """
    gray = _to_grayscale(image)
    quality = {
        "width": gray.size[0],
        "height": gray.size[1],
        "estimated_dpi": estimate_dpi(gray),
        "sharpness": sharpness_score(gray),
    }
    rotation = _orientation_rotation(gray)
    if rotation:
        # OSD "rotate" is the clockwise rotation needed; PIL rotates counter-clockwise.
        gray = gray.rotate(-rotation, expand=True, fillcolor=255)
    skew = estimate_skew_angle(gray)
    if abs(skew) >= _DESKEW_STEP_DEGREES:
        gray = gray.rotate(skew, resample=Image.BICUBIC, expand=True, fillcolor=255)
    gray = ImageOps.autocontrast(gray, cutoff=1)
    gray = gray.filter(ImageFilter.MedianFilter(3))
    # Tesseract works best near 300 DPI; upscale moderately low-resolution images.
    dpi = quality["estimated_dpi"]
    if settings.OCR_MIN_DPI <= dpi < 300:
        factor = min(2.0, 300.0 / dpi)
        gray = gray.resize((round(gray.size[0] * factor), round(gray.size[1] * factor)), Image.LANCZOS)
    quality.update({"orientation_rotation": rotation, "deskew_degrees": skew})
    return gray, quality


def quality_issue(quality: dict) -> str | None:
    if quality["estimated_dpi"] < settings.OCR_MIN_DPI:
        return "IMAGE_LOW_RESOLUTION"
    if quality["sharpness"] < settings.OCR_MIN_SHARPNESS:
        return "IMAGE_BLURRY"
    return None


def _ocr(image: Image.Image) -> Tuple[str, dict]:
    """OCR text plus word confidences only (raw diagnostic text is dropped)."""
    lang = settings.OCR_LANGUAGES
    text = pytesseract.image_to_string(image, lang=lang)
    data = pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
    return text.strip(), {"conf": list(data.get("conf", []))}


_TINY_TEXT_PT = 1.5          # below this a glyph is unreadable to a person
_WHITE = 0.97                # fill colour this close to white
_MIN_HIDDEN_FRAGMENT = 3     # shorter pieces are spacing/kerning noise


def _is_white(args: list, op: bytes) -> bool:
    try:
        values = [float(a) for a in args]
    except (TypeError, ValueError):
        return False
    if op in (b"g", b"sc", b"scn") and len(values) == 1 or op == b"rg" or (op in (b"sc", b"scn") and len(values) == 3):
        return bool(values) and all(v >= _WHITE for v in values)
    if op == b"k" or (op in (b"sc", b"scn") and len(values) == 4):
        return all(v <= 1 - _WHITE for v in values)
    return False


def extract_visible_pdf_text(page) -> Tuple[str, dict]:
    """Text a person can see on the page, plus counts of hidden text.

    Keyword stuffing hides text from the reader but not from a text extractor:
    render mode 3/7 (invisible) or a microscopic font. Such text is removed so
    it can neither reach the model nor become "evidence". White text is only
    counted: many CV templates print white text on a dark sidebar, and
    without the background we cannot tell the two apart.
    """
    state = {"tr": 0, "white": False}
    stack: list[dict] = []
    hidden: list[str] = []
    stats = {"invisible_chars": 0, "tiny_chars": 0, "white_chars": 0}

    def before(op, args, cm, tm):
        if op == b"q":
            stack.append(dict(state))
        elif op == b"Q" and stack:
            state.update(stack.pop())
        elif op == b"Tr" and args:
            try:
                state["tr"] = int(args[0])
            except (TypeError, ValueError):
                pass
        elif op in (b"g", b"rg", b"k", b"sc", b"scn"):
            state["white"] = _is_white(list(args), op)

    def on_text(text, cm, tm, font_dict, font_size):
        piece = (text or "").strip()
        if not piece:
            return
        try:
            scale = abs(float(tm[3]) * float(cm[3])) or abs(float(tm[0]) * float(cm[0]))
            size = abs(float(font_size or 0)) * (scale or 1.0)
        except (TypeError, ValueError, IndexError):
            size = 12.0
        if state["tr"] in (3, 7):
            stats["invisible_chars"] += len(piece)
            hidden.append(piece)
        elif 0 < size < _TINY_TEXT_PT:
            stats["tiny_chars"] += len(piece)
            hidden.append(piece)
        elif state["white"]:
            stats["white_chars"] += len(piece)

    text = page.extract_text(visitor_operand_before=before, visitor_text=on_text) or ""
    for piece in sorted(set(hidden), key=len, reverse=True):
        if len(piece) >= _MIN_HIDDEN_FRAGMENT:
            text = text.replace(piece, " ")
    return text, stats


def _paragraph_text(paragraph: Paragraph) -> str:
    return paragraph.text.strip()


def _table_lines(table: Table) -> list[str]:
    """One line per table row; merged cells are emitted once."""
    lines = []
    for row in table.rows:
        cells, seen = [], set()
        for cell in row.cells:
            if id(cell._tc) in seen:
                continue
            seen.add(id(cell._tc))
            parts = [p.text.strip() for p in cell.paragraphs if p.text.strip()]
            for nested in cell.tables:
                parts.extend(_table_lines(nested))
            if parts:
                cells.append(" ".join(parts))
        if cells:
            lines.append(" | ".join(cells))
    return lines


class DocumentProcessor:
    """Handles CV document parsing, text extraction and OCR.

    Supported inputs: text PDF, scanned PDF, DOCX (paragraphs, tables and
    embedded images) and standalone JPG/JPEG/PNG images (F2.06).
    """

    SUPPORTED_MIME_TYPES = {"application/pdf", DOCX_MIME, *IMAGE_MIME_TYPES}
    MAX_FILE_SIZE = settings.MAX_FILE_SIZE_BYTES

    async def validate_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Validate bytes rather than trusting a browser-supplied MIME type.

        DOCX is a ZIP container; checking the required entries also rejects ordinary
        ZIP files. Limit its expanded size before handing it to a document parser.
        Images are checked by magic bytes and their declared pixel size.
        """
        if not file_content or len(file_content) > self.MAX_FILE_SIZE:
            raise FileValidationError(f"File {filename} is empty or exceeds the size limit")

        extension = os.path.splitext(filename or "")[1].lower()
        if extension == ".pdf" and file_content.lstrip().startswith(b"%PDF-"):
            return "application/pdf"
        if extension == ".docx" and zipfile.is_zipfile(io.BytesIO(file_content)):
            try:
                with zipfile.ZipFile(io.BytesIO(file_content)) as archive:
                    names = set(archive.namelist())
                    if {"[Content_Types].xml", "word/document.xml"}.issubset(names):
                        if sum(item.file_size for item in archive.infolist()) <= 100_000_000:
                            return DOCX_MIME
            except (zipfile.BadZipFile, OSError):
                pass
        image_mime = _image_mime(file_content, extension)
        if image_mime:
            try:
                header = Image.open(io.BytesIO(file_content))
                width, height = header.size
            except (UnidentifiedImageError, OSError, ValueError):
                raise FileValidationError(f"File {filename} is not a valid image") from None
            if width <= 0 or height <= 0 or width * height > settings.OCR_MAX_IMAGE_PIXELS:
                raise FileValidationError(f"File {filename} exceeds the image pixel limit")
            return image_mime
        raise FileValidationError(f"File {filename} is not a valid PDF, DOCX, JPG or PNG")

    async def detect_document_type(self, file_content: bytes, content_type: str) -> DocumentType:
        """Detect if PDF is text-based or scanned, or DOCX / image"""
        if content_type == DOCX_MIME:
            return DocumentType.DOCX
        if content_type in IMAGE_MIME_TYPES:
            return DocumentType.IMAGE

        # Try reading PDF text directly
        try:
            pdf_file = io.BytesIO(file_content)
            reader = PdfReader(pdf_file)
            if reader.is_encrypted:
                return DocumentType.UNSUPPORTED

            text_content = ""
            for page in reader.pages[:2]:  # Check first 2 pages
                text = page.extract_text()
                if text and len(text.strip()) > 50:
                    text_content += text

            if len(text_content.strip()) > 100:
                return DocumentType.PDF_TEXT
            return DocumentType.PDF_SCANNED
        except Exception as e:
            logger.warning("Error detecting PDF type, assuming scanned or unsupported", error_type=type(e).__name__)
            return DocumentType.PDF_SCANNED

    async def extract_text_from_pdf_text(self, file_content: bytes) -> Tuple[str, list]:
        """Extract text directly from PDF with embedded text"""
        pdf_file = io.BytesIO(file_content)
        reader = PdfReader(pdf_file)
        if len(reader.pages) > settings.MAX_DOCUMENT_PAGES:
            raise DocumentQualityError("PDF_TOO_MANY_PAGES", {"pages": len(reader.pages)})
        pages_text = []
        hidden = {"invisible_chars": 0, "tiny_chars": 0, "white_chars": 0}

        for page_num, page in enumerate(reader.pages, start=1):
            text, stats = extract_visible_pdf_text(page)
            for key, value in stats.items():
                hidden[key] += value
            pages_text.append({
                "page_number": page_num,
                "content": text.strip()
            })
        if any(hidden.values()):
            # Counts only, never the hidden words; stored with the processing run.
            pages_text[0]["pdf_hidden_text"] = hidden
            logger.warning("PDF contains hidden or white text", **hidden)

        full_text = "\n\n".join([f"--- Page {p['page_number']} ---\n{p['content']}" for p in pages_text])
        return full_text, pages_text

    async def extract_text_from_pdf_scan(self, file_content: bytes) -> Tuple[str, list]:
        """Run OCR on scanned PDF to extract text"""
        pages_text = []
        try:
            page_count = len(PdfReader(io.BytesIO(file_content)).pages)
        except Exception:
            page_count = 0
        if page_count > settings.MAX_DOCUMENT_PAGES:
            raise DocumentQualityError("PDF_TOO_MANY_PAGES", {"pages": page_count})

        try:
            # From memory: an open NamedTemporaryFile cannot be reopened by
            # poppler on Windows, and last_page bounds the work either way.
            images = convert_from_bytes(file_content, dpi=300, last_page=settings.MAX_DOCUMENT_PAGES)
        except Exception as e:
            logger.error("Failed to convert PDF to images for OCR", error_type=type(e).__name__)
            raise FileValidationError("Could not process scanned PDF file")

        for page_num, image in enumerate(images, start=1):
            text, confidence = _ocr(image)
            pages_text.append({
                "page_number": page_num,
                "content": text,
                "ocr_confidence": confidence,
            })

        full_text = "\n\n".join([f"--- Page {p['page_number']} ---\n{p['content']}" for p in pages_text])
        return full_text, pages_text

    async def extract_text_from_image(self, file_content: bytes) -> Tuple[str, list]:
        """F2.06: OCR one standalone JPG/PNG image after preprocessing.

        Low resolution or blur raises DocumentQualityError before OCR so the
        CV goes to the manual queue instead of producing unreliable text.
        """
        image = _open_image(file_content)
        processed, quality = prepare_image_for_ocr(image)
        issue = quality_issue(quality)
        if issue:
            raise DocumentQualityError(issue, quality)
        text, confidence = _ocr(processed)
        if len(text) < 50:
            raise DocumentQualityError("IMAGE_NO_TEXT", quality)
        quality["source"] = "IMAGE"
        page = {"page_number": 1, "content": text, "ocr_confidence": confidence, "image_quality": quality}
        return f"--- Page 1 ---\n{text}", [page]

    def _docx_embedded_images(self, doc) -> list[bytes]:
        """Image blobs referenced from the document body, in reading order."""
        rels = doc.part.rels
        blobs, seen = [], set()
        for rel_id in doc.element.body.xpath(".//a:blip/@r:embed"):
            if rel_id in seen or rel_id not in rels:
                continue
            seen.add(rel_id)
            rel = rels[rel_id]
            if rel.reltype != RT.IMAGE or rel.is_external:
                continue
            blobs.append(rel.target_part.blob)
        return blobs

    async def extract_text_from_docx(self, file_content: bytes) -> Tuple[str, list]:
        """Extract DOCX paragraphs and tables in body order, then OCR embedded images.

        Page 1 holds the document text. Each embedded image that is large and
        clear enough becomes one extra page so evidence can point to it.
        """
        docx_file = io.BytesIO(file_content)
        doc = Document(docx_file)

        lines: list[str] = []
        for child in doc.element.body.iterchildren():
            tag = child.tag.rsplit("}", 1)[-1]
            if tag == "p":
                value = _paragraph_text(Paragraph(child, doc))
                if value:
                    lines.append(value)
            elif tag == "tbl":
                lines.extend(_table_lines(Table(child, doc)))
        body_text = "\n".join(lines)
        pages_text = [{"page_number": 1, "content": body_text}]

        stats = {"embedded_images": 0, "ocr_images": 0, "skipped_small": 0,
                 "skipped_low_quality": 0, "skipped_unreadable": 0, "skipped_over_limit": 0}
        for blob in self._docx_embedded_images(doc):
            stats["embedded_images"] += 1
            if stats["ocr_images"] >= settings.OCR_DOCX_MAX_IMAGES:
                stats["skipped_over_limit"] += 1
                continue
            try:
                image = _open_image(blob)
            except FileValidationError:
                # EMF/WMF/SVG or corrupt images: not OCR-able here.
                stats["skipped_unreadable"] += 1
                continue
            if image.size[0] * image.size[1] < settings.OCR_DOCX_MIN_IMAGE_PIXELS:
                stats["skipped_small"] += 1
                continue
            processed, quality = prepare_image_for_ocr(image)
            if quality_issue(quality):
                stats["skipped_low_quality"] += 1
                continue
            text, confidence = _ocr(processed)
            if not text:
                continue
            stats["ocr_images"] += 1
            quality["source"] = "DOCX_EMBEDDED_IMAGE"
            pages_text.append({"page_number": len(pages_text) + 1, "content": text,
                               "ocr_confidence": confidence, "image_quality": quality})

        text_length = sum(len((page.get("content") or "").strip()) for page in pages_text)
        if text_length < 50 and stats["skipped_low_quality"]:
            raise DocumentQualityError("DOCX_IMAGES_LOW_QUALITY", stats)
        pages_text[0]["docx_stats"] = stats

        if len(pages_text) == 1:
            return body_text, pages_text
        full_text = "\n\n".join(
            [body_text] + [f"--- Embedded image {p['page_number'] - 1} ---\n{p['content']}" for p in pages_text[1:]]
        )
        return full_text, pages_text

    async def process_document(self, file_content: bytes, filename: str, content_type: str) -> Tuple[str, list, DocumentType]:
        """Process document: validate, detect type, extract text"""
        detected_mime = await self.validate_file(file_content, filename, content_type)
        doc_type = await self.detect_document_type(file_content, detected_mime or content_type)

        if doc_type == DocumentType.UNSUPPORTED:
            raise FileValidationError(f"File {filename} is encrypted or unsupported")

        if doc_type == DocumentType.PDF_TEXT:
            full_text, pages = await self.extract_text_from_pdf_text(file_content)
        elif doc_type == DocumentType.PDF_SCANNED:
            full_text, pages = await self.extract_text_from_pdf_scan(file_content)
        elif doc_type == DocumentType.DOCX:
            full_text, pages = await self.extract_text_from_docx(file_content)
        elif doc_type == DocumentType.IMAGE:
            full_text, pages = await self.extract_text_from_image(file_content)
        else:
            raise FileValidationError("Unsupported document type")

        # Page markers are metadata, not CV content: a multi-page blank scan
        # must never pass the extraction check merely because of its labels.
        text_length = sum(len((page.get("content") or "").strip()) for page in pages)
        if text_length < 50:
            raise FileValidationError(
                f"Could not extract sufficient text from {filename}; document may be too low quality or image-only"
            )

        logger.info(
            "Document processed successfully",
            doc_type=doc_type.value,
            text_length=text_length,
            pages=len(pages)
        )

        return full_text, pages, doc_type


def document_quality_summary(pages: list) -> dict | None:
    """Numeric-only OCR/image diagnostics to persist with a processing run."""
    images = [page["image_quality"] for page in pages if isinstance(page.get("image_quality"), dict)]
    docx_stats = next((page["docx_stats"] for page in pages if isinstance(page.get("docx_stats"), dict)), None)
    hidden = next((page["pdf_hidden_text"] for page in pages if isinstance(page.get("pdf_hidden_text"), dict)), None)
    if not images and not docx_stats and not hidden:
        return None
    summary: dict = {"images": [
        {key: value for key, value in image.items()
         if key in ("source", "width", "height", "estimated_dpi", "sharpness", "orientation_rotation", "deskew_degrees")}
        for image in images
    ]}
    if docx_stats:
        summary["docx"] = dict(docx_stats)
    if hidden:
        summary["pdf_hidden_text"] = dict(hidden)
    return summary


# Singleton instance
document_processor = DocumentProcessor()
