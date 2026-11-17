#!/usr/bin/env python3
"""Manually reconcile old synthetic career uploads; never logs identifiers.

Dry-run by default. Execution changes DB and Storage; use only after the
operator confirms target DB/Storage, drains intake, and approves the plan.
"""
import argparse
import json
import re
import sys
from pathlib import Path
from urllib.parse import urlsplit

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from app.core.config import settings  # noqa: E402
from app.services.careers_reconciliation import dry_run, reconcile  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description='Đối soát upload careers tổng hợp; mặc định chỉ đếm.')
    parser.add_argument('--older-than-hours', type=int, default=24)
    parser.add_argument('--limit', type=int, default=20)
    parser.add_argument('--execute', action='store_true')
    parser.add_argument('--confirm', default='')
    parser.add_argument('--expected-project-ref', default='')
    args = parser.parse_args()
    if not 24 <= args.older_than_hours <= 8760 or not 1 <= args.limit <= 100:
        print('Giới hạn hợp lệ: tuổi 24–8760 giờ, số lượng 1–100.', file=sys.stderr)
        return 2
    if args.execute:
        hostname = urlsplit(settings.SUPABASE_URL or '').hostname or ''
        # Check Storage target only. DB connection still needs independent operator verification.
        if (settings.STORAGE_BACKEND != 'supabase' or settings.PUBLIC_CAREERS_TEST_INTAKE_ENABLED
                or args.confirm != 'RECONCILE_SYNTHETIC_CAREERS_UPLOADS'
                or not re.fullmatch(r'[a-z0-9]{20}', args.expected_project_ref)
                or hostname != f'{args.expected_project_ref}.supabase.co'):
            print('Từ chối: xác nhận đích Storage, tắt intake và tham số an toàn trước khi chạy.', file=sys.stderr)
            return 2
    try:
        result = reconcile(older_hours=args.older_than_hours, limit=args.limit) if args.execute else dry_run(older_hours=args.older_than_hours)
    except Exception as exc:
        # Connection/storage exceptions can contain secrets or paths.
        print(f'Đối soát không thành công ({type(exc).__name__}).', file=sys.stderr)
        return 1
    print(json.dumps(result, ensure_ascii=False))
    return 1 if result.get('error') else 0


if __name__ == '__main__':
    raise SystemExit(main())
