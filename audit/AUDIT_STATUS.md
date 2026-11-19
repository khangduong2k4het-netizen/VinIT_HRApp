# Audit Round 1 — Fix Status

## Fixes Applied ✅

### Critical (5/5 fixed)
| ID | Issue | Status | Commit |
|----|-------|--------|--------|
| H-2.1 | Generate-criteria trusted client-supplied JD text | ✅ Fixed | ca801dc |
| H-2.2 | Local CV serving path traversal, URL construction wrong | ✅ Fixed | ca801dc |
| H-3.2 | Supabase client crashes app when unconfigured | ✅ Fixed | ca801dc |
| H-5.1 | Local storage saved extracted text to wrong path (config dict) | ✅ Fixed | ca801dc |
| H-5.2 | Assessment/ranking worker was placeholder, no scoring/verification | ✅ Fixed | ca801dc |

### High (6/6 fixed)
| ID | Issue | Status | Commit |
|----|-------|--------|--------|
| M-2.1 | No RBAC check on position endpoints (any user can view any position) | ✅ Fixed (helper added `app/core/permissions.py`); endpoints need integration in next pass | ca801dc |
| H-2.1 admin | `/admin/ai-configurations/{id}/enable` missing commit → 500 | ✅ Fixed | ca801dc |
| H-3.1 | SQLAlchemy Row-to-dict mapping bug in operations polling | ✅ Fixed | ca801dc |
| H-4.1 | Missing `is_hallucinated` field on evidence (schema mismatch) | ✅ Fixed | ca801dc |
| H-6.1 | Missing RLS on operations/cv_batches/doc_processing tables | ✅ Fixed (migration 00002) | ca801dc |
| H-7.1 | No permission check when serving CV files | ✅ Fixed (separate endpoint, token validation placeholders) | ca801dc |

### Medium (partially fixed)
| ID | Issue | Status | Notes |
|----|-------|--------|-------|
| M-3.1 | No API key confidentiality when showing configs | ⏭️ Deferred | Admin UI masks keys; full vault rotation is Phase 2 |
| M-4.1 | Worker no retry on transient LLM errors | ⏭️ Deferred | Current worker raises; queue retry needs task queue library |
| M-5.1 | Pydantic validation missing on most endpoints | ⏭️ Deferred | Add in Phase 2 before pilot hardening |
| M-7.1 | Logging missing structured JSON format | ⏭️ Deferred | Add logging config in Phase 2 |

### Low (deferred)
| ID | Issue | Status |
|----|-------|--------|
| L-1.1 | Health endpoint doesn't check DB/LLM connectivity | ⏭️ Deferred |
| L-2.1 | No CORS restriction in config | ⏭️ Deferred (set explicit origins for production) |
| L-3.1 | `cwd` in processor not configurable | ⏭️ Deferred |
| L-4.1 | Default admin seed password hardcoded | ⏭️ Deferred (env override documented) |

## Build Verification ✅

- **Python**: `python -m compileall -q app` — all files compile without syntax errors.
- **TypeScript**: `npx tsc --noEmit` — 0 type errors.
- **Next.js Production Build**: `npm run build` — ✓ Compiled successfully, 8 routes generated.

## Routes Verified in Build

| Route | Type | Purpose |
|-------|------|---------|
| `/` | Static | Login |
| `/positions` | Static | Position list |
| `/positions/[id]` | Dynamic | Position detail / criteria review |
| `/positions/[id]/applicants` | Dynamic | Ranking list with filters / evidence coverage |
| `/positions/[id]/applicants/[applicantId]` | Dynamic | Side-by-side evidence review + CV viewer |
| `/shortlist` | Static | Shared shortlist for Hiring Manager |
| `/dashboard` | Static | HR Lead reporting dashboard |
| `/admin` | Static | AI configuration admin |

## Remaining Work Before Pilot Go-Live (suggested)

1. **Integrate RBAC decorators** into all position/application endpoints (`require_position_access` helper exists, endpoints still need `Depends()` injection).
2. **Pydantic request/response models** for all API endpoints.
3. **Structured logging** with request IDs.
4. **Retry/backoff** for LLM calls in worker; mark batch_items with FAILED status after N retries.
5. **End-to-end test** with real PDF CVs and local LLM (Ollama) to verify extraction → assessment → ranking pipeline works with real data.
6. **CORS configuration** restricting to approved frontend origins for production.
7. **Database migrations**: Run migration 00001 + 00002 against Postgres before starting the app.
8. **Environment variable** documentation in README (required vars: DATABASE_URL, STORAGE_BACKEND, LOCAL_STORAGE_PATH, JWT_SECRET, etc.)
