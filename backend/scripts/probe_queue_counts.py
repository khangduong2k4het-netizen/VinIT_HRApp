"""In ra bảng đối chiếu số "cần xác minh" giữa Dashboard, API ranking và chip FE.

Chỉ đọc: dùng hàm thuần của backend, không kết nối DB.

    cd backend && ./.venv/bin/python scripts/probe_queue_counts.py

Bối cảnh: doc/BAO_CAO_UX_HR_HM.md, mục UX-R1.
"""
import sys
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from app.services.workspace import summarize_applications  # noqa: E402

SCREENING = ("NEW", "IN_REVIEW", "SHORTLIST")

# 15 hồ sơ: 12 đang sàng lọc + 3 đã qua/đã loại (REJECTED_SCREENING, INTERVIEW, OFFERED).
rows = [
    dict(application_status="IN_REVIEW", matching_status="NEEDS_HR_VERIFICATION", evidence_coverage=0.55),
    dict(application_status="SHORTLIST", matching_status="MEETS_MANDATORY", evidence_coverage=0.92),
    dict(application_status="IN_REVIEW", matching_status="NEEDS_HR_VERIFICATION", evidence_coverage=0.61),
    dict(application_status="IN_REVIEW", matching_status="POSSIBLE_MISMATCH", evidence_coverage=0.78),
    dict(application_status="SHORTLIST", matching_status="MEETS_MANDATORY", evidence_coverage=0.88),
    dict(application_status="IN_REVIEW", matching_status="NEEDS_HR_VERIFICATION", evidence_coverage=0.49),
    dict(application_status="IN_REVIEW", matching_status="MEETS_MANDATORY", evidence_coverage=0.95),
    dict(application_status="NEW", matching_status="NOT_ASSESSED", evidence_coverage=0.0),
    dict(application_status="IN_REVIEW", matching_status="NEEDS_HR_VERIFICATION", evidence_coverage=0.66),
    dict(application_status="IN_REVIEW", matching_status="POSSIBLE_MISMATCH", evidence_coverage=0.74),
    dict(application_status="IN_REVIEW", matching_status="MEETS_MANDATORY", evidence_coverage=0.90),
    dict(application_status="NEW", matching_status="NOT_ASSESSED", evidence_coverage=0.0),
    dict(application_status="REJECTED_SCREENING", matching_status="NEEDS_HR_VERIFICATION", evidence_coverage=0.40),
    dict(application_status="INTERVIEW", matching_status="NEEDS_HR_VERIFICATION", evidence_coverage=0.52),
    dict(application_status="OFFERED", matching_status="NOT_ASSESSED", evidence_coverage=0.0),
]

# Dashboard/Work Queue: _APPLICATIONS_QUERY không lọc application_status.
dashboard = summarize_applications(rows)
# API ranking: chỉ trả hồ sơ đang sàng lọc.
ranking = summarize_applications([r for r in rows if r["application_status"] in SCREENING])
# Chip trang xếp hạng, theo đúng frontend/src/lib/applicantReview.ts::needsVerification
# sau khi thống nhất: hồ sơ chưa đánh giá không thuộc nhóm "cần xác minh".
chip = sum(
    1 for r in rows
    if r["application_status"] in SCREENING
    and r["matching_status"] != "NOT_ASSESSED"
    and (r["matching_status"] == "NEEDS_HR_VERIFICATION" or r["evidence_coverage"] < 0.7)
)

print(f"{'nguồn':30} {'needs_verification':>19} {'total':>6}")
print(f"{'Dashboard / Work Queue':30} {dashboard['needs_verification']:>19} {dashboard['total']:>6}")
print(f"{'API ranking (đang sàng lọc)':30} {ranking['needs_verification']:>19} {ranking['total']:>6}")
print(f"{'Chip FE (đang sàng lọc)':30} {chip:>19} {ranking['total']:>6}")
