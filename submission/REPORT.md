# Báo cáo cá nhân — K4-L3B Day 13 Monitoring & LLMOps

> Mỗi học viên hoàn thiện một file duy nhất này. Khi dẫn evidence, dùng đường dẫn tương đối, ví dụ `evidence/07-trace-waterfall.png`.

## 1. Thông tin học viên

- **Họ và tên:** Lê Trọng Khánh
- **MSSV:** 2A202602941
- **Lớp:** K4-L3B
- **Repository URL:** https://github.com/khanhlt2611/K4-L3-DAY13-LeTrongKhanh-2A202602941-Monitoring-LLMOps.git
- **Commit SHA cuối:**
- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1`
- **Tên project Langfuse cá nhân:** `day13-k4-l3b-2A202602941`

## 2. Evidence index

Điền đúng đường dẫn tới evidence thực tế. Có thể đổi tên hoặc dùng nhiều ảnh nếu cần.

| Evidence | Đường dẫn |
|---|---|
| Pytest cuối | `evidence/01-pytest.png` |
| Log validator | `evidence/02-log-validator.png` |
| Dashboard validator | `evidence/03-dashboard-validator.png` |
| Structured log | `evidence/04-structured-log.png` |
| PII redaction | `evidence/05-pii-redaction.png` |
| Trace list | `evidence/06-trace-list.png` |
| Trace waterfall | `evidence/07-trace-waterfall.png` |
| Trace metadata | `evidence/08-trace-metadata.png` |
| Prompt versions | `evidence/09-prompt-versions.png` |
| Prompt rollback | `evidence/10-prompt-rollback.png` |
| Dashboard runtime | `evidence/11-dashboard-overview.png` |
| Incident metric | `evidence/12-incident-metric.png` |
| Incident log | `evidence/13-incident-log.png` |
| Incident trace | `evidence/14-incident-trace.png` |

## 3. Kết quả kỹ thuật

| Nội dung | Baseline | Kết quả cuối | Nhận xét |
|---|---|---|---|
| `validate_logs.py` | 30/100 | 100/100 | Baseline có 30 records: thiếu correlation ID và metadata enrichment; PII đã được che. Kết quả cuối đạt 4/4 tiêu chí |
| `validate_dashboard.py` | Chưa ghi nhận | 6/6 panel | Dashboard contract đủ latency, traffic, errors, cost, tokens và quality |
| `pytest` | Chưa ghi nhận | 24 passed | Chạy `python -m pytest -q` trên mã nguồn CP2 |
| Số traces hợp lệ | 0 | Ít nhất 10 | Trace do workload cá nhân tạo, có root, retrieval và generation |
| Số PII leak | 0 | 0 | Baseline kiểm tra trên 30 log records; kết quả cuối kiểm tra trên 21 log records |
| Latency P95 / TTFT P95 | 1390 ms / 50 ms | 1378 ms / 51 ms | Kết quả cuối hiển thị trên dashboard runtime |
| Retrieval success rate | 100% (10/10) | 100% (22/22) | Không có retrieval failure trong workload cuối |

## 4. Logging và PII

- **Cách tạo/nhận và truyền correlation ID:** Middleware xóa context cũ ở đầu mỗi request, nhận `x-request-id` từ header nếu có hoặc sinh ID dạng `req-<8-hex>`, sau đó bind vào `structlog` context, lưu trong `request.state` và trả lại qua response header `x-request-id`.
- **Các metadata được ghi vào structured log:** `correlation_id`, `user_id_hash`, `session_id`, `feature`, `model`, `env`, `service`, timestamp và log level. Log phản hồi còn có latency, TTFT, token, cost, quality score và trạng thái retrieval.
- **Cách bảo đảm PII được scrub trước khi ghi:** Nội dung message/answer được rút gọn bằng `summarize_text`, hàm này gọi `scrub_text`. Ngoài ra, processor `scrub_event` được đặt trước `JsonlFileProcessor` và `JSONRenderer`, nên email, số điện thoại Việt Nam, CCCD và số thẻ được thay bằng marker `[REDACTED_*]` trước khi serialize và ghi xuống file.
- **Cách kiểm chứng kết quả:** Chạy `python scripts/load_test.py`, sau đó `python scripts/validate_logs.py`. Kết quả hiện tại: 21 records, không thiếu required fields hoặc enrichment, 10 correlation ID duy nhất, 0 PII leak và tổng điểm 100/100. Test PII trong `tests/test_pii.py` cũng kiểm tra email, các định dạng số điện thoại Việt Nam, CCCD và số thẻ.

## 5. Tracing và prompt versioning

- **Cách xác nhận traces do chính tôi tạo trong project cá nhân:** Chạy workload từ repo cá nhân và kiểm tra danh sách trace trong project Langfuse `day13-k4-l3b-2A202602941`; evidence `evidence/06-trace-list.png` thể hiện các observation mang trace name `day13-agent-request`.
- **Cấu trúc root/retrieval/generation observations:** Root `lab-agent-run` chứa child `retrieval` và `generation`. Retrieval ghi query preview và tài liệu đã scrub; generation liên kết managed prompt, model, token usage, cost, TTFT và answer preview đã scrub.
- **Cách nối trace với log:** `correlation_id` được bind vào Langfuse metadata và cũng xuất hiện trong structured log, cho phép tìm trace từ một log line cụ thể.
- **Prompt name:** `day13-chat`.
- **Version/label baseline:** Version 1, label `baseline`.
- **Version/label candidate:** Version 2, label `candidate`.
- **Trace ID của mỗi version:** Version 1: `e60bce42fdd4e9287d99271cb7c872ae`; version 2: `27e91af2376a79b939c68a38a84f568d`.
- **Cách promote và rollback `production`:** Chuyển label `production` từ version 1 sang version 2 để promote; khi candidate không đạt latency, cost hoặc quality thì chuyển label về version 1 mà không cần sửa code. Bằng chứng hai trạng thái label nằm trong `evidence/09-prompt-versions.png` và `evidence/10-prompt-rollback.png`.

## 6. Dashboard, SLO và alerts

- **Dashboard và sáu panel:** Dashboard `/dashboard` đọc `data/logs.jsonl`, tự refresh 30 giây trong time range 60 phút và hiển thị: latency P50/P95/P99 + TTFT P95, traffic, error rate + retrieval success, cost, input/output tokens và quality proxy. Mỗi panel có đơn vị và threshold; evidence tại `evidence/11-dashboard-overview.png`.
- **SLO và lý do chọn:** Trong cửa sổ 28 ngày, 99.5% request phải thành công và có latency không quá 3000 ms. Ngưỡng này cao hơn khoảng 2.2 lần baseline P95 1390 ms, tạo dung sai cho dao động bình thường nhưng vẫn phát hiện tail latency nghiêm trọng.
- **Cách tính error budget:** Error budget là `100% - 99.5% = 0.5%`. Với 10,000 request trong 28 ngày, tối đa `10,000 × 0.5% = 50` request được phép lỗi hoặc chậm hơn 3000 ms.
- **Ba alert và runbook tương ứng:** `HighLatencyP95` (>3000 ms trong 5m), `HighRequestErrorRate` (>2% trong 5m) và `LowRetrievalSuccessRate` (<90% trong 10m). Cả ba gửi tới Slack `#k4-l3b-alerts`, owner `student-2A202602941`; quy trình kiểm tra và mitigation nằm trong `docs/alerts.md`.

> Ví dụ cách viết error budget: "SLO 99.5% trong 28 ngày nghĩa là error budget 0.5%. Nếu workload có 10,000 request thì tối đa 50 request được phép lỗi hoặc chậm hơn ngưỡng SLO."

## 7. Điều tra challenge

- **Challenge ID:** `day13-k4-l3b-monitoring-llmops-v1` (cohort K4, affected feature `monitoring`).
- **Khoảng thời gian điều tra:** Workload incident từ `2026-09-30T04:41:47Z` đến `2026-09-30T04:42:02Z` (11:41–11:42 ICT). Request đại diện chạy từ `04:41:47.518Z` đến `04:41:51.852Z`.
- **Triệu chứng từ metrics:** Dashboard cho thấy latency P50 `2652 ms`, P95/P99 `3969 ms`, vượt ngưỡng dashboard `3000 ms` và ngưỡng challenge `2000 ms`. TTFT P95 vẫn `50 ms`, error rate `0%` và retrieval success `100%`, cho thấy retrieval bị chậm chứ không thất bại. Evidence: `evidence/12-incident-metric.png`.
- **Log line và correlation ID liên quan:** Log `response_sent` lúc `2026-09-30T04:41:51.852162Z` có `correlation_id=req-0779ecae`, `feature=monitoring`, `latency_ms=3969`, `ttft_ms=50`, `tool_name=retrieval`, `tool_success=true`, `tokens_in=74`, `tokens_out=149` và `cost_usd=0.002457`. Evidence: `evidence/13-incident-log.png`.
- **Trace ID và span gây ảnh hưởng:** Trace `0718a16c21fa619adef2ba191e2c0988` có cùng `correlation_id=req-0779ecae`. Root `lab-agent-run` mất `3.97 s`; child `retrieval` mất `2.50 s`, trong khi `generation` chỉ mất `0.15 s`. Span gây ảnh hưởng là `retrieval`. Evidence: `evidence/14-incident-trace.png`.
- **Root cause:** Challenge bật incident `rag_slow`, làm `retrieve()` chờ thêm khoảng `2.5 s`. Metric, log và trace cùng xác nhận tail latency tăng tại retrieval; generation, TTFT, error rate và retrieval success không có dấu hiệu bất thường tương ứng.
- **Fix action:** Tắt incident bằng `python scripts/inject_incident.py --disable`; endpoint `/health` sau đó xác nhận `rag_slow=false`. Trong production, khôi phục retrieval backend/config gây chậm và tránh blocking I/O trong request path.
- **Preventive measure:** Duy trì alert `HighLatencyP95` khi P95 vượt `3000 ms` trong 5 phút; theo dõi latency riêng cho span retrieval, đặt timeout/circuit breaker, chạy load-test regression và giữ runbook Metrics → Logs → Traces để khoanh vùng nhanh request bị ảnh hưởng.

> Gợi ý cách viết ngắn, không thay cho evidence thực tế: "Metric cho thấy `[latency/error/cost/quality]` bất thường trong `[khoảng thời gian]`. Log line `[event]` có `correlation_id=[...]` đại diện cho request bị ảnh hưởng. Trace cùng `correlation_id` cho thấy span `[retrieval/generation/prompt/tool]` có dấu hiệu `[chậm/lỗi/token tăng]`. Root cause là `[nguyên nhân suy ra từ evidence]`. Fix action là `[hành động khôi phục]`; preventive measure là `[alert/runbook/test/guardrail để ngăn tái diễn]`."

## 8. Giải thích và tự đánh giá

- **Một quyết định kỹ thuật quan trọng và lý do:** Dùng cùng `correlation_id` trong response header, structured log và Langfuse metadata, đồng thời tách `retrieval`/`generation` thành child observations. Quyết định này cho phép đi từ metric bất thường tới đúng request và đúng bước gây ảnh hưởng, thay vì đoán từ log tổng quát.
- **Một lỗi/blocker đã gặp:** Trong lúc thu evidence CP3, file log incident đầu tiên bị chuyển sang file baseline và process API reload làm state `rag_slow` trở về `false`; workload tiếp theo không còn tái hiện latency bất thường.
- **Cách tìm nguyên nhân và xử lý:** Kiểm tra `/health` để xác nhận incident đã tắt, đối chiếu log hiện tại với file đã chuyển và nhận ra các request incident vẫn còn nguyên. Sau đó bật lại `rag_slow`, chạy đúng workload challenge một lần, giữ nguyên `data/logs.jsonl` cho tới khi thu đủ metric, log và trace, rồi tắt incident.
- **Cách hiểu luồng Metrics → Logs → Traces:** Metrics xác định triệu chứng và khoảng thời gian, ví dụ P95 tăng. Logs thu hẹp xuống request cụ thể bằng `correlation_id` và cho biết latency/error/token/cost. Trace cùng ID phân rã thời gian theo span để xác định retrieval hay generation là nguyên nhân. Root cause chỉ được kết luận khi ba nguồn bằng chứng khớp nhau.
- **Vai trò của prompt version, token/cost, SLO hoặc rollback trong vận hành LLM:** Prompt version cho biết chính xác cấu hình nào tạo ra mỗi response; token và cost phát hiện regression chi phí; SLO chuyển kỳ vọng người dùng thành ngưỡng đo được; label `production` cho phép promote hoặc rollback prompt nhanh mà không sửa code.
- **Điều quan trọng nhất đã học:** Observability không chỉ là thu nhiều log mà là thiết kế các tín hiệu có thể liên kết, an toàn PII và đủ chi tiết để chứng minh nguyên nhân.
- **Hạn chế hoặc phần chưa hoàn thành, nếu có:** Lab dùng `FakeLLM`, dashboard local và alert contract; chưa tích hợp model production, kho metrics bền vữ hoặc gửi Slack alert thật. Các hạng mục bắt buộc CP0–CP3 và evidence đã hoàn thành; commit SHA cuối và nộp LMS được thực hiện sau lần kiểm tra cuối.

## 9. Checklist trước khi nộp

- [ ] Kết quả và evidence thuộc commit SHA cuối.
- [x] Tất cả ảnh/output mở được bằng đường dẫn tương đối.
- [x] Incident evidence nối đúng metric → log → trace.
- [x] Trace/prompt evidence thuộc project Langfuse cá nhân và ảnh không lộ secret.
- [x] Repository chạy lại được theo README.
- [x] Không có secret, API key bí mật, PII thô hoặc evidence của người khác/lớp khác.
- [ ] URL repo và commit SHA cuối đã được nộp trên LMS/Codelabs.
