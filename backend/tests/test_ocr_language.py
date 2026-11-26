"""OCR phải đọc được tiếng Việt, hoặc nói rõ là không đọc được.

Lỗi thật: `document_processor` gọi tesseract với `lang='eng'` cho mọi CV. CV scan
tiếng Việt sẽ ra chữ mất dấu ("Nguyễn Văn An" → "Nguyen Van An") hoặc rác, rồi
đem chữ sai đó đi chấm điểm. Dockerfile cũng chỉ cài `tesseract-ocr-eng`.

Test này kiểm hai việc, đều đọc từ mã nguồn nên chạy được ở job unit:
1. Ngôn ngữ OCR không được gắn cứng là 'eng'.
2. Nếu đọc tiếng Việt thì phải khai báo `vie` trong Dockerfile, nếu không sẽ
   ném lỗi lúc chạy chứ không phải lúc build.
"""
from pathlib import Path

BACKEND = Path(__file__).resolve().parents[1]
SOURCE = (BACKEND / "app" / "services" / "document_processor.py").read_text(encoding="utf-8")
DOCKERFILE = (BACKEND / "Dockerfile").read_text(encoding="utf-8")


def _ocr_calls() -> list[str]:
    """Chỉ lấy các dòng gọi tesseract, bỏ comment để không bắt nhầm chữ trong giải thích."""
    lines = []
    for line in SOURCE.splitlines():
        stripped = line.strip()
        if stripped.startswith("#"):
            continue
        if "image_to_string" in line or "image_to_data" in line:
            lines.append(line)
    return lines


def test_ocr_is_not_hardcoded_to_english():
    calls = _ocr_calls()
    assert calls, "Không tìm thấy lời gọi tesseract — code đã đổi, cập nhật test"
    offenders = [line.strip() for line in calls if "lang='eng'" in line or 'lang="eng"' in line]
    assert not offenders, (
        "OCR gắn cứng tiếng Anh — CV scan tiếng Việt sẽ mất dấu và bị chấm trên chữ sai:\n"
        + "\n".join(offenders)
    )


def test_vietnamese_ocr_language_is_installed_when_requested():
    """Dùng `vie` mà Dockerfile không cài gói tiếng Việt thì lỗi chỉ lộ lúc chạy."""
    uses_vietnamese = "vie" in SOURCE
    if not uses_vietnamese:
        return  # chưa bật thì không cần gói; test kia đã chặn việc gắn cứng 'eng'
    assert "tesseract-ocr-vie" in DOCKERFILE, (
        "Mã nguồn dùng lang='vie' nhưng Dockerfile không cài tesseract-ocr-vie"
    )
