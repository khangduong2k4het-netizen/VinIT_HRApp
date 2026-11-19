#!/usr/bin/env python3
"""Interactive DEP-02 test: generate cases only, never confirm or delete.

Run from backend: .venv/bin/python ../scripts/retention_generate.py
Requires python-dotenv, already a backend dependency. Credentials stay in memory.
"""
import getpass
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path
from urllib.parse import urlparse

from dotenv import dotenv_values

PROJECT = "myrymlqdbyqmpynesiwk.supabase.co"
API = "http://127.0.0.1:8005/v1"
POSITIONS = (
    ("IT-0006 Not Due", "a3c8acac-f03c-407b-9163-0263ee9125d0", 0),
    ("IT-0005 Due", "7c789422-95f1-4083-bc1c-c55142ef4028", 1),
)


def request(method, url, headers, payload=None):
    data = json.dumps(payload).encode("utf-8") if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        # Never print raw auth responses or headers, which could contain secrets.
        exc.close()
        return exc.code, {}


def main():
    env_path = Path.cwd() / ".env"
    if not env_path.is_file():
        print("Khong tim thay backend/.env. Hay chay lenh tu thu muc backend.")
        return 1
    config = dotenv_values(env_path, encoding="utf-8-sig")
    url = (config.get("SUPABASE_URL") or "").rstrip("/")
    key = config.get("SUPABASE_ANON_KEY")
    parsed = urlparse(url)
    if parsed.scheme != "https" or parsed.netloc != PROJECT or parsed.path or not key:
        print("Cau hinh Supabase khong dung project test hoac thieu SUPABASE_ANON_KEY. Dung lai.")
        return 1
    print("DEP-02: chi tao case cho IT-0005 va IT-0006; khong xac nhan hay xoa.")
    email = input("Email HR/Admin (chi email, khong nhap link): ").strip()
    if email.count("@") != 1 or any(c in email for c in " []()<>\t"):
        print("Email khong hop le. Chay lai va chi nhap dia chi email.")
        return 1
    if not sys.stdin.isatty():
        print("Can terminal tuong tac de nhap mat khau an toan.")
        return 1
    password = getpass.getpass("Mat khau (nhap an, khong hien ky tu): ")
    status, response = request("POST", url + "/auth/v1/token?grant_type=password",
                               {"apikey": key, "Content-Type": "application/json"},
                               {"email": email, "password": password})
    del password
    token = response.get("access_token")
    if status != 200 or not token:
        print(f"Dang nhap that bai: HTTP {status}. Kiem tra tai khoan hoac key.")
        return 1
    print("Dang nhap: OK")
    headers = {"Authorization": f"Bearer {token}"}
    success = True
    for label, position_id, expected in POSITIONS:
        path = f"{API}/retention/positions/{position_id}/cases"
        status, result = request("POST", path + "/generate", headers)
        if status != 200 or not isinstance(result, dict):
            print(f"{label}: generate HTTP {status} (khong thanh cong)")
            success = False
            continue
        count = result.get("created_count")
        print(f"{label}: HTTP {status}, created_count={count}, due_date={result.get('due_date')}")
        for case in result.get("cases", []):
            print(f"  case={case.get('retention_case_id')}, status={case.get('status')}")
        if count != expected:
            success = False
            # A previous run may have created a case before its output was lost.
            if expected == 1 and count == 0:
                list_status, cases = request("GET", path, headers)
                if list_status == 200 and isinstance(cases, list):
                    for case in cases:
                        print(f"  case da co: {case.get('retention_case_id')}, status={case.get('status')}")
                else:
                    print(f"  Khong doc duoc danh sach case: HTTP {list_status}")
    print("HOAN TAT BUOC GENERATE" if success else "KET QUA CAN KIEM TRA; chua xac nhan hoac xoa")
    return 0 if success else 1


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDa dung; neu generate dang chay, can kiem tra case truoc khi thu lai.")
        raise SystemExit(130)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Loi ket noi/du lieu ({type(exc).__name__}). Neu request generate da gui, kiem tra case truoc khi thu lai.")
        raise SystemExit(1)
