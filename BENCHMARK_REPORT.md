# Benchmark & Observability Report — Day 14

> Copy file này thành `BENCHMARK_REPORT.md` trong repo của bạn và điền đầy đủ.
> Mọi con số phải lấy từ report JSON / CSV / screenshot thật, không ước lượng.

**Họ tên:** Đặng Thanh Hải
**Ngày chạy:** 25/11/2026
**Môi trường:** Windows 11, WSL2 (Ubuntu 26.04, 16 CPU), Python 3.11, Docker Desktop (Docker 29.9.3). RAM: 16GB

---

## 1. SLO của agent

| SLI | SLO | Lý do chọn ngưỡng này |
|---|---|---|
| p95 latency `/ask` | < 500 ms | Ở concurrency 1–50, p95 đo được 217.1–351.0 ms, nên 500 ms còn khoảng dự phòng mà vẫn phát hiện được lúc chậm bất thường (mức 100 và `MOCK_SLOW_RATE=0.1` đều vi phạm) |
| Error rate `/ask` | < 2 % | Mock LLM lỗi khoảng 1% theo cấu hình; các lần đo ra 0–1.67%. 2% cho phép lỗi nền này nhưng bắt được khi lỗi tăng gấp đôi |
| Accuracy trên golden dataset | ≥ 85 % | v2 đạt 91.3% (21/23). 85% cho phép sai tối đa 3 câu, đủ để v1 (4.3%) không được deploy |

---

## 2. Benchmark hiệu năng (develop, `load_test.py`)

### 2.1 Concurrency vs latency (agent v2)

| Concurrency | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Error rate | SLO |
|---|---|---|---|---|---|---|
| 1 | 3.86 | 189.6 | 223.5 | 1710.0 | 0.00% | PASS |
| 10 | 37.57 | 190.2 | 217.1 | 1681.3 | 0.33% | PASS |
| 50 | 102.2 | 207.3 | 351.0 | 1687.7 | 1.00% | PASS |
| 100 | 48.64 | 491.3 | 4033.4 | 4533.1 | 0.33% | FAIL (p95) |

**Nhận xét:** RPS có tăng tuyến tính theo concurrency không? Vì sao?

- Từ 1 lên 10, RPS tăng gần tuyến tính (3.86 lên 37.57) và p50 gần như không đổi, vì agent chủ yếu chờ mock LLM chứ không dùng nhiều CPU.
- Từ 10 lên 50, RPS chỉ tăng khoảng 2.7 lần và p95 tăng từ 217.1 lên 351.0 ms.
- Từ 50 lên 100, RPS giảm còn 48.64 và p95 lên 4033.4 ms, vi phạm SLO.
- Mức 100 phản ánh giới hạn của công cụ đo nhiều hơn là của agent. Khi đo thêm (không nộp file), mức 100 vẫn chậm dù đã tắt log của agent. Khi chia 100 request song song cho hai process `load_test.py`, mỗi process 50, p95 trở lại vài trăm ms và agent gần như không tốn CPU. Vì vậy số ở mức 100 không nên dùng để kết luận sức chịu tải của agent.
- p99 ở ba mức đầu khoảng 1.7 giây là nhóm request chậm cố ý (`MOCK_SLOW_RATE` mặc định 0.03, cộng 1500 ms).

### 2.2 Tail latency

| `MOCK_SLOW_RATE` | avg (ms) | p95 (ms) | p99 (ms) |
|---|---|---|---|
| 0 | 189.9 | 217.7 | 227.8 |
| 0.03 (mặc định) | 248.7 | 226.9 | 1709.8 |
| 0.1 | 387.2 | 1692.6 | 1712.0 |

(300 request, concurrency 20 cho mỗi lần đo.)

**Nhận xét:** Chỉ số nào nhạy nhất với request chậm? Vì sao SLO không nên đặt theo average?

- p99 nhạy nhất: từ 0 lên 0.03, p99 tăng từ 227.8 lên 1709.8 ms (khoảng 7.5 lần), trong khi avg chỉ tăng 58.8 ms và p95 gần như không đổi.
- Ở 0.1, tỉ lệ request chậm vượt 5% nên p95 cũng nhảy lên 1692.6 ms và vi phạm SLO p95 500 ms.
- Average bị pha loãng bởi số đông request nhanh: ở 0.1, khoảng 1/10 người dùng chờ gần 1.7 giây mà avg chỉ 387.2 ms, vẫn dưới 500 ms. Nếu đặt SLO theo average thì lần này vẫn được coi là đạt.
- Vì vậy SLO nên đặt theo p95 hoặc p99. p95 chỉ phát hiện khi hơn 5% request chậm, còn p99 phát hiện từ khoảng 1%.

---

## 3. Benchmark chất lượng (develop, `eval/run_eval.py`)

| Chỉ số | Agent v1 | Agent v2 | Agent v2 (sau khi sửa KB) |
|---|---|---|---|
| Accuracy | 4.35% (1/23) | 91.3% (21/23) | 100% (23/23) |
| Avg tokens / câu | 56.9 | 108.8 | 113.7 |
| Tổng cost (USD) | 0.000402 | 0.000757 | 0.00079 |
| Cost / câu đúng (USD) | 0.00040155 | 0.00003607 | 0.00003436 |
| Quality gate | FAIL (ngưỡng 80%) | PASS (ngưỡng 80%) | PASS (ngưỡng 100%, 0 regression) |

**Những câu v2 trả lời sai ban đầu và cách bạn sửa:**

| ID | Keyword bị thiếu | Bạn đã sửa gì |
|---|---|---|
| security-02 | token, hết hạn, chữ ký | Thêm tài liệu về JWT và API key vào `KNOWLEDGE_BASE`, kích hoạt bằng từ khoá `jwt` |
| scaling-03 | cpu, memory, custom metrics | Thêm tài liệu về Kubernetes HPA, kích hoạt bằng `hpa`, `kubernetes`, `autoscal` |

**Nhận xét về trade-off chất lượng / chi phí / latency giữa v1 và v2:**

- Chất lượng: accuracy tăng từ 4.35% lên 91.3%, không có câu nào bị regression. v1 chỉ đúng 1/23 vì không có tài liệu để dựa vào.
- Chi phí: v2 tốn khoảng 1.9 lần token và tổng cost mỗi lần eval, vì prompt có thêm tài liệu và câu trả lời dài hơn. Nhưng cost trên mỗi câu đúng rẻ hơn khoảng 11 lần (0.00003607 so với 0.00040155 USD), nên nhìn cost mỗi câu sẽ kết luận ngược.
- Latency: p95 trong eval tăng từ 188.8 lên 216.6 ms do có thêm bước retrieval. Eval chỉ có 23 câu nên số này chỉ để tham khảo.
- Sau khi sửa knowledge base, v2 đạt 23/23 với thêm 4.9 token mỗi câu.

**Quality gate trong CI:** `run_eval.py` trả exit code 1 khi accuracy thấp hơn `--min-accuracy` hoặc có regression so với `--baseline`. File `.github/workflows/eval.yml` chạy agent v2 và eval trên mỗi pull request với ngưỡng 85%, nên job fail khi không đạt. Để chặn merge, cần bật branch protection và đặt job này là bắt buộc.

---

## 4. Observability stack (production)

### 4.1 Screenshot

- [x] Dashboard Grafana khi đang có tải (thấy rõ Golden Signals): [grafana-dashboard.png](screenshots/grafana-dashboard.png)
- [x] Một trace chậm trong Jaeger (thấy span nào chiếm thời gian): [jaeger-slow-trace.png](screenshots/jaeger-slow-trace.png)
- [x] Một trace lỗi trong Jaeger (có event `exception`): [jaeger-error-trace.png](screenshots/jaeger-error-trace.png)
- [x] Trang Alerts của Prometheus với ít nhất 1 alert đang **firing** (2 alert): [prometheus-alert-firing.png](screenshots/prometheus-alert-firing.png)

### 4.2 Thí nghiệm "phá hệ thống"

| # | Thay đổi | Alert nào firing | Thời gian từ lúc đổi → firing | Panel nào phản ánh rõ nhất |
|---|---|---|---|---|
| A | `MOCK_ERROR_RATE=0.2` | `AgentHighErrorRate` | 90 giây | Error rate |
| B | `MOCK_SLOW_RATE=0.3` (giữ `MOCK_ERROR_RATE=0.2` của A) | `AgentHighLatencyP95` (`AgentHighErrorRate` vẫn firing) | 146 giây | Latency p50/p95/p99 |
| C | `LLM_MODEL=mock-llm-large` | Không thực hiện | | |
| D | `docker pause` 1 instance | Không thực hiện | | |
| E | `AGENT_VERSION=v1` | Không có alert nào sau 5 phút | Không có | Không có panel latency hay error rate nào đo được lỗi chất lượng |

(Locust 30 users, 2 instance. Trước A, `LLMCostBurnRateHigh` đã firing sẵn vì tải 30 users, không phải do thí nghiệm. Trước E, hệ thống được đưa về bình thường và không còn alert nào.)

**Thí nghiệm E không làm alert nào firing. Bạn sẽ phát hiện loại sự cố này trong production bằng cách nào?**

- Cùng câu "Liveness probe dùng để làm gì?", v2 trả lời đúng, còn v1 trả "Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận." Request vẫn 200 và latency bình thường, nên metric hạ tầng không thấy gì bất thường.
- Trước khi deploy: chạy eval trên golden dataset trong CI và chặn merge khi accuracy dưới ngưỡng hoặc có regression. v1 chỉ đạt 4.35% nên sẽ bị chặn.
- Khi đang chạy: chạy eval định kỳ trên production bằng một tập câu hỏi cố định, chấm mẫu một phần traffic thật, theo dõi phản hồi của người dùng, và đặt alert cho các số này cùng retrieval hit ratio và phiên bản agent đang phục vụ.

### 4.3 Debug bằng trace

Chọn 1 trace chậm nhất bạn tìm được:

- `trace_id`: `4e648e7da900aca3cf9d471a547f3fa8` ([ảnh](screenshots/jaeger-slow-trace.png))
- Tổng thời gian: 1717.46 ms
- Span chiếm nhiều thời gian nhất: `chat mock-llm-small` (1689.99 ms, 98.4%). `agent.retrieve_context` chỉ mất 25.42 ms (1.5%), nên request chậm là do LLM chứ không phải retrieval hay code của agent. (`agent.run` 1715.61 ms là span cha, bao gồm cả hai span này.)
- Dòng log tương ứng (grep theo `trace_id`):

```json
{"ts": "2026-11-25T14:50:22.704287+00:00", "level": "INFO", "service": "observable-agent", "instance": "a34b743f1456", "event": "http_request", "trace_id": "4e648e7da900aca3cf9d471a547f3fa8", "span_id": "46cce5a9d432cd7d", "request_id": "cc865f4746b6", "method": "POST", "route": "/ask", "status": 200, "ms": 1716.9}
```

Trace lỗi: `trace_id` `72ba742296cac13e8d99a061d65deddd` ([ảnh](screenshots/jaeger-error-trace.png)), span `chat` có event `exception`. Dòng log:

```json
{"ts": "2026-11-25T14:53:06.891419+00:00", "level": "INFO", "service": "observable-agent", "instance": "a34b743f1456", "event": "llm_error", "trace_id": "72ba742296cac13e8d99a061d65deddd", "span_id": "8c202b815d217bc6", "request_id": "e10c71d2bf60", "error": "Upstream LLM error: 503 Service Unavailable (mock)"}
```

---

## 5. Benchmark scaling (production, Locust headless, 100 users, 2 phút)

| Số instance | RPS | p50 (ms) | p95 (ms) | p99 (ms) | Failures |
|---|---|---|---|---|---|
| 1 | 60.17 | 190 | 260 | 1700 | 73 / 7185 (1.02%) |
| 3 | 60.43 | 190 | 220 | 1700 | 64 / 7214 (0.89%) |

(Dòng `/ask` trong `scale_1_stats.csv` và `scale_3_stats.csv`.)

**Giải thích kết quả:** Scale có cải thiện p95 không? Nút thắt nằm ở đâu?

- p95 giảm nhẹ từ 260 xuống 220 ms; p50, p99 và RPS gần như không đổi. Mỗi cấu hình chỉ đo một lần nên chênh lệch nhỏ chưa chắc là do scale.
- RPS không tăng vì Locust mô phỏng người dùng nghỉ 0.5–2 giây giữa các câu: 100 người chỉ tạo khoảng 66 request/giây (cả `/health`), và 1 instance đã phục vụ hết.
- Nút thắt về latency là thời gian chờ mock LLM. p50 là 190 ms ở cả hai lần, p99 là nhóm request chậm cố ý; thêm instance không làm LLM nhanh hơn.
- Dấu hiệu 1 instance bận hơn: p95 của `/health` (không gọi LLM) là 12 ms với 1 instance và 4 ms với 3 instance, nhưng chưa đủ để thành nút thắt. Muốn thấy lợi ích của scale cần tải cao hơn.
- Lưu ý khi đo: `docker compose run locust` khởi động cả service phụ thuộc và đưa agent về 2 replica, nên các lần đo đầu bị loại. Kết quả trên chạy với `--no-deps` và đã kiểm tra `count(up{job="agent"}==1)` trong lúc đo là 1 và 3.

---

## 6. Kết luận

- 3 điều bạn học được về benchmark & observability:
  1. Average che giấu tail latency: ở `MOCK_SLOW_RATE=0.03`, avg chỉ tăng 58.8 ms còn p99 tăng khoảng 7.5 lần, nên SLO phải đặt theo percentile.
  2. Phải kiểm tra công cụ đo trước khi kết luận: mức 100 bị chậm do `load_test.py`, và hai lần đo scale đầu tiên bị loại vì số instance thực tế không đúng.
  3. Metric hạ tầng không đo được chất lượng: đổi sang v1 không làm alert nào firing, chỉ eval mới phát hiện.
- Nếu đưa agent này lên production thật, bạn sẽ thêm metric / alert nào nữa?
  - Alert cho accuracy của eval định kỳ và cho retrieval hit ratio giảm.
  - Alert theo p99, vì p95 không phát hiện nhóm request chậm dưới 5%.
  - Metric và alert ở tầng Nginx (tỉ lệ 5xx, thời gian chờ upstream), vì metric của agent không thấy lỗi xảy ra trước khi request tới agent.
  - Đặt lại ngưỡng `LLMCostBurnRateHigh`: $2/giờ đã bị vượt ở tải bình thường 30 users, nên alert này dễ bị bỏ qua.
