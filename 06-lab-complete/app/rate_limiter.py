import hashlib
import math
import time
import uuid

from fastapi import HTTPException

from app.config import settings
from app.redis_client import r

WINDOW_SECONDS = 60

_SCRIPT = r.register_script("""
local now = tonumber(ARGV[1])
local window = tonumber(ARGV[2])
local limit = tonumber(ARGV[3])
redis.call('ZREMRANGEBYSCORE', KEYS[1], '-inf', now - window)
if redis.call('ZCARD', KEYS[1]) >= limit then
    local oldest = redis.call('ZRANGE', KEYS[1], 0, 0, 'WITHSCORES')
    return {0, oldest[2] or ARGV[1]}
end
redis.call('ZADD', KEYS[1], ARGV[1], ARGV[4])
redis.call('EXPIRE', KEYS[1], window)
return {1, ARGV[1]}
""")


def check_rate_limit(key: str) -> None:
    now = time.time()
    redis_key = "ratelimit:" + hashlib.sha256(key.encode()).hexdigest()
    allowed, oldest = _SCRIPT(
        keys=[redis_key],
        args=[now, WINDOW_SECONDS, settings.rate_limit_per_minute, uuid.uuid4().hex],
    )
    if not int(allowed):
        retry_after = max(1, math.ceil(float(oldest) + WINDOW_SECONDS - now))
        raise HTTPException(
            status_code=429,
            detail="Rate limit exceeded",
            headers={"Retry-After": str(retry_after)},
        )
