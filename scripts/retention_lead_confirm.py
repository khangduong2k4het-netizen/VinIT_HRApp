#!/usr/bin/env python3
"""Confirm the specific synthetic DEP-02 case, with an explicit prompt.

Does not call execute or delete. Run interactively from backend directory.
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
POSITION = "7c789422-95f1-4083-bc1c-c55142ef4028"
CASE = "2d9407c8-deb6-4b3d-9bb1-92ce50afa2ea"
APPLICATION = "ea6bd426-6745-4c64-bf69-88d7d4210ce8"


def request(method, url, headers, payload=None):
    data = json.dumps(payload).encode() if payload is not None else None
    req = urllib.request.Request(url, data=data, headers=headers, method=method)
    try:
        with urllib.request.urlopen(req, timeout=30) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code, {}


def main():
    if not sys.stdin.isatty():
        print("Can terminal tuong tac.")
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
    print("Chi xac nhan case thu nghiem IT-0005; khong thuc hien xoa.")
    email = input("Email HR Lead (chi dia chi): ").strip()
    if email.count("@") != 1 or any(c in email for c in " []()<>\t"):
        print("Email khong hop le.")
        return 1
    password = getpass.getpass("Mat khau (nhap an): ")
    status, body = request("POST", base + "/auth/v1/token?grant_type=password",
                           {"apikey": key, "Content-Type": "application/json"},
                           {"email": email, "password": password})
    del password
    token = body.get("access_token") if isinstance(body, dict) else None
    if status != 200 or not token:
        print(f"Dang nhap that bai: HTTP {status}")
        return 1
    headers = {"Authorization": f"Bearer {token}"}
    status, profile = request("GET", API + "/auth/me", headers)
    if status != 200 or not isinstance(profile, dict):
        print(f"Khong kiem tra duoc vai tro: HTTP {status}")
        return 1
    if profile.get("must_change_password") is not False:
        print("Tai khoan can doi mat khau tren giao dien truoc khi tiep tuc. Dung lai.")
        return 1
    roles = set(profile.get("system_roles", []))
    if "HR_LEAD" not in roles or "ADMIN" in roles:
        print("Can tai khoan HR_LEAD khong co vai tro ADMIN de kiem thu. Dung lai.")
        return 1
    print("Dang nhap OK; vai tro HR_LEAD")
    status, cases = request("GET", f"{API}/retention/positions/{POSITION}/cases", headers)
    if status != 200 or not isinstance(cases, list):
        print(f"Khong doc duoc case: HTTP {status}")
        return 1
    matches = [item for item in cases if item.get("retention_case_id") == CASE]
    if len(matches) != 1:
        print("Khong tim thay dung case thu nghiem. Dung lai.")
        return 1
    case = matches[0]
    print(f"IT-0005: case={CASE}, status={case.get('status')}, is_due={case.get('is_due')}")
    if (case.get("application_id") != APPLICATION or case.get("position_id") != POSITION
            or case.get("status") != "PENDING" or case.get("is_due") is not True):
        print("Case khong con dung trang thai du kien; chua gui confirm. Dung lai.")
        return 1
    print("Xac nhan se chuyen case sang lich xoa; file/CV chua bi xoa o buoc nay.")
    if input("Nhap XAC NHAN IT-0005 de tiep tuc, hoac Enter de dung: ").strip() != "XAC NHAN IT-0005":
        print("Da dung, chua gui confirm.")
        return 0
    status, result = request("POST", f"{API}/retention/cases/{CASE}/confirm", headers)
    state = result.get("status") if isinstance(result, dict) else None
    print(f"Confirm HR Lead: HTTP {status}, status={state}")
    if status != 200 or state != "SCHEDULED_FOR_DELETION":
        print("Khong dat ky vong; kiem tra trang thai truoc khi thu lai.")
        return 1
    print("HOAN TAT CONFIRM; CHUA XOA")
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
