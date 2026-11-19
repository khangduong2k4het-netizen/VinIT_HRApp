#!/usr/bin/env python3
"""Check and revoke the single synthetic IT-0004 shortlist for E2E-09.

Run interactively from backend. Reads HM access before and after a specifically
confirmed revoke, and never prints tokens, response bodies or signed URLs.
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
POSITION = "c65ed290-c3c5-4ae2-9fc4-a81906b3b683"
SHARE = "c790ccb5-2122-4f7d-8176-47d4fe3907bc"
HM = "cbf2b66e-bc69-4552-8066-63081e53ac7c"
SHARED = "cf9cacff-9310-452b-9fa5-f97cac31abb8"
UNSHARED = "0901b740-8e33-4af9-9789-484695538ab0"


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
    email = input("Email (chi dia chi): ").strip()
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
        print("Tai khoan can doi mat khau tren giao dien. Dung lai.")
        return None, None
    print("Dang nhap OK; vai tro:", ", ".join(profile.get("system_roles", [])) or "(khong co)")
    return headers, profile


def check(label, actual, expected):
    print(f"{label}: HTTP {actual} (ky vong {expected})")
    return actual == expected


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
    print("E2E-09: kiem tra quyen shortlist IT-0004; se hoi truoc khi thu hoi.")
    hm, profile = login(base, key, "Hiring Manager duoc chia se")
    if not hm:
        return 1
    roles = set(profile.get("system_roles", []))
    if profile.get("user_id") != HM or "HIRING_MANAGER" not in roles or roles & {"ADMIN", "HR_LEAD"}:
        print("Sai tai khoan HM hoac co quyen HR/Admin; dung lai.")
        return 1
    assignments = profile.get("position_assignments", [])
    if not any(a.get("position_id") == POSITION and a.get("position_role") == "HIRING_MANAGER" for a in assignments):
        print("HM khong duoc phan cong IT-0004; dung lai.")
        return 1
    status, share = request("GET", f"{API}/shortlist/{SHARE}", hm)
    if not check("HM xem shortlist truoc thu hoi", status, 200) or not isinstance(share, dict):
        return 1
    items = share.get("applications")
    if (share.get("status") != "ACTIVE" or share.get("allow_cv_view") is not False
            or share.get("position_id") != POSITION or share.get("shared_with") != HM
            or not isinstance(items, list) or len(items) != 1
            or items[0].get("application_id") != SHARED
            or not share.get("feedback")):
        print("Noi dung shortlist/feedback khong dung fixture mong doi; dung lai.")
        return 1
    status, shared = request("GET", f"{API}/applications/{SHARED}", hm)
    if not check("HM xem ho so duoc chia se", status, 200) or not isinstance(shared, dict):
        return 1
    if shared.get("can_view_cv") is not False or shared.get("documents"):
        print("Ho so tom tat co quyen CV/document bat thuong; dung lai.")
        return 1
    status, _ = request("GET", f"{API}/applications/{SHARED}/cv-download-url", hm)
    if not check("HM lay link CV goc", status, 403):
        print("Quyen CV khong dung ky vong; dung lai.")
        return 1
    status, _ = request("GET", f"{API}/applications/{UNSHARED}", hm)
    if not check("HM xem ho so khong duoc chia se", status, 403):
        print("Pham vi ho so khong dung ky vong; dung lai.")
        return 1
    admin, profile = login(base, key, "Admin/HR phu trach")
    if not admin or "ADMIN" not in set(profile.get("system_roles", [])):
        print("Can tai khoan Admin; dung lai.")
        return 1
    print("Thu hoi chi shortlist thu nghiem IT-0004; khong xoa ho so hay feedback.")
    if input("Nhap THU HOI IT-0004 de tiep tuc, hoac Enter de dung: ").strip() != "THU HOI IT-0004":
        print("Da dung, chua thu hoi.")
        return 0
    status, result = request("POST", f"{API}/shortlist/{SHARE}/revoke", admin)
    if not check("HR thu hoi", status, 200) or not isinstance(result, dict) or result.get("status") != "REVOKED":
        print("Khong xac nhan duoc ket qua thu hoi; kiem tra trang thai truoc khi chay lai.")
        return 1
    ok = True
    status, _ = request("GET", f"{API}/shortlist/{SHARE}", hm)
    ok = check("HM xem shortlist sau thu hoi", status, 403) and ok
    status, _ = request("GET", f"{API}/applications/{SHARED}", hm)
    ok = check("HM xem ho so sau thu hoi", status, 403) and ok
    status, _ = request("GET", f"{API}/applications/{SHARED}/cv-download-url", hm)
    ok = check("HM lay link CV sau thu hoi", status, 403) and ok
    if not ok:
        print("Quyen sau thu hoi khong dung ky vong; dung lai.")
        return 1
    print("HOAN TAT KIEM TRA API; DOI CHIEU DB VA UI TRUOC KHI KET LUAN")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except KeyboardInterrupt:
        print("\nDa dung; neu da gui thu hoi, kiem tra trang thai truoc khi thu lai.")
        raise SystemExit(130)
    except (urllib.error.URLError, TimeoutError, OSError, ValueError) as exc:
        print(f"Loi ({type(exc).__name__}); neu da gui thu hoi, kiem tra trang thai truoc khi thu lai.")
        raise SystemExit(1)
