#!/usr/bin/env python3
"""Execute only the confirmed synthetic IT-0005 DEP-02 case after consent.

Permanently deletes the application and its CV artifacts. The script verifies
role, case, position, application and due status before asking for consent.
Run interactively from backend directory; never retry after an unknown result
without checking the database and storage first.
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
        with urllib.request.urlopen(req, timeout=120) as response:
            return response.status, json.loads(response.read() or b"{}")
    except urllib.error.HTTPError as exc:
        exc.close()
        return exc.code, {}


def main():
    if not sys.stdin.isatty():
        print("Can terminal tuong tac.")
        return 1
    env = Path.cwd() / ".env"
    if not env.is_file():
        print("Khong tim thay backend/.env.")
        return 1
    config = dotenv_values(env, encoding="utf-8-sig")
    base = (config.get("SUPABASE_URL") or "").rstrip("/")
    key = config.get("SUPABASE_ANON_KEY")
    parsed = urlparse(base)
    if parsed.scheme != "https" or parsed.netloc != PROJECT or parsed.path or not key:
        print("Sai project test hoac thieu SUPABASE_ANON_KEY. Dung lai.")
        return 1
    print("CANH BAO: Lenh nay XOA VINH VIEN CV va du lieu ho so thu nghiem IT-0005.")
    print("Khong tac dong IT-0006. Se hoi xac nhan truoc khi xoa.")
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
        print("Tai khoan can doi mat khau tren giao dien. Dung lai.")
        return 1
    roles = set(profile.get("system_roles", []))
    if "HR_LEAD" not in roles or "ADMIN" in roles:
        print("Can tai khoan HR_LEAD khong co vai tro ADMIN. Dung lai.")
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
            or case.get("status") != "SCHEDULED_FOR_DELETION" or case.get("is_due") is not True):
        print("Case khong con dung trang thai du kien; chua gui execute. Dung lai.")
        return 1
    print("Thao tac khong the hoan tac: xoa CV goc, text/pages va du lieu ho so IT-0005.")
    if input("Nhap XOA VINH VIEN IT-0005 de xoa, hoac Enter de dung: ").strip() != "XOA VINH VIEN IT-0005":
        print("Da dung, chua gui execute.")
        return 0
    # F2.07: the purge needs a one-time code sent to the confirming user.
    status, challenge = request("POST", f"{API}/retention/cases/{CASE}/purge-otp", headers)
    if status != 200 or not isinstance(challenge, dict) or not challenge.get("challenge_id"):
        print(f"Khong lay duoc ma OTP: HTTP {status}. Chua gui execute.")
        return 1
    otp = input("Nhap ma OTP 6 so vua nhan qua email, hoac Enter de dung: ").strip()
    if not otp:
        print("Da dung, chua gui execute.")
        return 0
    status, result = request("POST", f"{API}/retention/cases/{CASE}/execute", headers,
                             {"challenge_id": challenge["challenge_id"], "otp": otp})
    state = result.get("status") if isinstance(result, dict) else None
    print(f"Execute HR Lead: HTTP {status}, status={state}")
    if status != 200 or state != "DELETED":
        print("Chua xac nhan duoc ket qua. Khong chay lai; kiem tra DB va storage truoc.")
        return 1
    print("Execute da tra DELETED; can doi chieu DB, storage va audit de ket luan.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDa dung. Neu execute da gui, khong chay lai; kiem tra DB va storage truoc.")
        raise SystemExit(130)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Loi ({type(exc).__name__}). Neu execute da gui, khong chay lai; kiem tra DB va storage truoc.")
        raise SystemExit(1)
