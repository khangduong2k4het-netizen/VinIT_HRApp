"""Private career-upload storage helpers. Never print locations or payloads."""
import hashlib
import os
import re
from urllib.parse import urlsplit

from app.core.config import settings
from app.db.supabase import get_supabase_client

PATH_PATTERN = re.compile(r'^careers/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}/[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}\.(pdf|docx)$')
BUCKET_PATTERN = re.compile(r'^[A-Za-z0-9][A-Za-z0-9._-]{0,99}$')


def destination() -> tuple[str, str, str]:
    backend, bucket = settings.STORAGE_BACKEND, settings.SUPABASE_STORAGE_BUCKET_CV
    if not BUCKET_PATTERN.fullmatch(bucket) or bucket in ('.', '..'):
        raise ValueError('Invalid bucket')
    if backend == 'supabase':
        url = urlsplit(settings.SUPABASE_URL or '')
        if url.scheme != 'https' or not url.hostname or url.username or url.password or url.query or url.fragment:
            raise ValueError('Invalid Supabase URL')
        target = (settings.SUPABASE_URL or '').rstrip('/')
    elif backend == 'local':
        target = os.path.realpath(settings.LOCAL_STORAGE_PATH)
    else:
        raise ValueError('Unsupported storage backend')
    return backend, bucket, hashlib.sha256(target.encode()).hexdigest()


def validate_location(backend: str, bucket: str, identity: str, path: str) -> None:
    if (backend, bucket, identity) != destination() or not PATH_PATTERN.fullmatch(path):
        raise ValueError('Stored destination mismatch or invalid path')


def _local_file(bucket: str, path: str) -> str:
    base = os.path.realpath(settings.LOCAL_STORAGE_PATH)
    root = os.path.realpath(os.path.join(base, bucket))
    if os.path.commonpath([base, root]) != base:
        raise ValueError('Bucket escapes storage root')
    parent = os.path.realpath(os.path.join(root, os.path.dirname(path)))
    if os.path.commonpath([root, parent]) != root:
        raise ValueError('Path escapes storage root')
    return os.path.join(parent, os.path.basename(path))


def store(backend: str, bucket: str, identity: str, path: str, content: bytes, mime: str) -> None:
    validate_location(backend, bucket, identity, path)
    if backend == 'supabase':
        client = get_supabase_client()
        if not client:
            raise RuntimeError('Storage unavailable')
        client.storage.from_(bucket).upload(path=path, file=content, file_options={'content-type': mime, 'upsert': 'true'})
    else:
        full_path = _local_file(bucket, path)
        os.makedirs(os.path.dirname(full_path), exist_ok=True)
        temp_path = full_path + '.part'
        fd = os.open(temp_path, os.O_WRONLY | os.O_CREAT | os.O_TRUNC | getattr(os, 'O_NOFOLLOW', 0), 0o600)
        try:
            with os.fdopen(fd, 'wb') as stream:
                stream.write(content)
            os.replace(temp_path, full_path)
        finally:
            if os.path.lexists(temp_path):
                os.unlink(temp_path)


def remove(backend: str, bucket: str, identity: str, path: str) -> None:
    """Only call while owning the locked STAGING receipt transaction."""
    validate_location(backend, bucket, identity, path)
    if backend == 'supabase':
        client = get_supabase_client()
        if not client:
            raise RuntimeError('Storage unavailable')
        from storage3.exceptions import StorageApiError
        # A missing bucket is not proof that the object was deleted.
        client.storage.get_bucket(bucket)
        storage = client.storage.from_(bucket)
        try:
            storage.info(path)
        except StorageApiError as exc:
            if str(exc.status) == '404':
                return
            raise
        storage.remove([path])
        try:
            storage.info(path)
        except StorageApiError as exc:
            if str(exc.status) == '404':
                return
            raise
        raise RuntimeError('Storage object still exists after delete')
    else:
        full_path = _local_file(bucket, path)
        for candidate in (full_path, full_path + '.part'):
            try:
                os.unlink(candidate)
            except FileNotFoundError:
                pass
