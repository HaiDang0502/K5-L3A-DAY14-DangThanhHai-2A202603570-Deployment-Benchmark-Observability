# Day 14 Lab - Mission Answers

## Part 1: Localhost vs Production

### Exercise 1.1: Anti-patterns found

File: `01-localhost-vs-production/develop/app.py`

1. **Hardcode API key** (L17): push lên GitHub là lộ key. Xoá file sau đó vẫn còn key trong lịch sử commit.
2. **Hardcode mật khẩu database** trong `DATABASE_URL` (L18): lộ như trên, và muốn đổi database phải sửa code.
3. **In secret ra log** (L34): ai đọc được log đều thấy key.
4. **Dùng `print()` thay cho logging** (L33, L34, L38): không có level và thời gian, khó lọc khi có nhiều request.
5. **Cấu hình cố định trong code** (L21, L22): mỗi môi trường cần giá trị khác nhau thì phải sửa code.
6. **Không có `/health` và `/ready`** (ghi chú L42–43): platform không biết khi nào cần restart hoặc ngừng gửi traffic.
7. **`host="localhost"`** (L51): chạy trong container thì bên ngoài không kết nối vào được, cần `0.0.0.0`.
8. **`port=8000` cố định** (L52): Railway và Render cấp cổng qua biến `PORT`.
9. **`reload=True`** (L53): chế độ dành cho dev, tốn tài nguyên khi chạy thật.

Anti-pattern đã được sửa ở production: `port=8000` (develop L52) thành `port=settings.port` (`production/app.py` L197), với giá trị đọc từ `PORT` (`production/config.py` L18).

### Exercise 1.2: Chạy bản develop

**Gửi `question` qua query: 200**

```text
$ curl -i -X POST "http://localhost:8000/ask?question=Hello"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:43:16 GMT
server: uvicorn
content-length: 95
content-type: application/json

{"answer":"Agent đang hoạt động tốt! (mock response) Hỏi thêm câu hỏi đi nhé."}
```

**Gửi `question` qua JSON: 422**

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 422 Unprocessable Content
date: Wed, 25 Nov 2026 08:43:17 GMT
server: uvicorn
content-length: 94
content-type: application/json

{"detail":[{"type":"missing","loc":["query","question"],"msg":"Field required","input":null}]}
```

**Không có health check: 404** (chỉ chép phần header)

```text
$ curl -i http://localhost:8000/health
HTTP/1.1 404 Not Found
date: Wed, 25 Nov 2026 08:43:17 GMT
server: uvicorn
content-length: 22
content-type: application/json
```

Nhận xét: app trả lời được nhưng chưa production-ready, vì các vấn đề ở Exercise 1.1. Bản này đọc `question` từ query (`"loc":["query","question"]`) nên gửi JSON bị 422. `/health` trả 404, xác nhận anti-pattern số 6.

### Exercise 1.3: Comparison table

| Feature | Develop | Production | Why Important? |
|---------|---------|------------|----------------|
| Config | Hardcode (L17–22) | Đọc biến môi trường trong `config.py` | Cùng một bản code chạy được ở dev, staging và production |
| Secret | Nằm trong code và bị in ra log | Đọc từ env; thiếu `AGENT_API_KEY` khi `ENVIRONMENT=production` thì báo lỗi lúc khởi động | Không lộ secret qua git hoặc log, phát hiện thiếu cấu hình sớm |
| Health check | Không có | `/health` và `/ready` | `/health` để biết khi nào cần restart, `/ready` để biết khi nào được gửi traffic |
| Logging | `print()` | Module `logging`, có thời gian và level, không ghi key | Dễ lọc và tìm lỗi. Hạn chế: log sự kiện lồng JSON vào `msg` không escape dấu nháy nên chưa phải JSON hợp lệ |
| Shutdown | Chỉ có shutdown mặc định của uvicorn | Thêm `lifespan` để dọn dẹp và handler SIGTERM | Request đang chạy được làm xong khi deploy hoặc scale down |
| Host / Port | `localhost`, cổng 8000 | Mặc định `0.0.0.0`, cổng đọc từ `PORT` | Chạy được trong container và trên cloud |
| Reload | Luôn bật | Chỉ bật khi `DEBUG=true` | Không chạy chế độ dev trên production |
| Validate input | 422 khi thiếu `question`, nhưng nhận chuỗi rỗng | 422 khi thiếu hoặc rỗng | Chặn input vô nghĩa trước khi gọi LLM |

**Kết quả chạy bản production (cổng 8000)**

```text
$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 08:31:58 GMT
server: uvicorn
content-length: 131
content-type: application/json

{"status":"ok","uptime_seconds":362.5,"version":"1.0.0","environment":"development","timestamp":"2026-11-25T08:31:59.021324+00:00"}
```

**Đổi cấu hình bằng env, không sửa code (cổng 8001)**

```text
$ PORT=8001 ENVIRONMENT=staging python app.py
$ curl http://localhost:8001/health
{"status":"ok","uptime_seconds":11.8,"version":"1.0.0","environment":"staging","timestamp":"2026-11-25T08:34:15.350471+00:00"}
```

## Part 2: Docker

### Exercise 2.1: Dockerfile questions

1. Base image: `python:3.11`.
2. Working directory: `/app`.
3. Vì sao COPY requirements.txt trước: Docker cache theo layer. Khi chỉ sửa code, `requirements.txt` không đổi nên bước `pip install` dùng lại cache. Nếu copy code trước, mỗi lần sửa code phải cài lại thư viện.
4. CMD vs ENTRYPOINT: `CMD` là lệnh hoặc tham số mặc định, bị thay khi truyền lệnh vào `docker run`. `ENTRYPOINT` là lệnh chính, tham số của `docker run` được nối vào sau nó. Muốn thay thì dùng `--entrypoint`.

### Exercise 2.2: Build và run

Kích thước image develop: 1.67 GB (cột DISK USAGE, output `docker images` ở Exercise 2.3).

```text
$ docker run --rm -d --name agent-dev -p 8000:8000 my-agent:develop
$ curl -i -X POST "http://localhost:8000/ask?question=Docker"
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:09:20 GMT
server: uvicorn
content-length: 103
content-type: application/json

{"answer":"Container là cách đóng gói app để chạy ở mọi nơi. Build once, run anywhere!"}

$ curl -i http://localhost:8000/health
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:09:20 GMT
server: uvicorn
content-length: 53
content-type: application/json

{"status":"ok","uptime_seconds":4.9,"container":true}
```

Nhận xét: gọi được từ máy host vì app lắng nghe ở `0.0.0.0` và `-p 8000:8000` nối cổng host với cổng container.

### Exercise 2.3: Image size comparison

- Develop: 1670 MB (Docker hiển thị 1.67GB)
- Production: 240 MB
- Difference: giảm 85.6%, tính theo cột DISK USAGE: (1670 − 240) / 1670

Theo cột CONTENT SIZE (dung lượng nén): 426 MB xuống 57.4 MB, giảm 86.5%.

```text
$ docker images my-agent
IMAGE               ID             DISK USAGE   CONTENT SIZE   EXTRA
my-agent:advanced   56ef64599bc7        240MB         57.4MB
my-agent:develop    8d9c0e14a5da       1.67GB          426MB
```

- Stage 1 (`builder`): từ `python:3.11-slim`, cài `gcc`, `libpq-dev` và các thư viện Python bằng `pip install --user`.
- Stage 2 (`runtime`): bắt đầu lại từ `python:3.11-slim`, chỉ copy thư viện đã cài và code, chạy bằng user `appuser`.
- Vì sao image nhỏ hơn: dùng base `slim` thay cho bản đầy đủ, và công cụ build nằm lại ở stage 1.

### Exercise 2.4: Docker Compose stack

```text
Client --HTTP :80--> nginx --> agent:8000 (FastAPI)
                                 |-- REDIS_URL  --> redis:6379
                                 |-- QDRANT_URL --> qdrant:6333

Cả 4 service nằm trong network "internal".
```

- Service gọi nhau bằng tên service qua DNS nội bộ của Docker.
- Chỉ nginx mở cổng ra ngoài (80 và 443). `nginx.conf` chỉ cấu hình `listen 80`, nên cổng 443 chưa phục vụ HTTPS.
- Agent chờ redis và qdrant healthy rồi mới khởi động.
- Compose truyền `REDIS_URL` và `QDRANT_URL` cho agent, nhưng `main.py` hiện chưa dùng hai biến này, nên trong bản mẫu agent chưa thật sự gọi redis và qdrant.

**Các service đang chạy** (rút gọn các cột của `docker compose -p k5-day14-docker ps`)

```text
SERVICE   IMAGE                   STATUS                    PORTS
agent     k5-day14-docker-agent   Up 20 seconds (healthy)   8000/tcp
nginx     nginx:alpine            Up 20 seconds             0.0.0.0:80->80/tcp, 0.0.0.0:443->443/tcp
qdrant    qdrant/qdrant:v1.9.0    Up 31 seconds (healthy)   6333-6334/tcp
redis     redis:7-alpine          Up 31 seconds (healthy)   6379/tcp
```

**Gọi qua Nginx (cổng 80)**

```text
$ curl -i http://localhost/health
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 25 Nov 2026 09:07:39 GMT
Content-Type: application/json
Content-Length: 96
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"status":"ok","uptime_seconds":19.4,"version":"2.0.0","timestamp":"2026-11-25T09:07:39.258536"}

$ curl -i -X POST http://localhost/ask -H "Content-Type: application/json" -d '{"question":"Explain microservices"}'
HTTP/1.1 200 OK
Server: nginx
Date: Wed, 25 Nov 2026 09:07:39 GMT
Content-Type: application/json
Content-Length: 126
Connection: keep-alive
X-Frame-Options: DENY
X-Content-Type-Options: nosniff
X-XSS-Protection: 1; mode=block

{"answer":"Đây là câu trả lời từ AI agent (mock). Trong production, đây sẽ là response từ OpenAI/Anthropic."}
```

`Server: nginx` và các header `X-*` cho thấy request đi qua Nginx. Agent, redis và qdrant không có cổng nào nối ra máy host.

## Part 3: Cloud Deployment

### Exercise 3.1: Railway deployment

- URL: https://agent-production-44f3e8e0.up.railway.app
- Screenshot: [dashboard](screenshots/dashboard.png), [running](screenshots/running.png), [test](screenshots/test.png)
- Deploy thư mục `06-lab-complete/` bằng Railway CLI, có thêm service Redis. Chi tiết trong [DEPLOYMENT.md](DEPLOYMENT.md).

```text
URL: https://agent-production-44f3e8e0.up.railway.app
health          200
ready           200
ask khong key   401
ask co key      200
```

### Exercise 3.2: So sánh `railway.toml` và `render.yaml`

So `06-lab-complete/railway.toml` với `03-cloud-deployment/render/render.yaml`:

| | `railway.toml` | `render.yaml` | Vì sao |
|---|---|---|---|
| Phạm vi | Cách build và deploy một service | Nhiều service trong một file (web và Redis) | `render.yaml` là Blueprint mô tả hạ tầng |
| Build | `builder = "DOCKERFILE"` | `runtime: python` với `buildCommand` | Bài Part 6 đã có Dockerfile, bản mẫu Render thì không dùng Docker |
| Lệnh chạy | Không khai báo, dùng `CMD` của Dockerfile | `startCommand` với `$PORT` | Cả hai đều đọc cổng từ `PORT` |
| Health check | `healthcheckPath = "/health"` | `healthCheckPath: /health` | Cùng mục đích, khác cú pháp |
| Biến môi trường | Không nằm trong file, đặt bằng CLI hoặc dashboard | Khai báo trong `envVars` | Secret không ghi vào file: `sync: false` (nhập tay) hoặc `generateValue: true` (tự sinh) |
| Redis | Tạo service riêng | Khai báo `type: redis` | Bản mẫu Render chưa nối `REDIS_URL` vào web service |
| Region, plan | Không khai báo | `singapore`, `free` | `render.yaml` quản lý cả hạ tầng |

Theo tài liệu Railway ngày 25/11/2026, `railway.toml` (Config as Code) đã bị deprecated và ngừng được đọc từ 01/12/2026, thay bằng Infrastructure as Code.

### Exercise 3.3: Cloud Run

Pipeline trong `cloudbuild.yaml` chạy bốn bước nối tiếp bằng `waitFor`: test (pytest), build image, push image, rồi `gcloud run deploy`.
Test thất bại thì các bước sau không chạy. Image gắn tag `$COMMIT_SHA` để biết chính xác bản nào đang chạy và rollback được.
Bước deploy đặt 1–10 instance và lấy `OPENAI_API_KEY` từ Secret Manager thay vì ghi trong file.
`service.yaml` mô tả service dạng khai báo: scale 1–10, 80 request đồng thời mỗi instance, liveness gọi `/health`, startup probe gọi `/ready`.
Hai file chưa đồng nhất: pipeline không dùng `service.yaml` và không truyền `AGENT_API_KEY`, trong khi `service.yaml` có.

## Part 4: API Security

### Exercise 4.1: API key

- Check key ở đâu: hàm `verify_api_key` (`develop/app.py` L39), gắn vào `/ask` bằng `Depends` (L70).
- Sai key thì sao: thiếu key trả 401, sai key trả 403.
- Rotate key: đổi biến `AGENT_API_KEY` rồi restart. Code chỉ nhận một key nên client dùng key cũ bị ngắt ngay. Muốn chuyển êm thì cho hai key cùng hợp lệ một thời gian.

**Không có key: 401**

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 09:12:14 GMT
server: uvicorn
content-length: 67
content-type: application/json

{"detail":"Missing API key. Include header: X-API-Key: <your-key>"}
```

**Sai key: 403**

```text
$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: wrong" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 403 Forbidden
date: Wed, 25 Nov 2026 09:12:14 GMT
server: uvicorn
content-length: 29
content-type: application/json

{"detail":"Invalid API key."}
```

**Đúng key: 200** (key đã che, chỉ chép phần header)

```text
$ curl -i -X POST http://localhost:8000/ask -H "X-API-Key: ***" -H "Content-Type: application/json" -d '{"question":"Hello"}'
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:12:14 GMT
server: uvicorn
content-length: 114
content-type: application/json
```

### Exercise 4.2: JWT

Client gửi username và password tới `POST /auth/token`, server trả token đã ký bằng `JWT_SECRET`. Các request sau gửi token trong header `Authorization: Bearer`. Server kiểm tra chữ ký và hạn dùng (60 phút), rồi lấy `sub` và `role` từ token nên không phải tra database. Payload được ký chứ không mã hoá.

**Không có token: 401**

```text
$ curl -i -X POST http://localhost:8000/ask -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 401 Unauthorized
date: Wed, 25 Nov 2026 09:13:46 GMT
server: uvicorn
www-authenticate: Bearer
content-length: 76
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Authentication required. Include: Authorization: Bearer <token>"}
```

**Token sai: 403**

```text
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer abc" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 403 Forbidden
date: Wed, 25 Nov 2026 09:13:46 GMT
server: uvicorn
content-length: 27
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":"Invalid token."}
```

**Token đúng: 200** (token nằm trong biến `$TOKEN`, không in ra)

```text
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question":"Explain JWT"}'
HTTP/1.1 200 OK
date: Wed, 25 Nov 2026 09:13:46 GMT
server: uvicorn
content-length: 192
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"question":"Explain JWT","answer":"Tôi là AI agent được deploy lên cloud. Câu hỏi của bạn đã được nhận.","usage":{"requests_remaining":9,"budget_remaining_usd":1.9e-05}}
```

### Exercise 4.3: Rate limiting

- Thuật toán: sliding window, lưu timestamp từng request trong 60 giây cho mỗi user.
- Limit: user 10 request/phút, admin 100 request/phút.
- Admin: không bypass hoàn toàn, `app.py` L141 chọn limiter cao hơn khi `role == "admin"`.
- Hạn chế: đếm trong RAM nên restart là mất, nhiều instance thì đếm riêng.

**Vòng lặp 12 request** (chạy ngay sau request 200 ở Exercise 4.2)

```text
$ for i in $(seq 1 12); do curl -s -o /dev/null -w "Request $i: %{http_code}\n" ...; done
Request 1: 200
Request 2: 200
Request 3: 200
Request 4: 200
Request 5: 200
Request 6: 200
Request 7: 200
Request 8: 200
Request 9: 200
Request 10: 429
Request 11: 429
Request 12: 429
```

Request ở Exercise 4.2 đã chiếm 1 lượt, cộng 9 lượt trong vòng lặp là đủ 10, nên request thứ 10 của vòng lặp bị chặn.

**Vượt giới hạn: 429**

```text
$ curl -i -X POST http://localhost:8000/ask -H "Authorization: Bearer $TOKEN" -H "Content-Type: application/json" -d '{"question":"Test"}'
HTTP/1.1 429 Too Many Requests
date: Wed, 25 Nov 2026 09:13:47 GMT
server: uvicorn
x-ratelimit-limit: 10
x-ratelimit-remaining: 0
x-ratelimit-reset: 1795598087
retry-after: 59
content-length: 98
content-type: application/json
x-content-type-options: nosniff
x-frame-options: DENY
x-xss-protection: 1; mode=block
referrer-policy: strict-origin-when-cross-origin

{"detail":{"error":"Rate limit exceeded","limit":10,"window_seconds":60,"retry_after_seconds":59}}
```

### Exercise 4.4: Cost guard implementation

- Trước khi gọi LLM, `check_budget` chặn user vượt $1/ngày (402) và tổng vượt $10 (503). Sau khi gọi, `record_usage` cộng token và tính tiền.
- Hạn chế của bản mẫu: lưu trong RAM; `_global_cost` không reset theo ngày; kiểm tra trước, ghi sau nên request song song có thể cùng lọt; `budget_remaining_usd` trong `/ask` (`app.py` L160) thật ra là số đã tiêu.
- Cách làm với Redis ($10/tháng): key `budget:{user}:{YYYY-MM}`, sang tháng dùng key mới nên tự reset, `expire` 32 ngày. Đọc, so sánh và cộng cần gộp trong một Lua script để atomic.
- Cần cả rate limit và cost guard: gọi chậm nhưng prompt dài vẫn tốn nhiều tiền, gọi dồn dập bằng câu ngắn thì rẻ nhưng làm nghẽn server.

```text
$ curl -s http://localhost:8000/me/usage -H "Authorization: Bearer $TOKEN"
{"user_id":"student","date":"2026-11-25","requests":10,"input_tokens":22,"output_tokens":308,"cost_usd":0.000188,"budget_usd":1.0,"budget_remaining_usd":0.999812,"budget_used_pct":0.0}
```

- `requests` là 10: các request bị 429 không gọi LLM nên không bị tính tiền.
- Kiểm tra chi phí: 22/1000 × 0.00015 + 308/1000 × 0.0006 ≈ 0.000188 USD, khớp `cost_usd`.
- `/ask` ở Exercise 4.2 trả `budget_remaining_usd` là 1.9e-05 sau request đầu tiên, trong khi `/me/usage` trả 0.999812 sau 10 request. Điều này xác nhận `/ask` đang trả số đã tiêu.

## Part 5: Scaling & Reliability

### Exercise 5.1: Health checks

| | `/health` (liveness) | `/ready` (readiness) |
|---|---|---|
| Câu hỏi | Process còn sống không? | Nhận request được chưa? |
| Khi fail | Platform restart container | Load balancer ngừng gửi traffic, không restart |
| Khi Redis chết | Vẫn 200 | 503 |

Nếu `/health` fail theo Redis thì platform restart agent liên tục, trong khi restart agent không sửa được Redis.

Log server của bản develop khi gọi hai endpoint:

```text
INFO:     127.0.0.1:53604 - "GET /health HTTP/1.1" 200 OK
INFO:     127.0.0.1:53618 - "GET /ready HTTP/1.1" 200 OK
```

### Exercise 5.2: Graceful shutdown

Gửi một request mất khoảng 3 giây, sau 1 giây gửi SIGTERM bằng `pkill -TERM -f "python app.py"`. Log server:

```text
INFO:     Shutting down
INFO:     127.0.0.1:46082 - "POST /ask?question=Long%20task HTTP/1.1" 200 OK
INFO:     Waiting for application shutdown.
2026-11-25 09:17:20,005 INFO 🔄 Graceful shutdown initiated...
2026-11-25 09:17:20,005 INFO ✅ Shutdown complete
INFO:     Application shutdown complete.
INFO:     Finished server process [9398]
2026-11-25 09:17:20,005 INFO Received signal 15 — uvicorn will handle graceful shutdown
exit code: 0
```

- Dòng `200 OK` nằm sau `Shutting down`: request đang chạy vẫn hoàn thành rồi server mới tắt. Exit code là 0.
- Uvicorn chờ tối đa 30 giây (`timeout_graceful_shutdown`, `develop/app.py` L198), sau đó `lifespan` mới dọn dẹp.
- `Received signal 15` nằm cuối vì uvicorn giữ quyền xử lý tín hiệu khi đang chạy và phát lại tín hiệu sau khi tắt xong.
- Hạn chế: `/ask` là `async def` nhưng gọi hàm chặn (L94–97), nên trong lúc đó các request khác, kể cả `/health`, phải chờ.

### Exercise 5.3: Stateless design

- Nếu lưu history trong RAM, request sau vào instance khác sẽ không thấy history.
- Bản production lưu session vào Redis (`save_session`, `load_session`, `production/app.py` L59–73), key `session:<id>`, hết hạn sau 1 giờ.
- Hạn chế: không kết nối được Redis lúc khởi động thì app dùng RAM và `/ready` vẫn 200 (L42–45, L208–215); `append_to_history` đọc, sửa rồi ghi lại nên request song song có thể ghi đè nhau (L76–90); `turn` lệch 1 (L154).

### Exercise 5.4: Load balancing

Chạy `docker compose -p k5-day14-scaling up -d --build --scale agent=3`. Kết quả `ps` (rút gọn cột):

```text
NAME                       STATUS                    PORTS
k5-day14-scaling-agent-1   Up 21 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-2   Up 20 seconds (healthy)   8000/tcp
k5-day14-scaling-agent-3   Up 20 seconds (healthy)   8000/tcp
k5-day14-scaling-nginx-1   Up 20 seconds             0.0.0.0:8080->80/tcp
k5-day14-scaling-redis-1   Up 31 seconds (healthy)   6379/tcp
```

10 request `POST /chat` qua Nginx (in `served_by` và `storage`):

```text
instance-c40fe3 redis
instance-ec76f8 redis
instance-cd97a9 redis
instance-c40fe3 redis
instance-ec76f8 redis
instance-cd97a9 redis
instance-c40fe3 redis
instance-ec76f8 redis
instance-cd97a9 redis
instance-c40fe3 redis
```

Nginx chia round-robin: 3 instance luân phiên, số request là 4, 3 và 3. Nginx phân giải tên `agent` lúc khởi động nên scale thêm sau đó thì phải reload hoặc restart nginx.

### Exercise 5.5: Test stateless

```text
$ python3 test_stateless.py
Request 1: [instance-ec76f8]
Request 2: [instance-cd97a9]
Request 3: [instance-c40fe3]
Request 4: [instance-ec76f8]
Request 5: [instance-cd97a9]
Total requests: 5
Instances used: {'instance-cd97a9', 'instance-ec76f8', 'instance-c40fe3'}
✅ All requests served despite different instances!
Total messages: 10
✅ Session history preserved across all instances via Redis!
```

(Đã lược phần nội dung câu hỏi và câu trả lời.)

5 request của cùng một session đi qua cả 3 instance nhưng history vẫn đủ 10 message (5 câu hỏi, 5 câu trả lời), vì history nằm trong Redis. Script không tự tắt instance nào nên kết quả này chứng minh state dùng chung giữa các instance, chưa kiểm tra trường hợp một instance chết.

## Part 6: Final Project

Output của `python check_production_ready.py` (bản đầy đủ, có Docker, chạy trong `06-lab-complete/`):

```text
================================================================
  📋 Checklist Deliverable
     ✅ Dockerfile (multi-stage, < 500 MB)
     ✅ docker-compose.yml (agent + redis)
     ✅ .dockerignore
     ✅ Health check endpoint (GET /health)
     ✅ Readiness endpoint (GET /ready)
     ✅ API Key authentication
     ✅ Rate limiting
     ✅ Cost guard
     ✅ Config từ environment variables
     ✅ Structured logging
     ✅ Graceful shutdown
     ✅ Public URL ready (Railway / Render config)
----------------------------------------------------------------
  Result: 12/12 tiêu chí đạt · 41/41 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
================================================================
```

Số đo từ script: image 238 MB, `docker stop` exit code 0 sau 0.9s.

Sau khi xoá chú thích trong `.dockerignore` và deploy, chạy lại kèm `--public-url`:

```text
  Result: 12/12 tiêu chí đạt · 42/42 checks passed
  🎉 PASS 12/12 — PRODUCTION READY! Deploy nào!
```

Giữa hai lần này có một lần chạy chỉ đạt 6/12 (35/41). Code không đổi và lần chạy sau đạt 12/12; chưa xác định được nguyên nhân, nghi là Redis tạm của script không kết nối được.

## Part 7: Benchmark & Observability

Số liệu và nhận xét nằm trong [BENCHMARK_REPORT.md](BENCHMARK_REPORT.md).

### Exercise 7.1: Đọc metrics

Đã thêm Histogram `agent_question_length_chars` vào `develop/app.py`. Output sau một câu hỏi 40 ký tự (lược bớt bucket):

```text
http_requests_total{method="POST",route="/ask",status="200"} 1.0
agent_in_flight_requests 0.0
agent_question_length_chars_bucket{le="20.0"} 0.0
agent_question_length_chars_bucket{le="50.0"} 1.0
agent_question_length_chars_bucket{le="+Inf"} 1.0
agent_question_length_chars_count 1.0
agent_question_length_chars_sum 40.0
```

1. Counter: `http_requests_total` (chỉ tăng). Gauge: `agent_in_flight_requests` (lên xuống). Histogram: `agent_question_length_chars` (bucket cộng dồn).
2. Nếu dùng URL thật làm label, bot gọi hàng nghìn URL lạ sẽ tạo hàng nghìn time series, Prometheus tốn RAM. Dùng `route.path` và gom phần còn lại vào `unmatched` giữ số series nhỏ.

### Exercise 7.4: Observability stack

Stack 2 instance, Locust 30 users / ramp up 5. Số lấy từ Prometheus khi đang có tải (p95 và avg tính bằng giây):

```text
p95:          0.29267
avg:          0.2324
error_rate:   0.01055
rps_instance: 172.19.0.7:8000 = 9.52727, 172.19.0.8:8000 = 9.43636
tokens/s:     input = 1387.45455, output = 738.25455
cost_gio:     1.88151
GET /metrics qua nginx: 404
```

1. p95 khoảng 293 ms, avg khoảng 232 ms. Phần lớn request nhanh, nhưng avg bị khoảng 3% request chậm 1.7 giây kéo lên. p95 chưa chạm nhóm này vì nhóm chậm chưa tới 5%, nên phải xem thêm p99 mới thấy tail latency. p95 của Prometheus là giá trị nội suy trong bucket nên chỉ gần đúng.
2. Có. Hai instance nhận 9.53 và 9.44 request/giây, chênh khoảng 1%.
3. Input gồm system prompt, tài liệu retrieval và câu hỏi, còn output chỉ là câu trả lời ngắn. Input/output khoảng 1.9 lần.
4. 404. Nginx chặn `/metrics` vì metric lộ route, lưu lượng và phiên bản. Prometheus lấy trực tiếp từ agent trong mạng nội bộ.

## AI log

| Phần | Hỏi gì | Nhận gì | Tự sửa / tự kiểm tra |
|------|--------|---------|----------------------|
| Part 1 | Hướng dẫn Exercise 1.1–1.3, lỗi cài requirements, ý nghĩa log 422 và traceback khi nhấn Ctrl+C (Claude Code) | Hướng dẫn từng bước, cách dùng venv trong WSL, bản nháp câu trả lời và bảng so sánh | Tự chạy bản develop, gọi `/ask` (query và JSON) và `/health`. Tự chạy bản production, gọi `/health` và `/ask`, thử `PORT=8001 ENVIRONMENT=staging`. TODO: ghi phần bạn tự sửa |
| Part 2 | Hướng dẫn Exercise 2.1–2.4 (Claude Code) | Các lệnh chạy, cách sửa lỗi Docker trong WSL, bản nháp câu trả lời 2.1, 2.3 và sơ đồ 2.4, tính % giảm kích thước | Tự build hai image và đo bằng `docker images`, tự chạy container develop và gọi `/ask`, `/health`, tự chạy stack Compose và gọi qua Nginx. TODO: ghi phần bạn tự sửa |
| Part 3 | Hướng dẫn deploy Railway, Exercise 3.2 và 3.3 (Claude Code) | Các lệnh deploy, bản nháp phần so sánh và mô tả pipeline. Đọc log build lỗi trên Railway: AI đoán sai là do chú thích tiếng Việt trong `06-lab-complete/.dockerignore` và đã xoá khối chú thích, deploy lại vẫn lỗi; sau đó tìm thấy báo cáo cùng lỗi khi upload từ thư mục Windows và gợi ý upload từ thư mục Linux, làm theo thì service Online | Tự tạo project, Redis, đặt biến môi trường, deploy và chạy 4 lệnh tự kiểm (200, 200, 401, 200). TODO: ghi phần bạn đối chiếu file cấu hình và tự sửa |
| Part 4 | Hướng dẫn Exercise 4.1–4.4 (Claude Code) | Các lệnh chạy, bản nháp câu trả lời 4.1–4.4 | Tự chạy bản develop và gọi `/ask` không key, sai key, đúng key. Tự chạy bản production, lấy token, gọi `/ask` (401, 403, 200), chạy vòng lặp tới 429 và xem `/me/usage`. TODO: ghi phần bạn tự sửa |
| Part 5 | Hướng dẫn Exercise 5.1–5.5 (Claude Code) | Các lệnh chạy, bản nháp câu trả lời 5.1–5.5 | Tự chạy bản develop, gọi `/health`, `/ready`, thử SIGTERM khi có request đang chạy. Tự chạy stack 3 instance, gọi 10 request và chạy `test_stateless.py`. TODO: ghi phần bạn tự sửa |
| Part 6 | Hướng dẫn làm `06-lab-complete/`, lỗi cài `pydantic` trên Python 3.14 (Claude Code) | Code gợi ý kèm giải thích cho 6 file trong `app/`, `Dockerfile`, `.dockerignore`, `docker-compose.yml`, `railway.toml`; cách xử lý môi trường Python | Đưa code vào dự án, tự chạy `check_production_ready.py`: 7/12 ở chế độ `--skip-docker`, sau đó PASS 12/12 bản đầy đủ. TODO: ghi phần bạn tự sửa và tự kiểm tra thêm |
| Part 7 (Bước 1) | Hướng dẫn Exercise 7.1–7.3 (Claude Code) | Code metric `agent_question_length_chars`, hai tài liệu thêm vào `KNOWLEDGE_BASE` (theo lời giải mẫu), file `.github/workflows/eval.yml` do Claude tạo, bản nháp nhận xét trong `BENCHMARK_REPORT.md`, cách tìm nút thắt ở mức 100 | Đưa code vào dự án, tự chạy load test 4 mức, 3 mức `MOCK_SLOW_RATE`, eval v1, v2 và v2 sau khi sửa. TODO: ghi phần bạn tự sửa |
| Part 7 (Bước 2) | Hướng dẫn Exercise 7.4–7.7, lỗi Locust nhận toàn 502 (Claude Code) | Các lệnh chạy. Claude đọc log thấy agent crash `No module named 'uvicorn'` và thêm `ENV PYTHONUSERBASE=/home/agent/.local` vào `benchmark-observability/production/Dockerfile` | Lần chạy Locust đầu tiên bị 502 toàn bộ nên bỏ. Lần hai bị loại vì Prometheus cho thấy số instance sai (`docker compose run` đưa agent về 2 replica). Lần ba đo lại với `--no-deps`, tự kiểm tra đúng 1 và 3 instance. Tự chụp Grafana, Jaeger, Prometheus; tự chạy thí nghiệm A, B, E (lần đầu của E bị loại vì chạy sai thư mục). TODO: ghi phần bạn tự kiểm tra |
