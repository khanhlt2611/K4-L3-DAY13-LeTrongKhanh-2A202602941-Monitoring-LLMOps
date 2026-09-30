# Alert và runbook

Các alert dưới đây dựa trên triệu chứng quan sát được từ structured log. Quy trình điều tra chung là Metrics → Logs → Traces; không kết luận nguyên nhân trước khi đối chiếu `correlation_id`.

## Alert 1

- **Tên:** `HighLatencyP95`
- **Severity:** `warning`
- **Duration:** `5m`
- **Kênh thông báo:** Slack `#k4-l3b-alerts`
- **Owner:** `student-2A202602941`
- **SLI/SLO liên quan:** P95 của `response_sent.latency_ms`; SLO yêu cầu request thành công có latency không quá 3000 ms.
- **Điều kiện:** `p95(latency_ms) > 3000ms` liên tục trong 5 phút.
- **Ảnh hưởng:** Nhóm request chậm nhất khiến người dùng phải chờ lâu hơn để nhận câu trả lời.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel Latency, xác nhận P95/P99, TTFT và khoảng thời gian vượt ngưỡng.
  2. Lọc các log `response_sent` có `latency_ms > 3000`, lấy `correlation_id` của một request đại diện.
  3. Mở trace cùng `correlation_id`, so sánh thời gian của `retrieval` và `generation`.
- **Mitigation tạm thời:** Tắt scenario gây chậm hoặc rollback prompt/config vừa thay đổi; giảm concurrency nếu hệ thống quá tải.

## Alert 2

- **Tên:** `HighRequestErrorRate`
- **Severity:** `critical`
- **Duration:** `5m`
- **Kênh thông báo:** Slack `#k4-l3b-alerts`
- **Owner:** `student-2A202602941`
- **SLI/SLO liên quan:** Tỷ lệ `request_failed` trên tổng `request_received`; guardrail error rate tối đa 2%.
- **Điều kiện:** Error rate lớn hơn 2% liên tục trong 5 phút.
- **Ảnh hưởng:** Người dùng không nhận được câu trả lời hoặc nhận lỗi từ API.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel Errors, xác nhận error rate và phân bố theo `error_type`.
  2. Lọc log `request_failed`, chọn `correlation_id` và kiểm tra `tool_name`, `tool_success` cùng payload đã scrub.
  3. Mở trace cùng ID, xác định observation dừng ở `retrieval` hay `generation`.
- **Mitigation tạm thời:** Tắt incident practice, khôi phục dependency/config gần nhất; nếu lỗi do prompt thì rollback label `production`.

## Alert 3

- **Tên:** `LowRetrievalSuccessRate`
- **Severity:** `warning`
- **Duration:** `10m`
- **Kênh thông báo:** Slack `#k4-l3b-alerts`
- **Owner:** `student-2A202602941`
- **SLI/SLO liên quan:** Tỷ lệ `tool_success=true` trong các log có trạng thái retrieval; guardrail tối thiểu 90%.
- **Điều kiện:** Retrieval success dưới 90% liên tục trong 10 phút.
- **Ảnh hưởng:** Câu trả lời thiếu context, có thể giảm chất lượng hoặc request thất bại.
- **Ba bước kiểm tra đầu tiên:**
  1. Mở panel Errors & Retrieval, xác nhận thời điểm success rate giảm.
  2. Lọc log `tool_name=retrieval` và `tool_success=false`, lấy `correlation_id` của request lỗi.
  3. Mở trace cùng ID, kiểm tra status, latency và output của observation `retrieval`.
- **Mitigation tạm thời:** Khôi phục vector store/retrieval config, tắt scenario `tool_fail`; dùng fallback an toàn thay vì sinh câu trả lời không có context.
