"""In ra bảng lệch số liệu của cả 6 hàng đợi giữa Dashboard/Work Queue và trang xếp hạng.

Chỉ đọc: dùng hàm thuần của backend, không kết nối DB.

    cd backend && ./.venv/bin/python scripts/probe_queue_drift.py

Bối cảnh: doc/BAO_CAO_UX_HR_HM.md, mục UX-R1 (bảng "4 trong 6 hàng đợi lệch").
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.workspace import summarize_applications  # noqa: E402

SCREENING = ("NEW", "IN_REVIEW", "SHORTLIST")


def row(status, mstatus=None, cov=None, needs_review=False, dup=False):
    return dict(application_status=status, matching_status=mstatus, evidence_coverage=cov,
                needs_review=needs_review, duplicate=dup)


rows = [
    row("IN_REVIEW", "NEEDS_HR_VERIFICATION", 0.55, needs_review=True),
    row("SHORTLIST", "MEETS_MANDATORY", 0.92),
    row("IN_REVIEW", "NEEDS_HR_VERIFICATION", 0.61),
    row("IN_REVIEW", "POSSIBLE_MISMATCH", 0.78, dup=True),
    row("SHORTLIST", "MEETS_MANDATORY", 0.88),
    row("IN_REVIEW", "NEEDS_HR_VERIFICATION", 0.49, needs_review=True),
    row("IN_REVIEW", "MEETS_MANDATORY", 0.95),
    row("NEW", "NOT_ASSESSED", 0.0),
    row("IN_REVIEW", "NEEDS_HR_VERIFICATION", 0.66),
    row("IN_REVIEW", "POSSIBLE_MISMATCH", 0.74, dup=True),
    row("IN_REVIEW", "MEETS_MANDATORY", 0.90),
    row("NEW", "NOT_ASSESSED", 0.0),
    # 3 hồ sơ NGOÀI sàng lọc, cùng loại vấn đề: vẫn bị Dashboard đếm.
    row("REJECTED_SCREENING", "NEEDS_HR_VERIFICATION", 0.40, needs_review=True),
    row("INTERVIEW", "NEEDS_HR_VERIFICATION", 0.52, dup=True),
    row("OFFERED", "NOT_ASSESSED", 0.0),
]

dashboard = summarize_applications(rows)
ranking = summarize_applications([r for r in rows if r["application_status"] in SCREENING])

print(f"{'hàng đợi':24} {'Dashboard/WorkQueue':>20} {'trang xếp hạng':>16} {'lệch':>6}")
for key, label in [("file_review", "Cần kiểm tra file"), ("needs_verification", "Cần xác minh"),
                   ("duplicate_pending", "Cảnh báo trùng"), ("possible_mismatch", "Chưa đáp ứng"),
                   ("not_assessed", "Chưa matching"), ("total", "Tổng hồ sơ")]:
    print(f"{label:24} {dashboard[key]:>20} {ranking[key]:>16} {dashboard[key] - ranking[key]:>6}")
