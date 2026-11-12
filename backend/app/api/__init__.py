from fastapi import APIRouter
from . import quality, cross_duplicates, candidate_reports
from . import auth, users, positions, criteria, applications, assessments, shortlist, dashboard, admin, account_admin, operations, candidate_details, departments, retention, rubric_library, scorecards, analytics

api_router = APIRouter()
api_router.include_router(quality.router, prefix="/quality", tags=["Quality Inspection"])
api_router.include_router(cross_duplicates.router, prefix="/cross-duplicates", tags=["Cross-position Duplicates"])
api_router.include_router(candidate_reports.router, prefix="/candidate-reports", tags=["Candidate Comparison & Export"])
api_router.include_router(auth.router, prefix="/auth", tags=["Authentication"])
api_router.include_router(operations.router, prefix="/operations", tags=["Async Operations"])
api_router.include_router(users.router, prefix="/users", tags=["Users"])
api_router.include_router(departments.router, prefix="/departments", tags=["Departments"])
api_router.include_router(positions.router, prefix="/positions", tags=["Positions"])
api_router.include_router(criteria.router, prefix="/criteria", tags=["Criteria & Rubric"])
api_router.include_router(applications.router, prefix="/applications", tags=["Applications & CVs"])
api_router.include_router(candidate_details.router, prefix="/applications", tags=["Candidate details"])
api_router.include_router(assessments.router, prefix="/assessments", tags=["AI Assessment & Ranking"])
# Scorecards first: their literal paths must win over /shortlist/{share_id}.
api_router.include_router(scorecards.router, prefix="/shortlist", tags=["Shortlist Scorecards"])
api_router.include_router(shortlist.router, prefix="/shortlist", tags=["Shortlist Sharing"])
api_router.include_router(rubric_library.router, prefix="/rubric-library", tags=["Rubric Library"])
api_router.include_router(dashboard.router, prefix="/dashboard", tags=["Dashboard & Reporting"])
api_router.include_router(analytics.router, prefix="/analytics", tags=["Operational Analytics"])
api_router.include_router(retention.router, prefix="/retention", tags=["Retention & Deletion"])
api_router.include_router(admin.router, prefix="/admin", tags=["Admin Configuration"])
api_router.include_router(account_admin.router, prefix="/admin/users", tags=["Admin Accounts"])
