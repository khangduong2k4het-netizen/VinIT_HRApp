"""Seed only an empty local disposable careers demo DB. Never truncate anything."""
import os
from pathlib import Path
import hashlib
from uuid import uuid4

from sqlalchemy import text
from psycopg2.extensions import parse_dsn
from app.api.careers_demo import require_demo
from app.core.config import settings
from app.db.database import engine
from careers_demo_support import DEMO_USER_ID, SOURCE_ID, TARGET_ID, SOURCE_CODE, TARGET_CODE, synthetic_cv


def main():
    require_demo()
    if parse_dsn(settings.DATABASE_URL).get('dbname') not in ('hra_careers_demo_test', 'hra_careers_ready_test'):
        raise RuntimeError('Demo requires one of the dedicated careers demo test databases')
    if settings.APP_ENV != 'testing' or settings.SUPABASE_URL or settings.ALLOW_EXTERNAL_API:
        raise RuntimeError('Synthetic demo requires testing mode, no Supabase and no external APIs')
    root = Path(settings.LOCAL_STORAGE_PATH).resolve()
    if root != (Path(__file__).resolve().parents[2] / 'staging/generated' / (parse_dsn(settings.DATABASE_URL)['dbname'] + '-storage')).resolve():
        raise RuntimeError('Use only the dedicated synthetic demo storage directory')
    relative = f'{SOURCE_ID}/seed-synthetic/cv.docx'
    path = root / settings.SUPABASE_STORAGE_BUCKET_CV / relative
    with engine.begin() as conn:
        if conn.execute(text('SELECT EXISTS(SELECT 1 FROM auth.users) OR EXISTS(SELECT 1 FROM app_private.positions)')).scalar_one():
            raise RuntimeError('Database is not empty; refusing to modify it')
        if path.exists():
            raise RuntimeError('Demo fixture already exists; refusing to overwrite it')
        conn.execute(text("INSERT INTO auth.users(id,email) VALUES (:id,'hr-demo@example.invalid')"), {'id': DEMO_USER_ID})
        conn.execute(text("INSERT INTO app_private.user_profiles(user_id,display_name) VALUES (:id,'HR demo tổng hợp')"), {'id': DEMO_USER_ID})
        conn.execute(text("INSERT INTO app_private.user_role_assignments(user_id,role_code) VALUES (:id,'HR_RECRUITER')"), {'id': DEMO_USER_ID})
        for position, code, title in ((SOURCE_ID, SOURCE_CODE, 'Kỹ sư Backend Python — giả'), (TARGET_ID, TARGET_CODE, 'Kỹ sư API — giả')):
            conn.execute(text("""INSERT INTO app_private.positions(position_id,position_code,title,org_unit,work_location,work_mode,created_by,application_deadline_at)
                VALUES (:id,:code,:title,'Nhóm demo giả','Hà Nội (demo)','Hybrid',:hr,now()+interval '30 days')"""), {'id': position, 'code': code, 'title': title, 'hr': DEMO_USER_ID})
            conn.execute(text("INSERT INTO app_private.position_assignments(position_id,user_id,position_role) VALUES (:id,:hr,'HR_RECRUITER')"), {'id': position, 'hr': DEMO_USER_ID})
            jd = conn.execute(text("""INSERT INTO app_private.jd_versions(position_id,version_number,content_text,created_by)
                VALUES (:id,1,'JD TỔNG HỢP: xây dựng API Python, kiểm thử và làm việc với PostgreSQL. Không phải tin tuyển dụng thật.',:hr) RETURNING jd_version_id"""), {'id': position, 'hr': DEMO_USER_ID}).scalar_one()
            criteria = conn.execute(text("""INSERT INTO app_private.criteria_versions(position_id,jd_version_id,version_number,status)
                VALUES (:id,:jd,1,'APPROVED') RETURNING criteria_version_id"""), {'id': position, 'jd': jd}).scalar_one()
            conn.execute(text("""INSERT INTO app_private.criteria_items(criteria_version_id,name,description,category,weight_in_group)
                VALUES (:id,'Python (giả)','Tiêu chí minh họa, chưa được HR phê duyệt nghiệp vụ.','MUST_HAVE',100)"""), {'id': criteria})
        application, document = str(uuid4()), str(uuid4())
        conn.execute(text("INSERT INTO app_private.applications(application_id,position_id,source_code) VALUES (:app,:pos,'CAREERS_DEMO')"), {'app': application, 'pos': SOURCE_ID})
        conn.execute(text("INSERT INTO app_private.application_identities(application_id,display_name,email) VALUES (:app,'Ứng viên giả An','an@example.invalid')"), {'app': application})
        conn.execute(text("""INSERT INTO app_private.application_documents(document_id,application_id,bucket,storage_path,original_filename,mime_type,size_bytes,file_processing_status)
            VALUES (:doc,:app,:bucket,:path,'cv-gia.docx','application/vnd.openxmlformats-officedocument.wordprocessingml.document',:size,'COMPLETED')"""),
            {'doc': document, 'app': application, 'bucket': settings.SUPABASE_STORAGE_BUCKET_CV, 'path': relative, 'size': len(synthetic_cv())})
        conn.execute(text("""INSERT INTO app_private.talent_pool_demo_consents(application_id,notice_version,token_hash,expires_at)
            VALUES (:app,'synthetic-demo-v1',:token,now()+interval '7 days')"""), {'app': application, 'token': hashlib.sha256(os.urandom(32)).hexdigest()})
        path.parent.mkdir(parents=True, exist_ok=True)
        with path.open('xb') as stream:
            stream.write(synthetic_cv())
    print('Seeded two synthetic jobs and one synthetic opted-in candidate. No real data used.')


if __name__ == '__main__':
    main()
