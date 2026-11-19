"""Cross-position warnings. Contacts stay in identity storage, not signal metadata."""
import hashlib
import json
from difflib import SequenceMatcher

from sqlalchemy import text

from app.services.identity_matching import identity_signal, normalize_email, normalize_name, normalize_phone
from app.services.review_access import has_scope


def _career(db, application_id):
    rows = db.execute(text("""
        SELECT f.fact_value FROM app_private.profile_facts f
        WHERE f.profile_version_id=(SELECT profile_version_id FROM app_private.profile_versions
            WHERE application_id=:id AND status='COMPLETED' ORDER BY version_number DESC LIMIT 1)
        ORDER BY f.fact_type,f.fact_value::text
    """), {'id': str(application_id)}).scalars().all()
    return json.dumps(rows, sort_keys=True, ensure_ascii=False)


def _fingerprint(row):
    values = [normalize_email(row.get('email')), normalize_phone(row.get('phone')),
              normalize_name(row.get('display_name')), row.get('career_text', '')]
    return hashlib.sha256(json.dumps(values, ensure_ascii=False).encode()).hexdigest()


def refresh_application(db, application_id: str):
    # A single lock prevents concurrent scans from recreating superseded evidence.
    db.execute(text("SELECT pg_advisory_xact_lock(hashtext('hra:cross-duplicates'))"))
    source = db.execute(text("""
        SELECT a.application_id,a.position_id,i.display_name,i.email,i.phone
        FROM app_private.applications a JOIN app_private.application_identities i USING(application_id)
        WHERE a.application_id=:id
    """), {'id': application_id}).mappings().first()
    if not source:
        return
    source = dict(source)
    source['career_text'] = _career(db, application_id)
    source_fp = _fingerprint(source)
    # No contact/content is returned to the API caller by this internal scan.
    candidates = db.execute(text("""
        SELECT a.application_id,a.position_id,i.display_name,i.email,i.phone
        FROM app_private.applications a JOIN app_private.application_identities i USING(application_id)
        WHERE a.position_id<>:p
    """), {'p': source['position_id']}).mappings()
    current_ids = []
    for candidate in candidates:
        peer = dict(candidate)
        # Only fetch career content for contact or plausible name candidates.
        a, b = normalize_name(source.get('display_name')), normalize_name(peer.get('display_name'))
        if not identity_signal(source, peer) and (len(a.split()) < 2 or len(b.split()) < 2 or
                                                 SequenceMatcher(None, a, b).ratio() < 0.92):
            continue
        peer['career_text'] = _career(db, peer['application_id'])
        signal = identity_signal(source, peer)
        if not signal:
            continue
        first, second = sorted([str(application_id), str(peer['application_id'])])
        peer_fp = _fingerprint(peer)
        fingerprints = {application_id: source_fp, str(peer['application_id']): peer_fp}
        signal_id = db.execute(text("""
            INSERT INTO app_private.cross_position_duplicates(application_id_1,application_id_2,fingerprint_1,fingerprint_2,signal_type,confidence)
            VALUES (:a,:b,:fa,:fb,:t,:c)
            ON CONFLICT (application_id_1,application_id_2,fingerprint_1,fingerprint_2)
            DO UPDATE SET review_status=CASE WHEN cross_position_duplicates.review_status='SUPERSEDED' THEN 'PENDING'
                          ELSE cross_position_duplicates.review_status END
            RETURNING signal_id
        """), {'a': first, 'b': second, 'fa': fingerprints[first], 'fb': fingerprints[second],
                't': signal[0], 'c': signal[1]}).scalar_one()
        current_ids.append(str(signal_id))
    db.execute(text("""
        UPDATE app_private.cross_position_duplicates SET review_status='SUPERSEDED'
        WHERE (application_id_1=:id OR application_id_2=:id) AND review_status<>'SUPERSEDED'
          AND NOT (signal_id=ANY(CAST(:ids AS uuid[])))
    """), {'id': application_id, 'ids': current_ids})


def warnings(db, application_id: str, user_id: str) -> dict:
    rows = db.execute(text("""
        SELECT s.signal_id,s.signal_type,s.confidence,s.review_status,a.application_id,a.position_id,
               a.application_status,a.created_at,p.title AS position_title,p.position_code
        FROM app_private.cross_position_duplicates s
        JOIN app_private.applications a ON a.application_id=CASE WHEN s.application_id_1=:id THEN s.application_id_2 ELSE s.application_id_1 END
        JOIN app_private.positions p ON p.position_id=a.position_id
        WHERE (s.application_id_1=:id OR s.application_id_2=:id) AND s.review_status IN ('PENDING','CONFIRMED')
        ORDER BY a.created_at DESC,s.signal_id
    """), {'id': application_id}).mappings()
    visible, restricted = [], False
    for row in rows:
        if not has_scope(db, user_id, str(row['position_id'])):
            restricted = True
            continue
        item = dict(row)
        item['recruiters'] = [dict(r) for r in db.execute(text("""
            SELECT u.display_name FROM app_private.position_assignments p JOIN app_private.user_profiles u ON u.user_id=p.user_id
            WHERE p.position_id=:p AND p.revoked_at IS NULL AND p.position_role IN ('HR_RECRUITER','HR_LEAD') AND u.account_status='ACTIVE'
            ORDER BY u.display_name
        """), {'p': row['position_id']}).mappings()]
        visible.append(item)
    # Restricted matches expose no IDs, counts, dates, contacts or positions.
    return {'matches': visible, 'has_restricted_matches': restricted}
