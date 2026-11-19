#!/usr/bin/env python3
"""DEP-02 test, phase 2: recruiter authorization and admin audit verify.

Never calls confirm with a privileged user, and never calls execute. If the
recruiter unexpectedly has permission, confirm might schedule the test case;
the script reports that and stops. Run interactively from backend directory.
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
CASE = "2d9407c8-deb6-4b3d-9bb1-92ce50afa2ea"
POSITION = "7c789422-95f1-4083-bc1c-c55142ef4028"
RECRUITER = "86f869cc-4e8c-4d92-a73d-3e718e017e8c"


def request(method, url, headers, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code, {}


def login(base, key, label):
    print(f"\nDang nhap {label}:")
    email = input("Email (chi dia chi, khong nhap link): ").strip()
    if email.count("@") != 1 or any(c in email for c in " []()<>\t"):
        print("Email khong hop le.")
        return None, None
    password = getpass.getpass("Mat khau (nhap an): ")
    status, body = request("POST", base + "/auth/v1/token?grant_type=password",
                           {"apikey": key, "Content-Type": "application/json"},
                           {"email": email, "password": password})
    del password
    token = body.get("access_token") if isinstance(body, dict) else None
    if status != 200 or not token:
        print(f"Dang nhap that bai: HTTP {status}")
        return None, None
    headers = {"Authorization": f"Bearer {token}"}
    status, profile = request("GET", API + "/auth/me", headers)
    if status != 200 or not isinstance(profile, dict):
        print(f"Khong kiem tra duoc vai tro: HTTP {status}")
        return None, None
    if profile.get("must_change_password") is not False:
        print("Tai khoan can doi mat khau tren giao dien truoc khi kiem tra quyen. Dung lai.")
        return None, None
    print("Dang nhap OK; vai tro:", ", ".join(profile.get("system_roles", [])) or "(khong co)")
    return headers, profile


def main():
    if not sys.stdin.isatty():
        print("Can terminal tuong tac de nhap mat khau an toan.")
        return 1
    path = Path.cwd() / ".env"
    if not path.is_file():
        print("Khong tim thay backend/.env.")
        return 1
    config = dotenv_values(path, encoding="utf-8-sig")
    base = (config.get("SUPABASE_URL") or "").rstrip("/")
    key = config.get("SUPABASE_ANON_KEY")
    parsed = urlparse(base)
    if parsed.scheme != "https" or parsed.netloc != PROJECT or parsed.path or not key:
        print("Sai project test hoac thieu SUPABASE_ANON_KEY. Dung lai.")
        return 1
    print("DEP-02: kiem tra quyen Recruiter va audit. Khong thuc hien xoa.")
    print("Neu Recruiter co quyen sai, lenh thu confirm co the len lich xoa; script se dung.")
    recruiter, profile = login(base, key, "HR Recruiter khong co grant xoa")
    if not recruiter:
        return 1
    roles = set(profile.get("system_roles", []))
    if profile.get("user_id") != RECRUITER or "HR_RECRUITER" not in roles or roles & {"ADMIN", "HR_LEAD"}:
        print("Sai tai khoan Recruiter test; chua goi confirm. Dung lai.")
        return 1
    if any(a.get("position_id") == POSITION and a.get("position_role") == "HR_LEAD"
           for a in profile.get("position_assignments", [])):
        print("Recruiter duoc gan HR Lead tren vi tri nay; chua goi confirm. Dung lai.")
        return 1
    status, _ = request("GET", API + "/admin/audit/verify", recruiter)
    print(f"Audit Recruiter: HTTP {status} (ky vong 403)")
    if status != 403:
        print("Quyen audit khong dung ky vong; dung lai.")
        return 1
    status, body = request("POST", f"{API}/retention/cases/{CASE}/confirm", recruiter)
    print(f"Confirm Recruiter: HTTP {status} (ky vong 403)")
    if status != 403:
        if isinstance(body, dict) and body.get("status"):
            print("Trang thai case tra ve:", body["status"])
        print("Quyen confirm khong dung ky vong; dung lai, khong xoa.")
        return 1
    admin, profile = login(base, key, "Admin")
    if not admin or "ADMIN" not in set(profile.get("system_roles", [])):
        print("Chua xac minh duoc tai khoan Admin; dung lai.")
        return 1
    status, result = request("GET", API + "/admin/audit/verify", admin)
    if status != 200 or not isinstance(result, dict):
        print(f"Audit Admin: HTTP {status} (ky vong 200)")
        return 1
    print(f"Audit Admin: HTTP {status}, valid={result.get('valid')}, "
          f"checked_events={result.get('checked_events')}, broken_events={result.get('broken_events')}")
    if result.get("valid") is not True:
        print("Audit khong hop le; dung lai, khong sua audit rows.")
        return 1
    print("HOAN TAT KIEM TRA QUYEN VA AUDIT; CHUA XAC NHAN HOAC XOA")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDa dung; neu confirm da gui, can kiem tra case truoc khi thu lai.")
        raise SystemExit(130)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Loi ket noi/du lieu ({type(exc).__name__}); kiem tra case truoc khi thu lai.")
        raise SystemExit(1)
