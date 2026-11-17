"""Operator-triggered reconciliation of abandoned synthetic intake objects.

Never call this automatically: it deletes objects. Transactions lock each
receipt, so an in-flight intake owning that receipt is skipped. Counts only.
"""
from sqlalchemy import text

from app.db.database import SessionLocal
from app.services.careers_storage import destination, remove


def _validate(older_hours: int, limit: int = 1) -> None:
    if (isinstance(older_hours, bool) or not isinstance(older_hours, int) or not 24 <= older_hours <= 8760
            or isinstance(limit, bool) or not isinstance(limit, int) or not 1 <= limit <= 100):
        raise ValueError('Unsafe reconciliation bounds')


def dry_run(*, older_hours: int) -> dict:
    _validate(older_hours)
    backend, bucket, identity = destination()
    with SessionLocal() as db:
        row = db.execute(text("""SELECT count(*) AS stale,
            count(*) FILTER (WHERE storage_backend=:backend AND storage_bucket=:bucket AND storage_identity=:identity) AS matching_destination,
            count(*) FILTER (WHERE storage_backend IS NULL OR storage_bucket IS NULL OR storage_identity IS NULL) AS missing_destination
            FROM app_private.careers_intake_receipts WHERE state='STAGING'
              AND updated_at < clock_timestamp() - make_interval(hours => :hours)"""),
            {'backend': backend, 'bucket': bucket, 'identity': identity, 'hours': older_hours}).mappings().one()
        return dict(row)


def reconcile(*, older_hours: int, limit: int) -> dict:
    """Remove a bounded number of old objects, mark receipts ABANDONED.

    An ambiguous delete or DB failure stops the batch and leaves STAGING so a
    later operator can safely retry. Rows with unknown destination are skipped.
    """
    _validate(older_hours, limit)
    backend, bucket, identity = destination()
    processed = 0
    for _ in range(limit):
        db = SessionLocal()
        try:
            row = db.execute(text("""SELECT request_id,position_id,storage_path FROM app_private.careers_intake_receipts
                WHERE state='STAGING' AND storage_backend=:backend AND storage_bucket=:bucket AND storage_identity=:identity
                  AND updated_at < clock_timestamp() - make_interval(hours => :hours)
                ORDER BY updated_at,request_id LIMIT 1 FOR UPDATE SKIP LOCKED"""),
                {'backend': backend, 'bucket': bucket, 'identity': identity, 'hours': older_hours}).mappings().first()
            if not row:
                return {'abandoned': processed, 'error': False}
            # Do not remove any path already referenced by an application.
            referenced = db.execute(text("""SELECT 1 FROM app_private.application_documents
                WHERE bucket=:bucket AND storage_path=:path LIMIT 1"""), {'bucket': bucket, 'path': row['storage_path']}).first()
            if referenced:
                db.rollback()
                return {'abandoned': processed, 'error': True}
            remove(backend, bucket, identity, row['storage_path'])
            db.execute(text("""UPDATE app_private.careers_intake_receipts
                SET state='ABANDONED',updated_at=clock_timestamp() WHERE request_id=:req AND state='STAGING'"""), {'req': row['request_id']})
            db.execute(text("""INSERT INTO app_private.audit_events(action_type,object_type,object_id,position_id,outcome)
                VALUES ('CAREERS_TEST_RECONCILE','INTAKE_RECEIPT',:id,:pos,'SUCCESS')"""), {'id': row['request_id'], 'pos': row['position_id']})
            db.commit()
            processed += 1
        except Exception:
            db.rollback()
            return {'abandoned': processed, 'error': True}
        finally:
            db.close()
    return {'abandoned': processed, 'error': False}
