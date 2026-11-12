from pydantic import model_validator
from pydantic_settings import BaseSettings, SettingsConfigDict
from typing import Literal, Optional


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", case_sensitive=True)

    # Application
    APP_ENV: str = "development"
    APP_NAME: str = "VinUni HRA API"
    API_V1_PREFIX: str = "/v1"
    DEBUG: bool = False

    # Database - direct PostgreSQL connection string
    DATABASE_URL: str = "postgresql://postgres:postgres@localhost:5432/hra"
    DATABASE_POOL_SIZE: int = 5

    # Supabase (optional - used for Auth and Storage if provided)
    SUPABASE_URL: Optional[str] = None
    SUPABASE_ANON_KEY: Optional[str] = None
    SUPABASE_SERVICE_ROLE_KEY: Optional[str] = None
    # Legacy HS256 verification only. Projects using asymmetric signing keys
    # (for example ES256) are verified through JWKS derived from SUPABASE_URL.
    SUPABASE_JWT_SECRET: str = ""
    SUPABASE_JWT_ISSUER: Optional[str] = None
    SUPABASE_JWKS_URL: Optional[str] = None
    SUPABASE_JWKS_CACHE_SECONDS: int = 300

    # Disabled by default. Set a unique random token only during first-admin
    # setup, over HTTPS and a restricted network; remove it afterwards.
    ADMIN_BOOTSTRAP_TOKEN: str = ""

    # Storage (local or Supabase)
    STORAGE_BACKEND: str = "local"  # "local" or "supabase"
    LOCAL_STORAGE_PATH: str = "./storage"
    SUPABASE_STORAGE_BUCKET_CV: str = "cv-originals"
    SUPABASE_STORAGE_BUCKET_EXTRACTED: str = "cv-extracted-text"

    # File upload limits
    MAX_FILE_SIZE_BYTES: int = 10_000_000  # 10 MB
    MAX_FILES_PER_BATCH: int = 50
    MAX_BATCH_SIZE_BYTES: int = 250_000_000  # 250 MB

    # F2.06 — image CVs (JPG/PNG) and images embedded in DOCX.
    # Tesseract language packs, joined with "+" (e.g. "eng+vie"). Every pack
    # listed here must be installed on the worker host.
    OCR_LANGUAGES: str = "eng"
    # Decompression-bomb guard: images above this pixel count are rejected.
    OCR_MAX_IMAGE_PIXELS: int = 16_000_000
    # Below this effective resolution the CV goes to the HR manual queue.
    OCR_MIN_DPI: int = 150
    # Variance of the Laplacian on the normalised grayscale image. Lower means
    # blurrier. Proposed default from a synthetic A4 test (readable at 35,
    # garbled at 10); recalibrate on a labelled image set before go-live.
    OCR_MIN_SHARPNESS: float = 20.0
    # Embedded DOCX images smaller than this (logos, icons) are not OCR-ed.
    OCR_DOCX_MIN_IMAGE_PIXELS: int = 40_000
    OCR_DOCX_MAX_IMAGES: int = 10

    # AI/LLM
    # local/openai/azure/compatible labels share the OpenAI-compatible transport.
    # "mock" = built-in synthetic AI for development until AI Core exposes its API.
    LLM_PROVIDER: str = "local"
    LLM_PROVIDER_NAME: Optional[str] = None
    LLM_MODEL_NAME: str = "vinuni/hra-llm-7b"
    LLM_API_BASE: Optional[str] = None
    LLM_API_KEY: Optional[str] = None
    # Server-only Fernet key used to encrypt API keys entered by an Admin for
    # an OpenAI-compatible provider. Generate one with:
    #   python -c "from cryptography.fernet import Fernet; print(Fernet.generate_key().decode())"
    # Rotating it makes previously stored provider keys undecryptable.
    AI_CONFIG_ENCRYPTION_KEY: str = ""
    # Optional JSON arrays. The environment default endpoint/model are always
    # included. These are operator policy, never editable in the UI.
    LLM_ALLOWED_API_BASES: list[str] = []
    LLM_ALLOWED_MODELS: list[str] = []
    LLM_TEMPERATURE_DEFAULT: float = 0.1
    # Optional provider seed. Leave unset unless the selected OpenAI-compatible
    # provider explicitly supports `seed`; determinism is still best-effort.
    LLM_SEED: int | None = None
    ALLOW_EXTERNAL_API: bool = False
    # Opt-in provider-enforced JSON Schema for matching. Some compatible
    # endpoints reject this response format, so it stays off by default and
    # client-side validation remains the fallback.
    LLM_STRICT_JSON_SCHEMA: bool = False

    # Matching/Scoring. Bump these versions whenever prompt, scoring or rule
    # behaviour changes; assessment fingerprints include them so old results
    # are never silently mixed with new behaviour.
    ASSESSMENT_POLICY_VERSION: str = "assessment-v2.0"
    MATCHING_POLICY_VERSION: str = "matching-v2.1"
    RANKING_POLICY_VERSION: str = "ranking-v2.0"
    CRITERIA_PROMPT_VERSION: str = "criteria-prompt-v2.1"
    PROFILE_PROMPT_VERSION: str = "profile-prompt-v2.0"
    MATCHING_PROMPT_VERSION: str = "matching-prompt-v2.0"
    DETERMINISTIC_RULES_VERSION: str = "deterministic-rules-v1.4"
    MANDATORY_CRITERIA_WEIGHT_DEFAULT: float = 0.7
    NICE_TO_HAVE_WEIGHT_DEFAULT: float = 0.3
    MIN_EVIDENCE_COVERAGE: float = 0.7
    STRONG_MATCH_SCORE: int = 100
    MATCH_SCORE: int = 80
    NO_MATCH_SCORE: int = 0

    # Semantic retrieval (pgvector + BGE). Disabled by default: enabling it
    # changes the candidate chunks sent to the LLM fallback, so the full
    # semantic configuration is pinned into the assessment fingerprint.
    SEMANTIC_RETRIEVAL_ENABLED: bool = False
    EMBEDDING_PROVIDER: str = "disabled"  # disabled | bge_http | hash
    EMBEDDING_API_BASE: str | None = None
    EMBEDDING_API_KEY: str | None = None
    EMBEDDING_MODEL: str = "BAAI/bge-m3"
    EMBEDDING_DIMENSION: int = 1024
    EMBEDDING_INDEX_VERSION: str = "bge-index-v1"
    EMBEDDING_TIMEOUT_SECONDS: float = 30.0
    EMBEDDING_QUERY_INSTRUCTION: str = ""
    SEMANTIC_TOP_K: int = 5
    SEMANTIC_MIN_SIMILARITY: float = 0.35

    # Learning-to-Rank. OFF by default; SHADOW scores without changing the
    # published order, ACTIVE may reorder only inside the existing
    # mandatory-status/coverage gates when a gated model artifact is loaded.
    LTR_MODE: str = "OFF"  # OFF | SHADOW | ACTIVE
    LTR_MODEL_PATH: str | None = None
    LTR_MODEL_VERSION: str | None = None
    LTR_MIN_NDCG_AT_10: float = 0.70
    LTR_MIN_PAIRWISE_ACCURACY: float = 0.65
    LTR_MIN_HOLDOUT_EXAMPLES: int = 20
    LTR_MIN_HOLDOUT_GROUPS: int = 2

    # Langfuse AI observability. Disabled by default and metadata-first:
    # enabling it must never be required for LLM, worker or assessment
    # operations. Content capture is additionally blocked in production by
    # app.services.langfuse_observability.
    LANGFUSE_ENABLED: bool = False
    LANGFUSE_PUBLIC_KEY: Optional[str] = None
    LANGFUSE_SECRET_KEY: Optional[str] = None
    LANGFUSE_HOST: Optional[str] = None
    LANGFUSE_BASE_URL: Optional[str] = None
    LANGFUSE_ENVIRONMENT: Optional[str] = None
    LANGFUSE_RELEASE: Optional[str] = None
    LANGFUSE_SAMPLE_RATE: float = 1.0
    LANGFUSE_CAPTURE_CONTENT: bool = False

    # Retention
    RETENTION_MONTHS: int = 12
    # F2.07 — reminder milestones before the due date (days) and the window in
    # which cases appear in the console before they are due.
    RETENTION_NOTICE_DAYS: list[int] = [30, 15, 7]
    # The periodic cycle (case sync, reopen guard, reminders) is off until
    # Legal & Privacy approves the process. It never deletes data by itself.
    RETENTION_SCHEDULER_ENABLED: bool = False
    RETENTION_SCHEDULER_INTERVAL_MINUTES: int = 60
    # Physical purge needs a one-time code sent to the confirming user.
    RETENTION_PURGE_REQUIRE_OTP: bool = True
    RETENTION_OTP_TTL_MINUTES: int = 10
    RETENTION_OTP_MAX_ATTEMPTS: int = 5
    # Development/testing only: return the OTP in the API response when no
    # email channel is configured. Refused in production by the validator.
    RETENTION_OTP_DEV_ECHO: bool = False
    # Frontend base URL used in reminder emails.
    APP_PUBLIC_URL: str = "http://localhost:3000"

    # Outbound email (retention reminders and purge OTP). Disabled when empty.
    SMTP_HOST: Optional[str] = None
    SMTP_PORT: int = 587
    SMTP_USERNAME: Optional[str] = None
    SMTP_PASSWORD: Optional[str] = None
    SMTP_FROM: Optional[str] = None
    SMTP_STARTTLS: bool = True

    # F2.09 candidate comparison and custom export (Excel/PDF). Contact
    # details (email/phone) are never exported.
    EXPORT_MAX_ROWS: int = 500
    # TrueType font with Vietnamese glyphs for PDF export. Empty = search
    # DejaVu Sans (Linux, fonts-dejavu-core) then Arial (Windows).
    PDF_FONT_PATH: Optional[str] = None

    # CORS
    CORS_ORIGINS: list[str] = ["http://localhost:3000", "http://127.0.0.1:3000"]

    # Security
    ACCESS_TOKEN_EXPIRE_MINUTES: int = 60 * 8  # 8 hours

    # Authentication backend.
    #   "supabase": Supabase Auth issues tokens (default, unchanged behaviour).
    #   "local":    the backend stores scrypt password hashes in PostgreSQL
    #               (app_private.local_credentials) and signs its own HS256
    #               tokens with SUPABASE_JWT_SECRET, which then acts as the
    #               app's JWT secret. Intended for plain PostgreSQL without Supabase.
    AUTH_BACKEND: Literal["supabase", "local"] = "supabase"
    LOCAL_AUTH_MAX_FAILED_ATTEMPTS: int = 5
    LOCAL_AUTH_LOCKOUT_MINUTES: int = 15

    @model_validator(mode="after")
    def _guard_development_shortcuts(self):
        if self.AUTH_BACKEND == "local" and len(self.SUPABASE_JWT_SECRET) < 32:
            raise ValueError("AUTH_BACKEND=local requires SUPABASE_JWT_SECRET of at least 32 random characters")
        # The mock AI returns synthetic, heuristic results. It must never
        # assess real candidates, so it is refused outside development/testing.
        if self.LLM_PROVIDER == "mock" and self.APP_ENV not in ("development", "testing"):
            raise ValueError("LLM_PROVIDER=mock is only allowed when APP_ENV is development or testing")
        if self.RETENTION_OTP_DEV_ECHO and self.APP_ENV not in ("development", "testing"):
            raise ValueError("RETENTION_OTP_DEV_ECHO is only allowed when APP_ENV is development or testing")
        if any(day < 1 for day in self.RETENTION_NOTICE_DAYS):
            raise ValueError("RETENTION_NOTICE_DAYS must contain positive day counts")
        return self


settings = Settings()
