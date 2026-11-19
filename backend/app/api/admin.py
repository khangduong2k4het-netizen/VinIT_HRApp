import json
from typing import Literal
from uuid import UUID

from fastapi import APIRouter, Depends, HTTPException
from pydantic import BaseModel, ConfigDict, Field, field_validator
from sqlalchemy import text

from app.core.config import settings
from app.core.permissions import require_admin_role
from app.db.database import SessionLocal
from app.services.ai_config import (
    AIConfigError,
    allowed_endpoints,
    allowed_models,
    canonical_endpoint,
    get_active_runtime,
    public_runtime,
    validate_runtime,
)
from app.services.ai_secrets import (
    AISecretConfigurationError,
    AISecretError,
    api_key_hint,
    decrypt_api_key,
    encrypt_api_key,
    encryption_ready,
    normalize_api_key,
)
from app.services.audit_integrity import verify_audit_chain
from app.services.langfuse_observability import get_observability_status
from app.services.llm_client import LLMError, llm_client
from app.services.ltr import LTRError, LTRModel, artifact_sha256
from app.services.semantic_diagnostics import get_semantic_diagnostics

router = APIRouter()


class AIConfigUpdateRequest(BaseModel):
    # api_key is write-only: it is encrypted before storage and is never
    # returned by any endpoint, audit record or operation snapshot.
    model_config = ConfigDict(extra="forbid")
    provider: Literal["local", "openai", "azure", "compatible"]
    provider_name: str | None = Field(default=None, max_length=120)
    model_name: str = Field(min_length=1, max_length=200)
    api_base: str = Field(min_length=1, max_length=500)
    api_key: str | None = Field(default=None, max_length=500, repr=False)
    temperature_default: float = Field(default=0.1, ge=0, le=1)

    @field_validator("provider_name", "model_name", "api_base", mode="before")
    @classmethod
    def _strip_text(cls, value):
        return value.strip() if isinstance(value, str) else value

    @field_validator("api_key", mode="before")
    @classmethod
    def _empty_api_key_is_omitted(cls, value):
        if isinstance(value, str):
            value = value.strip()
            return value or None
        return value


class LTRModelReviewRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: str = Field(min_length=1, max_length=1000)

    @field_validator("reason", mode="before")
    @classmethod
    def _strip_reason(cls, value):
        return value.strip() if isinstance(value, str) else value


def _lock_active_admin(db, user_id: str) -> None:
    """Keep account/role revocation from racing a configuration write."""
    account = db.execute(text("SELECT account_status FROM app_private.user_profiles WHERE user_id=:user FOR SHARE"),
                         {"user": user_id}).scalar_one_or_none()
    roles = db.execute(text("""
        SELECT role_code FROM app_private.user_role_assignments
        WHERE user_id=:user AND role_code='ADMIN' AND revoked_at IS NULL FOR SHARE
    """), {"user": user_id}).scalars().all()
    if account != "ACTIVE" or not roles:
        raise HTTPException(status_code=403, detail="Admin role required for this endpoint")


def _validate_choice(runtime: dict, *, require_provider_name: bool = False) -> dict:
    try:
        normalized = validate_runtime(runtime, require_provider_name=require_provider_name)
        # The database/UI cannot override the environment's egress decision.
        llm_client._check_endpoint_policy(normalized["api_base"])
        return normalized
    except (AIConfigError, LLMError) as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


def _stored_key_config_id_for_endpoint(db, runtime: dict) -> str | None:
    """Return the ACTIVE config whose stored key may be reused for this URL."""
    active = db.execute(text("""
        SELECT config_id, api_base, api_key_ciphertext
        FROM app_private.ai_configuration_versions
        WHERE status = 'ACTIVE' LIMIT 1
    """)).mappings().first()
    if not active or not active["api_key_ciphertext"] or not active["api_base"]:
        return None
    try:
        same_endpoint = canonical_endpoint(active["api_base"]) == runtime["api_base"]
    except AIConfigError:
        return None
    return str(active["config_id"]) if same_endpoint else None


@router.get("/ai/options")
async def get_ai_options(current_user: dict = Depends(require_admin_role)):
    try:
        return {"models": allowed_models(), "endpoints": allowed_endpoints(),
                "external_api_allowed": settings.ALLOW_EXTERNAL_API,
                "custom_openai_compatible": {
                    "api_key_encryption_configured": encryption_ready(),
                }}
    except AIConfigError:
        raise HTTPException(status_code=503, detail="Danh sách endpoint của môi trường không hợp lệ") from None


@router.get("/ai/config")
async def list_ai_configs(current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT config_id, provider, provider_name, model_name, deployment_mode, api_base,
                   temperature_default, status, created_by, created_at, enabled_at, disabled_at,
                   (api_key_ciphertext IS NOT NULL) AS api_key_configured, api_key_hint
            FROM app_private.ai_configuration_versions ORDER BY created_at DESC, config_id DESC LIMIT 100
        """)).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


@router.post("/ai/config", status_code=201)
async def create_ai_config(request: AIConfigUpdateRequest, current_user: dict = Depends(require_admin_role)):
    submitted = request.model_dump()
    api_key = submitted.pop("api_key")
    runtime = _validate_choice(
        submitted,
        require_provider_name=submitted["provider"] == "compatible",
    )
    if api_key is not None and runtime["provider"] != "compatible":
        raise HTTPException(
            status_code=400,
            detail="API key chỉ áp dụng cho nhà cung cấp OpenAI Compatible.",
        )

    api_key_ciphertext = None
    stored_hint = None
    if api_key is not None:
        try:
            normalized_key = normalize_api_key(api_key)
            api_key_ciphertext = encrypt_api_key(normalized_key)
            stored_hint = api_key_hint(normalized_key)
        except AISecretConfigurationError as exc:
            raise HTTPException(status_code=503, detail=str(exc)) from None
        except AISecretError as exc:
            raise HTTPException(status_code=400, detail=str(exc)) from None

    db = SessionLocal()
    try:
        _lock_active_admin(db, current_user["user_id"])
        if runtime["provider"] == "compatible" and api_key is None:
            # Reuse is endpoint-bound: changing only the provider display name,
            # model or temperature at the same Base URL must not force the
            # Admin to retype a key, and the key is never copied to a new URL.
            active = db.execute(text("""
                SELECT api_base, api_key_ciphertext, api_key_hint
                FROM app_private.ai_configuration_versions
                WHERE status = 'ACTIVE' LIMIT 1
            """)).mappings().first()
            if active and active["api_key_ciphertext"] and active["api_base"]:
                try:
                    same_endpoint = canonical_endpoint(active["api_base"]) == runtime["api_base"]
                except AIConfigError:
                    same_endpoint = False
                if same_endpoint:
                    api_key_ciphertext = active["api_key_ciphertext"]
                    stored_hint = active["api_key_hint"]
        row = db.execute(text("""
            INSERT INTO app_private.ai_configuration_versions
                (provider, provider_name, model_name, deployment_mode, api_base,
                 temperature_default, api_key_ciphertext, api_key_hint, created_by, status)
            VALUES (:provider, :provider_name, :model_name, :provider, :api_base,
                    :temperature_default, :api_key_ciphertext, :api_key_hint, :user_id, 'DRAFT')
            RETURNING config_id, provider, provider_name, model_name, api_base,
                      temperature_default, status, created_at,
                      (api_key_ciphertext IS NOT NULL) AS api_key_configured, api_key_hint
        """), {**runtime, "api_key_ciphertext": api_key_ciphertext,
               "api_key_hint": stored_hint,
               "user_id": current_user["user_id"]}).mappings().one()
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'CREATE_AI_CONFIG', 'AI_CONFIG', :id, 'DRAFT')
        """), {"user_id": current_user["user_id"], "id": row["config_id"]})
        db.commit()
        return dict(row)
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/ai/test-connection")
async def test_ai_connection(request: AIConfigUpdateRequest, current_user: dict = Depends(require_admin_role)):
    """Test the entered provider values without creating a config version."""
    submitted = request.model_dump()
    api_key = submitted.pop("api_key")
    runtime = _validate_choice(
        submitted,
        require_provider_name=submitted["provider"] == "compatible",
    )
    if api_key is not None and runtime["provider"] != "compatible":
        raise HTTPException(
            status_code=400,
            detail="API key chỉ áp dụng cho nhà cung cấp OpenAI Compatible.",
        )
    runtime["source"] = "connection_test"

    db = SessionLocal()
    try:
        _lock_active_admin(db, current_user["user_id"])
        if api_key is not None:
            try:
                runtime["api_key"] = normalize_api_key(api_key)
                runtime["api_key_configured"] = True
            except AISecretError as exc:
                raise HTTPException(status_code=400, detail=str(exc)) from None
        elif runtime["provider"] == "compatible":
            reusable_config_id = _stored_key_config_id_for_endpoint(db, runtime)
            if reusable_config_id:
                runtime["config_id"] = reusable_config_id
                runtime["api_key_configured"] = True
    finally:
        db.close()

    try:
        return await llm_client.test_provider_connection(runtime)
    except LLMError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from None


@router.post("/ai/config/{config_id}/enable")
async def enable_ai_config(config_id: UUID, current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        _lock_active_admin(db, current_user["user_id"])
        # Serialize activations across all API instances and make the switch
        # atomic. Existing worker attempts keep their already-pinned snapshot.
        db.execute(text("SELECT pg_advisory_xact_lock(hashtextextended('hra-ai-activation', 418630021))"))
        row = db.execute(text("""
            SELECT config_id, provider, provider_name, model_name, api_base,
                   temperature_default, status, api_key_ciphertext
            FROM app_private.ai_configuration_versions WHERE config_id = :id FOR UPDATE
        """), {"id": str(config_id)}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy phiên bản cấu hình AI")
        _validate_choice(
            dict(row),
            require_provider_name=row["provider"] == "compatible",
        )
        if row["api_key_ciphertext"]:
            try:
                decrypt_api_key(row["api_key_ciphertext"])
            except AISecretError as exc:
                raise HTTPException(status_code=503, detail=str(exc)) from None
        db.execute(text("""
            UPDATE app_private.ai_configuration_versions SET status = 'DISABLED', disabled_at = NOW()
            WHERE status = 'ACTIVE' AND config_id != :id
        """), {"id": str(config_id)})
        db.execute(text("""
            UPDATE app_private.ai_configuration_versions SET status = 'ACTIVE', enabled_at = NOW(), disabled_at = NULL
            WHERE config_id = :id
        """), {"id": str(config_id)})
        db.execute(text("""
            INSERT INTO app_private.audit_events (actor_user_id, action_type, object_type, object_id, outcome)
            VALUES (:user_id, 'ENABLE_AI_CONFIG', 'AI_CONFIG', :id, 'ACTIVE')
        """), {"user_id": current_user["user_id"], "id": str(config_id)})
        db.commit()
        return {"config_id": str(config_id), "status": "ACTIVE"}
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.get("/ai/active-config")
async def get_active_ai_config(current_user: dict = Depends(require_admin_role)):
    db = SessionLocal()
    try:
        runtime = get_active_runtime(db, include_secret=False)
    finally:
        db.close()
    try:
        validate_runtime(
            runtime,
            require_provider_name=(
                runtime.get("source") == "database" and runtime.get("provider") == "compatible"
            ),
        )
        llm_client._check_endpoint_policy(runtime["api_base"])
        allowed = True
    except (AIConfigError, LLMError):
        allowed = False
    return {"active": True, "source": runtime["source"], "allowed_by_this_process": allowed,
            "config": {**public_runtime(runtime), "external_api_allowed": settings.ALLOW_EXTERNAL_API}}


@router.get("/langfuse/health")
async def get_langfuse_health(current_user: dict = Depends(require_admin_role)):
    """Safe Langfuse configuration state; never returns keys or host."""
    return get_observability_status()


@router.get("/semantic/health")
async def get_semantic_health(current_user: dict = Depends(require_admin_role)):
    """Configured/runtime semantic state for this API/worker process.

    This intentionally does not call the embedding provider and never
    returns the configured endpoint or API key.  ``READY_UNVERIFIED`` means
    configuration is coherent but this process has not completed a semantic
    run yet; ``DEGRADED_FALLBACK`` means the last attempt returned lexical
    candidates because the provider failed.
    """
    return get_semantic_diagnostics()


@router.get("/audit/verify")
async def verify_audit_integrity(current_user: dict = Depends(require_admin_role)):
    """Verify the audit hash chain without exposing audit metadata."""
    db = SessionLocal()
    try:
        return verify_audit_chain(db)
    finally:
        db.close()


@router.get("/ltr/models")
async def list_ltr_models(current_user: dict = Depends(require_admin_role)):
    """List LTR registry metadata without returning model artifacts."""
    db = SessionLocal()
    try:
        rows = db.execute(text("""
            SELECT model_version, status, metrics, feature_names, training_examples,
                   training_groups, data_sha256, artifact_sha256, registered_by,
                   reviewed_by, reviewed_at, review_reason, created_at, approved_at
            FROM app_private.ltr_model_versions
            ORDER BY created_at DESC, model_version DESC
            LIMIT 100
        """)).mappings().all()
        return [dict(row) for row in rows]
    finally:
        db.close()


def _review_ltr_model(model_version: str, action: str, reason: str, current_user: dict) -> dict:
    target_status = "APPROVED" if action == "APPROVED" else "REJECTED"
    db = SessionLocal()
    try:
        _lock_active_admin(db, current_user["user_id"])
        row = db.execute(text("""
            SELECT model_version, artifact, metrics, data_sha256, artifact_sha256, status
            FROM app_private.ltr_model_versions
            WHERE model_version = :model_version
            FOR UPDATE
        """), {"model_version": model_version}).mappings().first()
        if not row:
            raise HTTPException(status_code=404, detail="Không tìm thấy LTR model version")
        if str(row["status"] or "").upper() != "DRAFT":
            raise HTTPException(status_code=409, detail="Chỉ có thể phê duyệt hoặc từ chối model ở trạng thái DRAFT")
        artifact = row["artifact"]
        if isinstance(artifact, str):
            artifact = json.loads(artifact)
        try:
            model = LTRModel.from_artifact(artifact)
        except (LTRError, TypeError, ValueError) as exc:
            raise HTTPException(status_code=409, detail=f"Artifact LTR không hợp lệ: {exc}") from None
        current_hash = artifact_sha256(artifact)
        if row["artifact_sha256"] and str(row["artifact_sha256"]) != current_hash:
            raise HTTPException(status_code=409, detail="Artifact hash trong registry không khớp nội dung artifact")
        if action == "APPROVED" and not model.passes_gates(
            min_ndcg=float(settings.LTR_MIN_NDCG_AT_10),
            min_pairwise=float(settings.LTR_MIN_PAIRWISE_ACCURACY),
            min_test_examples=int(settings.LTR_MIN_HOLDOUT_EXAMPLES),
            min_test_groups=int(settings.LTR_MIN_HOLDOUT_GROUPS),
        ):
            raise HTTPException(status_code=400, detail="Artifact chưa đạt quality gates để phê duyệt")

        db.execute(text("""
            UPDATE app_private.ltr_model_versions
            SET status = :status,
                artifact_sha256 = :artifact_sha256,
                reviewed_by = :user_id,
                reviewed_at = NOW(),
                review_reason = :reason,
                approved_at = CASE WHEN :status = 'APPROVED' THEN NOW() ELSE NULL END
            WHERE model_version = :model_version
        """), {
            "status": target_status, "artifact_sha256": current_hash,
            "user_id": current_user["user_id"], "reason": reason,
            "model_version": model_version,
        })
        metrics = row["metrics"] if isinstance(row["metrics"], dict) else {}
        db.execute(text("""
            INSERT INTO app_private.ltr_model_review_events
                (model_version, artifact_sha256, actor_user_id, action, from_status,
                 to_status, reason, metrics, data_sha256)
            VALUES (:model_version, :artifact_sha256, :user_id, :action, 'DRAFT',
                    :status, :reason, CAST(:metrics AS jsonb), :data_sha256)
        """), {
            "model_version": model_version, "artifact_sha256": current_hash,
            "user_id": current_user["user_id"], "action": action,
            "status": target_status, "reason": reason,
            "metrics": json.dumps(metrics, ensure_ascii=False),
            "data_sha256": row["data_sha256"],
        })
        db.execute(text("""
            INSERT INTO app_private.audit_events
                (actor_user_id, action_type, object_type, object_id, outcome, metadata)
            VALUES (:user_id, :action_type, 'LTR_MODEL', NULL, :status,
                    CAST(:metadata AS jsonb))
        """), {
            "user_id": current_user["user_id"],
            "action_type": f"LTR_MODEL_{action}",
            "status": target_status,
            "metadata": json.dumps({
                "model_version": model_version,
                "artifact_sha256": current_hash,
            }, ensure_ascii=False),
        })
        updated = db.execute(text("""
            SELECT model_version, status, artifact_sha256, reviewed_by, reviewed_at,
                   review_reason, approved_at
            FROM app_private.ltr_model_versions
            WHERE model_version = :model_version
        """), {"model_version": model_version}).mappings().one()
        db.commit()
        return dict(updated)
    except HTTPException:
        db.rollback()
        raise
    except Exception:
        db.rollback()
        raise
    finally:
        db.close()


@router.post("/ltr/models/{model_version}/approve")
async def approve_ltr_model(
    model_version: str,
    request: LTRModelReviewRequest,
    current_user: dict = Depends(require_admin_role),
):
    return _review_ltr_model(model_version, "APPROVED", request.reason, current_user)


@router.post("/ltr/models/{model_version}/reject")
async def reject_ltr_model(
    model_version: str,
    request: LTRModelReviewRequest,
    current_user: dict = Depends(require_admin_role),
):
    return _review_ltr_model(model_version, "REJECTED", request.reason, current_user)


@router.get("/worker/health")
async def get_worker_health(current_user: dict = Depends(require_admin_role)):
    """Queue indicators, not a substitute for external alerting/liveness probes."""
    db = SessionLocal()
    try:
        row = db.execute(text("""
            SELECT COUNT(*) FILTER (WHERE status = 'PENDING') AS pending,
                   COUNT(*) FILTER (WHERE status = 'PROCESSING') AS processing,
                   COUNT(*) FILTER (WHERE status = 'PROCESSING' AND
                       (heartbeat_at IS NULL OR heartbeat_at < NOW() - INTERVAL '2 minutes')) AS stale_heartbeat,
                   COUNT(*) FILTER (WHERE status = 'PROCESSING' AND attempt_started_at < NOW() - INTERVAL '30 minutes') AS long_running,
                   COUNT(*) FILTER (WHERE status = 'FAILED' AND completed_at >= NOW() - INTERVAL '24 hours') AS failed_24h,
                   (SELECT COUNT(*) FROM app_private.operation_recovery_events WHERE recovered_at >= NOW() - INTERVAL '24 hours') AS recoveries_24h,
                   COALESCE(EXTRACT(EPOCH FROM (NOW() - MIN(created_at) FILTER (WHERE status = 'PENDING'))), 0)::integer AS oldest_pending_seconds
            FROM app_private.operations WHERE capability IN ('CV_PROCESSING', 'ASSESSMENT', 'RANKING')
        """)).mappings().one()
        return {**dict(row), "stale_after_seconds": 120, "long_running_after_seconds": 1800}
    finally:
        db.close()


@router.get("/audit/events")
async def list_audit_events(
    action_type: str | None = None,
    actor_user_id: UUID | None = None,
    position_id: UUID | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 50,
    current_user: dict = Depends(require_admin_role),
):
    """S-20: browse the audit trail (Admin only, like /audit/verify).

    Returns who did what to which object and the outcome. The free-form
    metadata column is deliberately NOT returned: it can hold role lists or
    other context that the audit viewer does not need, and must never be a
    side channel for CV content or PII.
    """
    if page < 1 or not 1 <= page_size <= 200:
        raise HTTPException(status_code=400, detail="Tham số phân trang không hợp lệ")
    if action_type is not None and (len(action_type) > 100 or not action_type.replace("_", "").isalnum()):
        raise HTTPException(status_code=400, detail="Loại thao tác không hợp lệ")
    from datetime import date as _date
    bounds = {}
    for key, value in (("date_from", date_from), ("date_to", date_to)):
        if value:
            try:
                bounds[key] = _date.fromisoformat(value)
            except ValueError:
                raise HTTPException(status_code=400, detail="Ngày phải theo định dạng YYYY-MM-DD") from None
        else:
            bounds[key] = None
    params = {"action": action_type, "actor": str(actor_user_id) if actor_user_id else None,
              "position": str(position_id) if position_id else None,
              "from": bounds["date_from"], "to": bounds["date_to"],
              "limit": page_size, "offset": (page - 1) * page_size}
    where = """
        WHERE (CAST(:action AS text) IS NULL OR e.action_type = :action)
          AND (CAST(:actor AS uuid) IS NULL OR e.actor_user_id = CAST(:actor AS uuid))
          AND (CAST(:position AS uuid) IS NULL OR e.position_id = CAST(:position AS uuid))
          AND (CAST(:from AS date) IS NULL OR e.created_at >= CAST(:from AS date))
          AND (CAST(:to AS date) IS NULL OR e.created_at < CAST(:to AS date) + INTERVAL '1 day')
    """
    db = SessionLocal()
    try:
        total = db.execute(text("SELECT COUNT(*) FROM app_private.audit_events e" + where), params).scalar_one()
        rows = db.execute(text("""
            SELECT e.event_id, e.created_at, e.action_type, e.object_type, e.object_id, e.outcome,
                   e.actor_user_id, actor.display_name AS actor_name,
                   e.position_id, p.title AS position_title, p.position_code
            FROM app_private.audit_events e
            LEFT JOIN app_private.user_profiles actor ON actor.user_id = e.actor_user_id
            LEFT JOIN app_private.positions p ON p.position_id = e.position_id
        """ + where + " ORDER BY e.created_at DESC, e.event_id DESC LIMIT :limit OFFSET :offset"), params).mappings().all()
        action_types = db.execute(text("SELECT DISTINCT action_type FROM app_private.audit_events ORDER BY action_type")).scalars().all()
        return {"total": total, "page": page, "page_size": page_size,
                "items": [dict(row) for row in rows], "action_types": list(action_types)}
    finally:
        db.close()
