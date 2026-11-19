#!/usr/bin/env python3
"""Sinh bộ 30 CV demo cho `doc/BO_DEMO_TUYEN_DUNG/`.

Vì sao có script này: bộ CV cũ mở đầu mỗi tệp bằng dòng "ỨNG VIÊN GIẢ <TÊN>",
và nội dung lặp lại một khuôn ("Chuyên viên IT — Công ty Mẫu 7", "Dự án phần
mềm tổng hợp"). Nhìn là biết dữ liệu bịa, nên không dùng để demo như thật được.
Script này sinh CV có họ tên đầy đủ, chức danh, kinh nghiệm theo từng công ty
với số liệu, học vấn và chứng chỉ — tức là những gì một CV thật có.

Ràng buộc: hồ sơ kỹ năng của từng người **giữ nguyên theo bảng phân bổ**, vì
kịch bản demo dựa vào việc ai đủ/thiếu bằng chứng cho vị trí nào.

Cách chạy::

    cd backend && .venv/bin/python scripts/demo_pack/generate.py

Ghi đè lên `doc/BO_DEMO_TUYEN_DUNG/02_CV/` (đúng 30 tệp, xoá tệp cũ cùng tên
khác đuôi). Không chạm vào `01_JD/` hay `03_GMAIL/`.
"""
from __future__ import annotations

import re
import sys
import unicodedata
from pathlib import Path

# Cho phép chạy trực tiếp bằng đường dẫn tệp.
sys.path.insert(0, str(Path(__file__).resolve().parents[2]))

from scripts.demo_pack.cv_data import CANDIDATES, Candidate  # noqa: E402
from scripts.demo_pack.render import render_docx, render_pdf  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
OUTPUT_DIR = REPO_ROOT / "doc" / "BO_DEMO_TUYEN_DUNG" / "02_CV"


def slug(name: str) -> str:
    """Chuyển họ tên thành phần tên tệp không dấu.

    Tên tệp cố ý **không** theo quy chuẩn đẹp: ngoài đời HR nhận đủ kiểu tên
    như "CV_final_v2 (1).pdf". Bộ demo cần đúng sự lộn xộn đó để chứng minh hệ
    thống không còn lấy tên tệp làm tên ứng viên.
    """
    # Tách dấu bằng NFD rồi bỏ dấu; đ -> d phải xử lý riêng vì đ không tách được.
    # Tên tiếng Anh có dấu gạch nối và dấu nháy, phải bỏ đi để tên tệp sạch.
    decomposed = unicodedata.normalize("NFD", name.lower())
    without_marks = "".join(ch for ch in decomposed if not unicodedata.combining(ch))
    cleaned = re.sub(r"[^a-z0-9 ]+", "", without_marks)
    return cleaned.strip().replace(" ", "_")


#: Tên tệp cố ý đa dạng: viết hoa, dấu cách, hậu tố phiên bản, có/không dấu.
#: Đây là dữ liệu đầu vào thật của bài toán "đừng lấy tên tệp làm tên người".
FILENAME_PATTERNS = (
    "CV_{n:02d}_{slug}.docx",
    "CV_{n:02d}_{slug}.pdf",
    "CV-{n:02d}-{slug}-final.docx",
    "CV_{n:02d}_{slug}_v2.docx",
    "{slug}_CV_2024.pdf",
    "CV {n:02d} {slug} (1).docx",
)


def target_filename(candidate: Candidate) -> str:
    pattern = FILENAME_PATTERNS[(candidate.number - 1) % len(FILENAME_PATTERNS)]
    return pattern.format(n=candidate.number, slug=slug(candidate.full_name))


def main() -> int:
    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    written: list[Path] = []
    for candidate in CANDIDATES:
        filename = target_filename(candidate)
        path = OUTPUT_DIR / filename
        if filename.endswith(".pdf"):
            path.write_bytes(render_pdf(candidate))
        else:
            path.write_bytes(render_docx(candidate))
        written.append(path)

    # Xoá tệp cũ không còn trong bộ mới, để thư mục đúng bằng 30 tệp.
    keep = {p.name for p in written}
    for stale in OUTPUT_DIR.iterdir():
        if stale.is_file() and stale.name not in keep and stale.suffix in {".docx", ".pdf"}:
            stale.unlink()

    print(f"Đã ghi {len(written)} CV vào {OUTPUT_DIR}")
    for candidate, path in zip(CANDIDATES, written):
        print(f"  {candidate.number:02d}  {candidate.full_name:<22} {path.name}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
