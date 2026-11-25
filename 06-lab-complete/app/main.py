import json
import logging
import sys
import time
from contextlib import asynccontextmanager
from datetime import datetime, timezone

from fastapi import Depends, FastAPI, HTTPException, Request
from fastapi.responses import JSONResponse
from pydantic import BaseModel, ConfigDict, Field
from redis.exceptions import RedisError

from app.auth import verify_api_key
from app.config import settings
from app.cost_guard import check_budget, record_cost
from app.rate_limiter import check_rate_limit
from app.redis_client import r, redis_healthy
from utils.mock_llm import ask as llm_ask


class JsonFormatter(logging.Formatter):
    def format(self, record):
        entry = {
            "ts": datetime.fromtimestamp(record.created, timezone.utc).isoformat(),
            "lvl": record.levelname,
            "event": record.getMessage(),
        }
        entry.update(getattr(record, "fields", {}))
        if record.exc_info:
            entry["exc"] = self.formatException(record.exc_info)
        return json.dumps(entry, ensure_ascii=False)


_handler = logging.StreamHandler(sys.stdout)
_handler.setFormatter(JsonFormatter())
logging.basicConfig(level=logging.INFO, handlers=[_handler], force=True)
logger = logging.getLogger("agent")


def log(event: str, level: int = logging.INFO, **fields):
    logger.log(level, event, extra={"fields": fields})


@asynccontextmanager
async def lifespan(app: FastAPI):
    log("startup", environment=settings.environment)
    yield
    r.close()
    log("shutdown")


app = FastAPI(title="Production AI Agent", lifespan=lifespan)


@app.middleware("http")
async def log_requests(request: Request, call_next):
    start = time.perf_counter()
    status = 500
    try:
        response = await call_next(request)
        status = response.status_code
        return response
    finally:
        ms = round((time.perf_counter() - start) * 1000, 1)
        log("request", method=request.method, path=request.url.path, status=status, ms=ms)


@app.exception_handler(RedisError)
async def redis_error(request: Request, exc: RedisError):
    log("redis_error", logging.ERROR, error=type(exc).__name__)
    return JSONResponse(status_code=503, content={"detail": "Service temporarily unavailable"})


class AskRequest(BaseModel):
    model_config = ConfigDict(str_strip_whitespace=True)
    question: str = Field(..., min_length=1, max_length=2000)


@app.get("/health")
async def health():
    return {"status": "ok"}


@app.get("/ready")
def ready():
    if not redis_healthy():
        raise HTTPException(status_code=503, detail="Redis not available")
    return {"ready": True}


@app.post("/ask")
def ask(body: AskRequest, api_key: str = Depends(verify_api_key)):
    check_rate_limit(api_key)
    check_budget()
    answer = llm_ask(body.question)
    record_cost(len(body.question.split()) * 2, len(answer.split()) * 2)
    return {"question": body.question, "answer": answer}
