# Deployment Information

## Public URL

https://agent-production-44f3e8e0.up.railway.app

## Platform

Railway. Project có hai service: `agent` (build từ `06-lab-complete/Dockerfile`) và `Redis`. Agent gọi Redis qua `REDIS_URL`.

## Test Commands

```bash
BASE=https://agent-production-44f3e8e0.up.railway.app
```

### Health và readiness

```bash
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/health"     # 200
curl -sS -o /dev/null -w '%{http_code}\n' "$BASE/ready"      # 200
```

### API (có xác thực)

```bash
# Không có key: 401
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -d '{"question":"Hello"}'

# Có key: 200
curl -sS -o /dev/null -w '%{http_code}\n' -X POST "$BASE/ask" -H 'Content-Type: application/json' -H "X-API-Key: $AGENT_API_KEY" -d '{"question":"Hello"}'
```

### Kết quả

```text
URL: https://agent-production-44f3e8e0.up.railway.app
health          200
ready           200
ask khong key   401
ask co key      200
```

## Environment Variables Set

Đặt trên Railway cho service `agent`, không ghi giá trị secret trong repo:

- `AGENT_API_KEY` (secret, sinh ngẫu nhiên)
- `REDIS_URL` (tham chiếu `${{Redis.REDIS_URL}}`)
- `ENVIRONMENT`
- `PORT`
- `RATE_LIMIT_PER_MINUTE`
- `DAILY_BUDGET_USD`

## Deploy

Chạy Railway CLI trên ổ Linux. Upload từ thư mục Windows (`/mnt/...`) bị lỗi build `header key "exclude-patterns" contains value with non-printable ASCII characters`.

```bash
# Chạy từ thư mục 06-lab-complete/
mkdir -p ~/day14-deploy
cp -r Dockerfile .dockerignore railway.toml requirements.txt app utils ~/day14-deploy/
cd ~/day14-deploy
railway link -p day14-agent -e production -s agent
railway up . --path-as-root -s agent --detach
railway domain --port 8000 -s agent
```

## Screenshots

- [Deployment dashboard](screenshots/dashboard.png)
- [Service running](screenshots/running.png)
- [Test results](screenshots/test.png)
