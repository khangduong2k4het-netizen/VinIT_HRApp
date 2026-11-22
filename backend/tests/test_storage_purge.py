"""Đối soát Storage: tìm và dọn file mồ côi.

Logic dễ sai nhất không phải "xoá" mà là **phân biệt file với thư mục** khi liệt
kê, và **không xoá file vừa upload**. Hai chỗ đó được test ở đây bằng một
Storage giả, không cần Supabase thật.
"""
from datetime import datetime, timedelta, timezone


from app.services import storage_purge as sp


FILE = "__file__"  # đánh dấu: giá trị này là file, không phải thư mục con


class FakeProxy:
    """Giả lập bucket proxy của storage3: list() trả MỘT cấp mỗi lần.

    Cây thư mục viết dạng {"org1": {"app1": {"a.docx": {FILE: True}}}}.
    Dùng FILE để phân biệt, vì một file cũng là dict nên không thể dựa vào kiểu.
    """

    def __init__(self, tree, refuse=False):
        self.tree = tree
        self.refuse = refuse
        self.removed = []

    def list(self, path=None, options=None):
        if self.refuse:
            raise RuntimeError("network down")
        node = self.tree
        if path:
            for part in path.split("/"):
                node = node[part]
        out = []
        for name, value in node.items():
            if value.get(FILE):
                out.append({
                    "name": name, "id": "obj-" + name,
                    "metadata": {"size": 1}, "created_at": value.get("created_at"),
                })
            else:
                out.append({"name": name, "id": None, "metadata": None, "created_at": None})
        return out

    def remove(self, paths):
        self.removed.extend(paths)
        return [{"name": p} for p in paths]


class FakeStorage:
    def __init__(self, proxies):
        self.proxies = proxies

    def from_(self, bucket):
        return self.proxies[bucket]


class FakeClient:
    def __init__(self, storage):
        self.storage = storage


def _install(monkeypatch, proxies, refuse=False):
    storage = FakeStorage({b: FakeProxy(t, refuse) for b, t in proxies.items()})
    monkeypatch.setattr(sp, "_client", lambda: FakeClient(storage))
    monkeypatch.setattr(sp.settings, "STORAGE_BACKEND", "supabase")
    return storage


class FakeDB:
    """Trả tập đường dẫn 'còn dùng' theo bucket qua hai câu SELECT."""

    def __init__(self, originals=(), extracted=(), busy=0):
        self.originals = list(originals)
        self.extracted = list(extracted)
        self.busy = busy
        self.sql = []

    def execute(self, statement, params=None):
        self.sql.append(str(statement))
        return FakeResult(self)


class FakeResult:
    def __init__(self, db):
        self.db = db

    def mappings(self):
        return self

    def all(self):
        sql = self.db.sql[-1]
        if "application_documents" in sql:
            return [{"bucket": "cv-originals", "storage_path": p} for p in self.db.originals]
        if "document_processing_runs" in sql:
            return [(p,) for p in self.db.extracted]
        return []

    def scalar(self):
        return self.db.busy


def test_list_walks_nested_folders(monkeypatch):
    """list() của storage3 chỉ trả một cấp — phải tự đi xuống."""
    _install(monkeypatch, {
        "cv-originals": {
            "org1": {"app1": {"file1.docx": {FILE: True}, "file2.docx": {FILE: True}}},
        },
        "cv-extracted-text": {},
    })
    files = sp.list_bucket_files("cv-originals")
    assert sorted(f["path"] for f in files) == [
        "org1/app1/file1.docx",
        "org1/app1/file2.docx",
    ]


def test_orphans_are_files_not_referenced_by_db(monkeypatch):
    _install(monkeypatch, {
        "cv-originals": {"o": {"a": {"keep.docx": {FILE: True}, "orphan.docx": {FILE: True}}}},
        "cv-extracted-text": {},
    })
    db = FakeDB(originals=["o/a/keep.docx"])
    result = sp.sweep_orphans(db)
    assert result["deleted"] == 1


def test_referenced_files_are_never_deleted(monkeypatch):
    storage = _install(monkeypatch, {
        "cv-originals": {"o": {"a": {"keep.docx": {FILE: True}}}},
        "cv-extracted-text": {},
    })
    db = FakeDB(originals=["o/a/keep.docx"])
    sp.sweep_orphans(db)
    assert storage.proxies["cv-originals"].removed == []


def test_extracted_pages_json_counts_as_needed(monkeypatch):
    """pages.json đi kèm extracted.txt nên cũng phải được coi là còn dùng."""
    _install(monkeypatch, {
        "cv-originals": {},
        "cv-extracted-text": {"o": {"a": {"extracted.txt": {FILE: True}, "pages.json": {FILE: True}}}},
    })
    db = FakeDB(extracted=["o/a/extracted.txt"])
    result = sp.sweep_orphans(db)
    assert result["deleted"] == 0, "pages.json phải được giữ cùng extracted.txt"


def test_fresh_files_are_spared(monkeypatch):
    """File vừa tạo có thể đang upload — không được xoá."""
    recent = (datetime.now(timezone.utc) - timedelta(minutes=1)).isoformat()
    _install(monkeypatch, {
        "cv-originals": {"o": {"a": {"uploading.docx": {FILE: True, "created_at": recent}}}},
        "cv-extracted-text": {},
    })
    result = sp.sweep_orphans(FakeDB())
    assert result["deleted"] == 0
    assert result["kept_fresh"] == 1


def test_old_orphans_are_deleted(monkeypatch):
    old = (datetime.now(timezone.utc) - timedelta(hours=2)).isoformat()
    _install(monkeypatch, {
        "cv-originals": {"o": {"a": {"old-orphan.docx": {FILE: True, "created_at": old}}}},
        "cv-extracted-text": {},
    })
    result = sp.sweep_orphans(FakeDB())
    assert result["deleted"] == 1


def test_refuses_when_worker_busy(monkeypatch):
    """Xoá file khi worker đang xử lý có thể xoá file vừa upload xong."""
    _install(monkeypatch, {"cv-originals": {}})
    result = sp.sweep_orphans(FakeDB(busy=1))
    assert result["swept"] is False
    assert "operation" in result["reason"].lower()


def test_listing_failure_deletes_nothing(monkeypatch):
    """Không liệt kê được thì thà còn rác hơn xoá nhầm."""
    storage = _install(monkeypatch, {
        "cv-originals": {"o": {"a": {"x.docx": {FILE: True}}}},
        "cv-extracted-text": {},
    })
    for proxy in storage.proxies.values():
        proxy.refuse = True
    result = sp.sweep_orphans(FakeDB())
    assert result["swept"] is False
    assert result["deleted"] == 0


def test_non_supabase_backend_is_noop(monkeypatch):
    monkeypatch.setattr(sp.settings, "STORAGE_BACKEND", "local")
    result = sp.sweep_orphans(FakeDB())
    assert result["swept"] is False


def test_dry_run_reports_without_deleting(monkeypatch):
    storage = _install(monkeypatch, {
        "cv-originals": {"o": {"a": {"orphan.docx": {FILE: True}}}},
        "cv-extracted-text": {},
    })
    result = sp.sweep_orphans(FakeDB(), dry_run=True)
    assert result["deleted"] == 1
    assert storage.proxies["cv-originals"].removed == [], "Dry run không được xoá thật"
