# Phase 1 Closure Review — 2026-11-07

> Mục đích: đối chiếu F1.01–F1.13 theo PRD → API → DB → Source Code → Test → Acceptance Evidence để quyết định đóng Phase 1. Báo cáo này không sửa đè các audit lịch sử. “Có trong code” không đồng nghĩa “đã nghiệm thu”.
>
> Phạm vi kiểm tra ban đầu: branch `arena/ea6e2570-vinit-hrapp`, commit nền `1326acd`, cập nhật sửa điểm tại `57b9072`. Project Supabase đã kết nối: `myrymlqdbyqmpynesiwk`.

> Audit chi tiết các batch nâng cấp: [`audit/UPGRADE_AUDIT_2026-11-07.md`](UPGRADE_AUDIT_2026-11-07.md). Danh sách hạng mục đã sẵn sàng nhưng chưa triển khai/nghiệm thu: [`doc/PENDING_DEPLOYMENT.md`](../doc/PENDING_DEPLOYMENT.md).

## 1. Quy ước trạng thái

| Trạng thái | Ý nghĩa |
|---|---|
| `PASS` | Có implementation và bằng chứng kiểm thử/nghiệm thu tương ứng |
| `PARTIAL` | Đã có implementation nhưng thiếu kiểm thử, vận hành hoặc nghiệm thu đầy đủ |
| `BLOCKED` | Không thể đóng vì còn điều kiện an toàn/dữ liệu/pháp lý/vận hành chưa hoàn thành |
| `NOT TESTED` | Chưa có bằng chứng kiểm thử trên môi trường/dịch vụ thật |

## 2. Bằng chứng môi trường và kiểm thử hiện có

| Hạng mục | Bằng chứng | Trạng thái |
|---|---|---|
| Migration trên project Supabase đã kết nối | Đã kiểm tra danh sách migration tới retention/audit integrity `00012`, remote version `20261107142027` | `PASS` cho project đã kết nối; môi trường đích khác vẫn `NOT TESTED` |
| Backend automated tests | Local full backend trên PostgreSQL dùng một lần đạt **158 passed** sau Batch 5; CI tại run `42380974685` cho commit `cce75b5` đạt cả 3 job | `PARTIAL` — vẫn cần bằng chứng staging riêng |
| GitHub CI | Đã bổ sung `.github/workflows/ci.yml` gồm backend unit, frontend checks và backend integration với PostgreSQL/pgvector dùng một lần; run `42380974685` đạt cả 3 job | `PARTIAL` — còn branch protection nếu quy trình phát hành yêu cầu |
| Retention/audit Batch 5 | Đã triển khai retention workflow từng hồ sơ, audit SHA-256 hash chain/append-only trigger và `GET /v1/admin/audit/verify`; targeted **9 passed**, full backend local **158 passed**, migration sạch local `00001`–`00012` áp đạt; postflight remote xác nhận 21/21 audit events có hash và 0 broken event | `PARTIAL` — chưa chạy workflow qua staging Supabase Auth/Storage và backend đã deploy |
| Supabase Auth/Storage thật | Chưa có E2E staging được ghi nhận đầy đủ | `NOT TESTED` |
| OCR scan thật | Có code và unit test mô phỏng; chưa có bộ hồ sơ scan thật được nghiệm thu | `NOT TESTED` |
| LLM/BGE thật | Có provider và cấu hình; chưa có báo cáo golden set HR trên model/endpoint thật | `NOT TESTED` |
| Legacy Supabase keys | Legacy keys vẫn là hạng mục phải đóng thủ công; connector không có thao tác deactivate legacy/revoke JWT signing secret | `BLOCKED` |

## 3. Traceability F1.01–F1.13

| ID | Yêu cầu | API/Code chính | DB/Migration | Bằng chứng hiện tại | Trạng thái | Việc cần làm để đóng |
|---|---|---|---|---|---|---|
| F1.01 | Vị trí, JD, Hiring Manager | API positions/JD, UI positions | `positions`, `jd_versions`, `position_assignments` | Có tạo/sửa vị trí, lịch sử JD, kiểm tra HM và xung đột phiên bản | `PARTIAL` | Test UI/API trên staging; bổ sung hoặc chấp nhận thiếu UI đổi HM sau tạo |
| F1.02 | Tiêu chí, dual approval, trọng số | API criteria, requirement spec | `criteria_versions`, `criteria_items.requirement_spec` tại 00009 | Có HR/HM hai bước, khóa bản duyệt, spec có cấu trúc | `PARTIAL` | Kiểm thử LLM thật và ma trận quyền phê duyệt |
| F1.03 | Upload batch | API applications/documents | `application_documents`, operations | Giới hạn file/batch, validate PDF/DOCX, theo dõi tiến trình | `PARTIAL` | E2E Storage thật và batch lớn trên staging |
| F1.04 | Trích xuất, OCR, sửa profile | document processor, profile API/UI | profile versions, document processing runs | Có PDF text/DOCX, OCR code, profile versioning | `PARTIAL` | Bộ CV scan thật, đo OCR EN/VI và lỗi trích xuất |
| F1.05 | Đánh giá và dẫn chứng | deterministic engine, LLM fallback, evidence verification | assessment runs/results/evidence | Rule-first, candidate chunks, quote span/page verification | `PARTIAL` | Golden set HR thật; đo false MATCH/NO_MATCH/unresolved |
| F1.06 | Điểm và ranking | `MatchingEngine.calculate_assessment_scores`, `rank_applications` | assessment/ranking runs/items | Đã sửa tại `57b9072`: từ `matching-v2.1`, UNCLEAR bị loại khỏi tử/mẫu của score; coverage là chỉ số riêng; LTR vẫn OFF mặc định | `PARTIAL` | HR/HM xác nhận policy; chạy golden/repeatability sau sửa; train lại LTR nếu sau này dùng |
| F1.07 | Cảnh báo trùng | duplicate detection theo email/phone | duplicate signals | Có tín hiệu trong cùng position, không tự gộp/xóa | `PARTIAL` | Test các trường hợp đổi identifier và dữ liệu thiếu |
| F1.08 | Trạng thái và lịch sử | application status API | status events/audit events | HR cập nhật theo transition, lý do khi loại, AI không tự đổi trạng thái | `PARTIAL` | RBAC matrix và audit integrity |
| F1.09 | Shortlist, feedback, ghi chú HR | shortlist API/UI | shortlist shares/items/feedback | Có chia sẻ HM, quyền xem CV, feedback, thu hồi; ghi chú append-only qua API | `PARTIAL` | Kiểm thử chia sẻ/thu hồi trên staging và quyền HM |
| F1.10 | RBAC, audit, retention | admin/account APIs, audit events, Admin LTR review API, retention API `/v1/retention`, `GET /v1/admin/audit/verify` | RBAC tables, audit events, retention/deletion tables, LTR governance tại 00011, retention/audit integrity tại 00012 remote `20261107142027` | Có quản lý role/trạng thái; LTR approve/reject đã có hash/actor/reason/audit; RBAC integration theo position và CI Batch 5 đã xanh. Batch 5 đã có workflow tạo case đến hạn, xác nhận/hủy/thực thi từng hồ sơ, purge storage+DB không ghi PII vào bằng chứng, audit hash chain/append-only và test phát hiện tamper/storage failure/chưa đến hạn/case hủy được tạo lại; postflight remote 0 broken audit event | `BLOCKED` | Đóng legacy key; chạy RBAC/retention matrix và audit verify qua backend staging với Supabase Auth/Storage |
| F1.11 | Cấu hình AI, privacy | Admin AI config, LLM/embedding providers, `GET /v1/admin/semantic/health` | AI config versions, provider secret encryption, pgvector embeddings | Có allowlist, mã hóa API key, redaction best effort; đã bổ sung embedding cache và semantic diagnostics phân biệt DISABLED/MISCONFIGURED/READY/OPERATIONAL/DEGRADED | `BLOCKED` cho CV thật | Phê duyệt privacy/egress; E2E model thật; đánh giá bias/prompt injection |
| F1.12 | Việt–Anh | frontend i18n | Không áp dụng | Có VI/EN, mặc định VI, test i18n | `PARTIAL` | HR review nội dung nghiệp vụ và các nhãn mới theo policy điểm |
| F1.13 | Dashboard, worker | dashboard API, worker health | operations, recovery events | Worker thread trong API, advisory lock/fencing/heartbeat/recovery; at-least-once; đã thêm RBAC integration test cho dashboard position scope | `PARTIAL` | Chỉ định một worker-enabled instance hoặc tách worker; monitoring/alerting; E2E recovery trên staging |

## 4. Các gate chưa được phép vượt qua

### Gate dữ liệu thật

Chưa dùng CV thật ở quy mô pilot cho tới khi:

- Legacy Supabase keys/JWT secret được đóng và kiểm chứng.
- Privacy/egress được phê duyệt cho LLM/BGE/OCR endpoints.
- Retention/deletion workflow đã có code/test và migration remote; phải thực thi và đối soát được qua backend staging.
- RBAC matrix và E2E Auth/Storage đạt trên staging.

### Gate LTR ACTIVE

Chưa bật `LTR_MODE=ACTIVE` cho tới khi:

- Có HR gold dataset, không chỉ weak labels.
- Train offline đạt gates và artifact được đăng ký.
- Governance có artifact hash, người phê duyệt, lý do và audit event — đã bổ sung tại migration 00011/Admin API; post-audit hardening đã sửa worker để `ACTIVE` từ chối registry artifact thiếu `artifact_sha256`, còn cần CI/deploy và kiểm thử trên staging.
- Production ACTIVE chỉ dùng registry artifact `APPROVED`; file artifact đã bị chặn ở production từ `57b9072`.
- SHADOW report chứng minh không có vi phạm mandatory/coverage gate.

### Gate production scale

Chưa tuyên bố production scale cho tới khi:

- CI đã có workflow độc lập và checks xanh tại run `42379643837`; còn cấu hình branch protection nếu quy trình phát hành yêu cầu.
- Worker được triển khai có chủ đích cho nhiều replicas hoặc tách process.
- Có monitoring/alerting, backup/restore và DR drill.
- Audit trail đã có hash chain/append-only trigger và migration `00012` đã áp lên project đã kết nối với postflight 0 broken event; vẫn cần kiểm chứng `GET /v1/admin/audit/verify` qua backend staging đã deploy.

## 5. Thứ tự nâng cấp đang thực hiện

1. Sửa công thức điểm UNCLEAR và khóa LTR file artifact ở production — đã có tại `57b9072`.
2. Đóng legacy Supabase keys — `BLOCKED` chờ thao tác Dashboard/Management API của chủ project sau khi xác nhận mọi deployment đã chuyển sang key/JWKS mới.
3. Tạo closure review này để theo dõi F1.01–F1.13.
4. Embedding cache và semantic diagnostics — đã bổ sung ở mức code; cần kiểm thử với endpoint/pgvector thật trên staging.
5. LTR governance migration/API — đã bổ sung và áp migration `00011` lên project đã kết nối; còn thiếu kiểm thử API trên staging và UI phê duyệt.
6. RBAC test matrix và CI — đã bổ sung và CI xanh tại run `42379643837`; runbook E2E staging tại `doc/E2E_STAGING.md`, còn cần chạy thật trên staging có Auth/Storage/OCR/LLM/BGE.
7. Retention/deletion workflow và audit integrity — đã triển khai ở code, CI xanh và migration `00012` đã áp lên project đã kết nối; còn staging evidence qua Supabase Auth/Storage/backend đã deploy.
8. Đánh giá BGE bằng golden set; xây HR gold dataset và chạy LTR SHADOW trước ACTIVE.
