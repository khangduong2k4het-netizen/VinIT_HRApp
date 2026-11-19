"""Position scopes shared by QA and duplicate review; checked on every request."""
from fastapi import HTTPException
from sqlalchemy import text


def has_scope(db, user_id: str, position_id: str, *, quality: bool = False) -> bool:
    global_roles = ['HR_LEAD'] if quality else ['ADMIN', 'HR_LEAD']
    position_roles = ['HR_LEAD'] if quality else ['HR_RECRUITER', 'HR_LEAD']
    return bool(db.execute(text("""
        SELECT EXISTS (SELECT 1 FROM app_private.user_profiles WHERE user_id=:u AND account_status='ACTIVE')
          AND (EXISTS (SELECT 1 FROM app_private.user_role_assignments
                       WHERE user_id=:u AND revoked_at IS NULL AND role_code=ANY(:gr))
            OR EXISTS (SELECT 1 FROM app_private.position_assignments
                       WHERE user_id=:u AND position_id=CAST(:p AS uuid) AND revoked_at IS NULL
                         AND position_role=ANY(:pr)))
    """), {'u': user_id, 'p': position_id, 'gr': global_roles, 'pr': position_roles}).scalar_one())


def require_scope(db, user_id: str, position_id: str, *, quality: bool = False):
    # Hold current membership through commit so role/account revocation cannot
    # race a mutation or a source-file download authorised by this transaction.
    db.execute(text('SELECT user_id FROM app_private.user_profiles WHERE user_id=:u FOR SHARE'), {'u': user_id}).all()
    db.execute(text('SELECT user_id FROM app_private.user_role_assignments WHERE user_id=:u AND revoked_at IS NULL FOR SHARE'), {'u': user_id}).all()
    db.execute(text('SELECT user_id FROM app_private.position_assignments WHERE user_id=:u AND position_id=:p AND revoked_at IS NULL FOR SHARE'),
               {'u': user_id, 'p': position_id}).all()
    if not has_scope(db, user_id, position_id, quality=quality):
        raise HTTPException(403, 'Chỉ HR Lead có quyền kiểm định' if quality else 'Bạn không có quyền với vị trí này')


def audit(db, user_id: str, action: str, object_type: str, object_id: str, position_id: str):
    db.execute(text("""
        INSERT INTO app_private.audit_events(actor_user_id,action_type,object_type,object_id,position_id,outcome)
        VALUES (:u,:a,:t,:id,:p,'SUCCESS')
    """), {'u': user_id, 'a': action, 't': object_type, 'id': str(object_id), 'p': position_id})
