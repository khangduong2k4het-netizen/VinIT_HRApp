"""Load a labelled synthetic CV/JD dataset through the real API and compare rankings with the labels.

Dataset layout (see cv_fake/):
    jobs_en.json            {"jobs": [{"id", "title", "description", "requirements", ...}]}
    bang_cv_jd.md           table: ma_jd | phu_hop | khong_phu_hop | khong_lien_quan (markdown links to PDFs)
    phu_hop/ khong_phu_hop/ khong_lien_quan/   one CV per job in each label folder

For every job the script acts like the users would: HR creates the position,
asks the configured AI for draft criteria, HR and HM approve them, HR uploads
the three CVs, the worker assesses and ranks. It then reports whether the
ranking agrees with the labels (phu_hop > khong_phu_hop > khong_lien_quan).

Only for synthetic data on a local/test server. Usage (from backend/):
    python scripts/run_labelled_dataset.py --dataset ../cv_fake --users-file path/to/users.json [--limit 1]
users.json: {"hr": {"email", "password"}, "hm": {"email", "password"}}
"""
from __future__ import annotations

import argparse
import json
import re
import sys
import time
from pathlib import Path
from urllib.parse import unquote

import httpx

LABELS = ("phu_hop", "khong_phu_hop", "khong_lien_quan")
MARKER = "[CVFAKE]"  # prefix on position titles so reruns can skip loaded jobs


def parse_label_table(path: Path) -> dict[str, dict[str, dict]]:
    """ma_jd -> label -> {"name", "file"}"""
    table: dict[str, dict[str, dict]] = {}
    for line in path.read_text(encoding="utf-8").splitlines():
        cells = [c.strip() for c in line.strip().strip("|").split("|")]
        if len(cells) != 4 or not re.fullmatch(r"`[0-9a-f]+`", cells[0]):
            continue
        row = {}
        for label, cell in zip(LABELS, cells[1:]):
            m = re.fullmatch(r"\[(.+?)\]\((.+)\)", cell)
            if m:
                row[label] = {"name": m.group(1), "file": unquote(m.group(2))}
        table[cells[0].strip("`")] = row
    return table


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dataset", required=True, type=Path)
    parser.add_argument("--users-file", required=True, type=Path)
    parser.add_argument("--api", default="http://127.0.0.1:8000/v1")
    parser.add_argument("--limit", type=int, default=None, help="Only the first N jobs")
    parser.add_argument("--marker", default=MARKER, help="Title prefix for this run, e.g. [CVFAKE-OPENAI]")
    parser.add_argument("--report", type=Path, default=None, help="Write the JSON report here")
    args = parser.parse_args()
    sys.stdout.reconfigure(encoding="utf-8")

    if not re.match(r"https?://(127\.0\.0\.1|localhost)[:/]", args.api):
        print("Refusing a non-local API: this script is for synthetic data on a local server.", file=sys.stderr)
        return 2

    jobs = json.loads((args.dataset / "jobs_en.json").read_text(encoding="utf-8"))["jobs"]
    labels = parse_label_table(args.dataset / "bang_cv_jd.md")
    users = json.loads(args.users_file.read_text(encoding="utf-8"))
    api = httpx.Client(base_url=args.api, timeout=180)

    def login(key: str) -> dict:
        r = api.post("/auth/login", json=users[key])
        r.raise_for_status()
        return {"Authorization": f"Bearer {r.json()['access_token']}"}

    hr, hm = login("hr"), login("hm")
    hm_id = api.get("/auth/me", headers=hm).json()["user_id"]
    departments = api.get("/departments", headers=hr).json()
    if not departments:
        print("No department exists; an Admin must create one first.", file=sys.stderr)
        return 1
    department_id = departments[0]["department_id"]
    existing = {p["title"]: p for p in api.get("/positions", headers=hr, params={"page_size": 100}).json()}

    results = []
    for job in jobs[: args.limit]:
        row = labels.get(job["id"])
        title = f"{args.marker} {job['title']} — {job.get('company') or ''}".strip(" —")[:200]
        entry = {"job_id": job["id"], "title": job["title"], "company": job.get("company")}
        results.append(entry)
        if not row or len(row) != 3:
            entry["error"] = "no complete label row"
            continue
        position_id = existing[title]["position_id"] if title in existing else None
        if position_id and api.get("/applications", headers=hr, params={"position_id": position_id}).json():
            print(f"= {job['title']}: already loaded, reading results")
        else:
            # New job, or one left half-way by an earlier run: finish the missing steps.
            if not position_id:
                skills = job.get("skills")
                if isinstance(skills, list):
                    skills = ", ".join(str(s) for s in skills)
                jd = "\n\n".join(str(part).strip() for part in (
                    job.get("description"), job.get("requirements"), f"Skills: {skills}" if skills else None) if part)
                created = api.post("/positions", headers=hr, json={"department_id": department_id, "title": title,
                                                                   "jd_content": jd, "hiring_manager_user_id": hm_id})
                if created.status_code != 201:
                    entry["error"] = f"create position: {created.status_code} {created.text[:200]}"
                    print("!", job["title"], entry["error"]); continue
                position_id = created.json()["position_id"]
            versions = api.get(f"/criteria/position/{position_id}/versions", headers=hr)
            if versions.status_code != 200:
                entry["error"] = f"read criteria: {versions.status_code} {versions.text[:200]}"
                print("!", job["title"], entry["error"]); continue
            version = versions.json()[0] if versions.json() else None
            if version is None:
                draft = api.post(f"/criteria/generate/{position_id}", headers=hr)
                if draft.status_code != 202:
                    entry["error"] = f"generate criteria: {draft.status_code} {draft.text[:200]}"
                    print("!", job["title"], entry["error"]); continue
                version = draft.json()
            entry["criteria"] = len(version["criteria"])
            entry["fairness_warnings"] = [w["name"] for w in version.get("fairness_warnings", [])]
            approve = f"/criteria/{version['criteria_version_id']}/approve"
            if version["status"] in ("DRAFT", "PENDING_HR_REVIEW"):
                a1 = api.post(approve, headers=hr, json={"action": "APPROVE"})
                if a1.status_code != 200:
                    entry["error"] = f"HR approve: {a1.status_code} {a1.text[:300]}"
                    print("!", job["title"], entry["error"]); continue
                version = a1.json()
            if version["status"] == "PENDING_HM_APPROVAL":
                a2 = api.post(approve, headers=hm, json={"action": "APPROVE"})
                if a2.status_code != 200:
                    entry["error"] = f"HM approve: {a2.status_code} {a2.text[:300]}"
                    print("!", job["title"], entry["error"]); continue
                version = a2.json()
            if version["status"] != "APPROVED":
                entry["error"] = f"criteria not approved (status {version['status']})"
                print("!", job["title"], entry["error"]); continue
            files = []
            for label in LABELS:
                content = (args.dataset / row[label]["file"]).read_bytes()
                files.append(("files", (row[label]["name"].replace(" ", "_") + ".pdf", content, "application/pdf")))
            upload = api.post(f"/applications/upload-batch/{position_id}", headers=hr, files=files)
            if upload.status_code != 202:
                entry["error"] = f"upload: {upload.status_code} {upload.text[:200]}"
                print("!", job["title"], entry["error"]); continue
            entry["operation_id"] = upload.json()["operation_id"]
            print(f"+ {job['title']}: {entry['criteria']} criteria, 3 CVs queued")
        entry["position_id"] = position_id

    # Wait for the worker (one operation at a time).
    pending = [e for e in results if e.get("operation_id")]
    deadline = time.time() + 60 * 30
    while pending and time.time() < deadline:
        for e in list(pending):
            status = api.get(f"/operations/{e['operation_id']}", headers=hr).json()
            if status["status"] in ("COMPLETED", "FAILED"):
                e["operation_status"] = status["status"]
                pending.remove(e)
        if pending:
            time.sleep(3)
    for e in pending:
        e["operation_status"] = "TIMEOUT"

    # Compare rankings with labels.
    top1 = pairs_ok = pairs_total = evaluated = 0
    status_by_label = {label: {} for label in LABELS}
    for e in results:
        if not e.get("position_id") or e.get("error"):
            continue
        row = labels[e["job_id"]]
        apps = api.get("/applications", headers=hr, params={"position_id": e["position_id"]}).json()
        by_file = {}
        for app in apps:
            for doc in app.get("documents", []):
                by_file[doc["original_filename"]] = app["application_id"]
        ranking = {r["application_id"]: r for r in api.get(f"/assessments/ranking/latest/{e['position_id']}", headers=hr).json()}
        scored = {}
        for label in LABELS:
            app_id = by_file.get(row[label]["name"].replace(" ", "_") + ".pdf")
            r = ranking.get(app_id) if app_id else None
            scored[label] = {"candidate": row[label]["name"], "rank": r and r["rank_number"],
                             "score": r and r["matching_score"], "coverage": r and r["evidence_coverage"],
                             "status": (r and r["matching_status"]) or "NOT_RANKED"}
            status_by_label[label][scored[label]["status"]] = status_by_label[label].get(scored[label]["status"], 0) + 1
        e["candidates"] = scored

        def key(label):  # higher is better; unranked/None sorts last
            s = scored[label]
            return (s["status"] == "MEETS_MANDATORY", s["score"] if s["score"] is not None else -1.0)

        evaluated += 1
        e["top1_correct"] = key("phu_hop") > max(key("khong_phu_hop"), key("khong_lien_quan"))
        top1 += e["top1_correct"]
        for better, worse in (("phu_hop", "khong_phu_hop"), ("phu_hop", "khong_lien_quan"), ("khong_phu_hop", "khong_lien_quan")):
            pairs_total += 1
            pairs_ok += key(better) > key(worse)

    summary = {"jobs_evaluated": evaluated, "jobs_with_errors": sum(1 for e in results if e.get("error")),
               "top1_accuracy": round(top1 / evaluated, 3) if evaluated else None,
               "pairwise_accuracy": round(pairs_ok / pairs_total, 3) if pairs_total else None,
               "matching_status_by_label": status_by_label}
    print("\n=== Kết quả theo JD (điểm: phù hợp / không phù hợp / không liên quan) ===")
    for e in results:
        if e.get("candidates"):
            c = e["candidates"]
            print(f"{'OK ' if e['top1_correct'] else 'SAI'} {e['title'][:48]:48} "
                  + " / ".join(f"{c[l]['score'] if c[l]['score'] is not None else '—'} ({c[l]['status'][:5]})" for l in LABELS))
        else:
            print(f"LỖI {e['title'][:48]:48} {e.get('error') or e.get('operation_status')}")
    print("\n=== Tổng hợp ===")
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if args.report:
        args.report.write_text(json.dumps({"summary": summary, "jobs": results}, ensure_ascii=False, indent=2, default=str), encoding="utf-8")
        print("report:", args.report)
    return 0


if __name__ == "__main__":
    sys.exit(main())
