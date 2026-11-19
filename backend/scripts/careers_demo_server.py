"""Standalone fake-auth server for isolated synthetic demos, never production."""
import secrets
import time
from pathlib import Path
import jwt
from fastapi import HTTPException
from fastapi.responses import Response
from sqlalchemy import text
from psycopg2.extensions import parse_dsn

from app.api.careers_demo import require_demo
from app.core.config import settings
from app.db.database import engine
from app.main import create_app
from app.workers.processor import worker, llm_client
from careers_demo_support import DEMO_USER_ID, synthetic_cv, synthetic_email

require_demo()
if parse_dsn(settings.DATABASE_URL).get('dbname') not in ('hra_careers_demo_test', 'hra_careers_ready_test'):
    raise RuntimeError('Demo requires one of the dedicated careers demo test databases')
if (settings.APP_ENV != 'testing' or settings.SUPABASE_URL or settings.SUPABASE_ANON_KEY
        or settings.SUPABASE_SERVICE_ROLE_KEY or settings.ALLOW_EXTERNAL_API or settings.LANGFUSE_ENABLED):
    raise RuntimeError('Demo requires testing mode, no Supabase, Langfuse or external APIs')
if Path(settings.LOCAL_STORAGE_PATH).resolve() != (Path(__file__).resolve().parents[2] / 'staging/generated' / (parse_dsn(settings.DATABASE_URL)['dbname'] + '-storage')).resolve():
    raise RuntimeError('Use only the dedicated synthetic demo storage directory')
with engine.connect() as conn:
    if not conn.execute(text("SELECT 1 FROM app_private.user_profiles WHERE user_id=:id AND display_name='HR demo tổng hợp'"), {'id': DEMO_USER_ID}).first():
        raise RuntimeError('Synthetic demo fixture not found')
settings.SUPABASE_JWT_SECRET = secrets.token_urlsafe(48)
app = create_app()


async def synthetic_profile(**kwargs):
    # No provider call or model inference; only synthetic fixtures are allowed.
    return {'education': [], 'work_history': [], 'skills': []}


llm_client.extract_candidate_profile = synthetic_profile


def skip_demo_assessment(operation_id, db, **kwargs):
    # This demo illustrates intake, not AI scoring/ranking.
    return None


worker._run_assessments = skip_demo_assessment
worker._generate_ranking = skip_demo_assessment


@app.on_event('startup')
def demo_start_worker():
    worker.start()


@app.post('/v1/demo/session')
def demo_session():
    require_demo()
    now = int(time.time())
    token = jwt.encode({'sub': DEMO_USER_ID, 'aud': 'authenticated', 'email': 'hr-demo@example.invalid',
                        'iat': now, 'exp': now + 8 * 3600}, settings.SUPABASE_JWT_SECRET, algorithm='HS256')
    return Response(content=__import__('json').dumps({'access_token': token}), media_type='application/json', headers={'Cache-Control': 'no-store'})


@app.get('/v1/demo/fixture/{kind}')
def demo_fixture(kind: str):
    require_demo()
    if kind == 'cv':
        return Response(synthetic_cv(), media_type='application/vnd.openxmlformats-officedocument.wordprocessingml.document',
                        headers={'Content-Disposition': 'attachment; filename="cv-demo-daniel-whitfield.docx"', 'Cache-Control': 'no-store'})
    if kind == 'email':
        return Response(synthetic_email(), media_type='message/rfc822',
                        headers={'Content-Disposition': 'attachment; filename="email-gia.eml"', 'Cache-Control': 'no-store'})
    raise HTTPException(404, 'Không có file demo')
