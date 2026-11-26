import os
import tempfile
from typing import Tuple, Optional
from enum import Enum
from pypdf import PdfReader
from pdf2image import convert_from_path
import pytesseract
from docx import Document
import io
import zipfile
from app.core.config import settings


def _ocr_languages() -> str:
    """Ngôn ngữ cho tesseract: tiếng Việt + tiếng Anh, lùi về tiếng Anh nếu thiếu gói.

    Trước đây gắn cứng `eng`, nên CV scan tiếng Việt ra chữ mất dấu — và chữ sai
    đó vẫn được đem đi chấm điểm, không có gì báo là đã sai.

    Không hard-code `vie` được: máy chưa cài `tesseract-ocr-vie` sẽ ném
    TesseractError lúc chạy, tức là hỏng cả luồng nhận CV thay vì chỉ giảm chất
    lượng. Vì vậy hỏi tesseract xem có gói nào rồi mới chọn, và chỉ tính một lần.
    """
    global _OCR_LANG_CACHE
    if _OCR_LANG_CACHE is not None:
        return _OCR_LANG_CACHE
    try:
        available = set(pytesseract.get_languages(config=""))
    except Exception:
        available = set()
    if "vie" in available:
        _OCR_LANG_CACHE = "vie+eng"
    else:
        _OCR_LANG_CACHE = "eng"
    return _OCR_LANG_CACHE


_OCR_LANG_CACHE: Optional[str] = None
from app.core.logging import get_logger
from app.core.exceptions import FileValidationError

logger = get_logger(__name__)


class DocumentType(str, Enum):
    PDF_TEXT = "PDF_TEXT"
    PDF_SCANNED = "PDF_SCANNED"
    DOCX = "DOCX"
    UNSUPPORTED = "UNSUPPORTED"


class DocumentProcessor:
    """Handles CV document parsing, text extraction, and OCR for scanned PDFs"""

    SUPPORTED_MIME_TYPES = {
        "application/pdf",
        "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
    }
    MAX_FILE_SIZE = settings.MAX_FILE_SIZE_BYTES

    async def validate_file(self, file_content: bytes, filename: str, content_type: str) -> str:
        """Validate bytes rather than trusting a browser-supplied MIME type.

        DOCX is a ZIP container; checking the required entries also rejects ordinary
        ZIP files. Limit its expanded size before handing it to a document parser.
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
                            return "application/vnd.openxmlformats-officedocument.wordprocessingml.document"
            except (zipfile.BadZipFile, OSError):
                pass
        raise FileValidationError(f"File {filename} is not a valid PDF or DOCX")

    async def detect_document_type(self, file_content: bytes, content_type: str) -> DocumentType:
        """Detect if PDF is text-based or scanned, or DOCX"""
        if content_type == "application/vnd.openxmlformats-officedocument.wordprocessingml.document":
            return DocumentType.DOCX

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
        pages_text = []

        for page_num, page in enumerate(reader.pages, start=1):
            text = page.extract_text() or ""
            pages_text.append({
                "page_number": page_num,
                "content": text.strip()
            })

        full_text = "\n\n".join([f"--- Page {p['page_number']} ---\n{p['content']}" for p in pages_text])
        return full_text, pages_text

    async def extract_text_from_pdf_scan(self, file_content: bytes) -> Tuple[str, list]:
        """Run OCR on scanned PDF to extract text"""
        pages_text = []

        with tempfile.NamedTemporaryFile(suffix=".pdf", delete=True) as temp_pdf:
            temp_pdf.write(file_content)
            temp_pdf.flush()

            try:
                images = convert_from_path(temp_pdf.name, dpi=300)
            except Exception as e:
                logger.error("Failed to convert PDF to images for OCR", error_type=type(e).__name__)
                raise FileValidationError("Could not process scanned PDF file")

            for page_num, image in enumerate(images, start=1):
                lang = _ocr_languages()
                text = pytesseract.image_to_string(image, lang=lang)
                pages_text.append({
                    "page_number": page_num,
                    "content": text.strip(),
                    "ocr_language": lang,
                    "ocr_confidence": pytesseract.image_to_data(image, lang=lang, output_type=pytesseract.Output.DICT)
                })

        full_text = "\n\n".join([f"--- Page {p['page_number']} ---\n{p['content']}" for p in pages_text])
        return full_text, pages_text

    async def extract_text_from_docx(self, file_content: bytes) -> Tuple[str, list]:
        """Extract text from DOCX file"""
        docx_file = io.BytesIO(file_content)
        doc = Document(docx_file)

        # DOCX doesn't have fixed page numbers in simple extraction; treat as single section for MVP
        full_text = "\n".join([para.text for para in doc.paragraphs if para.text.strip()])
        pages_text = [{
            "page_number": 1,
            "content": full_text
        }]

        return full_text, pages_text

    async def process_document(self, file_content: bytes, filename: str, content_type: str) -> Tuple[str, list, DocumentType]:
        """Process document: validate, detect type, extract text"""
        await self.validate_file(file_content, filename, content_type)
        doc_type = await self.detect_document_type(file_content, content_type)

        if doc_type == DocumentType.UNSUPPORTED:
            raise FileValidationError(f"File {filename} is encrypted or unsupported")

        if doc_type == DocumentType.PDF_TEXT:
            full_text, pages = await self.extract_text_from_pdf_text(file_content)
        elif doc_type == DocumentType.PDF_SCANNED:
            full_text, pages = await self.extract_text_from_pdf_scan(file_content)
        elif doc_type == DocumentType.DOCX:
            full_text, pages = await self.extract_text_from_docx(file_content)
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


# Singleton instance
document_processor = DocumentProcessor()
