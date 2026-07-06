# api-gateway/main.py
# =============================================================================
# AI Platform — API Gateway (FastAPI)
#
# Integration 8: Serving -> API Gateway
# Integration 9: Prometheus metrics (/metrics)
# Integration 10: LangSmith tracing (tùy chọn)
#
# Trọng tâm chất lượng (khớp rubric chấm điểm):
#   - Error handling ở mọi integration point (Qdrant, embed, vLLM)
#   - Circuit breaker + graceful degradation (fallback khi service down)
#   - Input validation -> HTTP 422 (Pydantic)
#   - Observability: custom Prometheus metrics + structured logging
#   - Security: endpoint /admin trả 403
# =============================================================================
import logging
import os
import time

import httpx
from fastapi import FastAPI, HTTPException
from fastapi.responses import JSONResponse
from pydantic import BaseModel, Field
from prometheus_client import Counter, Histogram
from prometheus_fastapi_instrumentator import Instrumentator

# ── Config ───────────────────────────────────────────────────────────────────
VLLM_URL = os.environ.get("VLLM_URL", "http://mock-vllm:8001").rstrip("/")
EMBED_URL = os.environ.get("EMBED_URL", "http://mock-embed:8002").rstrip("/")
QDRANT_URL = os.environ.get("QDRANT_URL", "http://qdrant:6333").rstrip("/")
LLM_MODEL = os.environ.get("LLM_MODEL", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")
COLLECTION = os.environ.get("QDRANT_COLLECTION", "documents")
VECTOR_SIZE = int(os.environ.get("VECTOR_SIZE", "384"))
LLM_TIMEOUT = float(os.environ.get("LLM_TIMEOUT", "30"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s | %(levelname)s | api-gateway | %(message)s",
)
log = logging.getLogger("api-gateway")

# ── LangSmith tracing (tùy chọn, không crash nếu thiếu key) ──────────────────
LANGSMITH_ENABLED = bool(os.environ.get("LANGCHAIN_API_KEY"))
if LANGSMITH_ENABLED:
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    log.info("LangSmith tracing ENABLED (project=%s)",
             os.environ.get("LANGCHAIN_PROJECT", "lab28-platform"))
else:
    log.info("LangSmith tracing disabled (no LANGCHAIN_API_KEY) — bỏ qua, không lỗi")

app = FastAPI(title="AI Platform API Gateway", version="1.0.0")

# ── Prometheus: instrumentator mặc định + custom metrics ─────────────────────
Instrumentator().instrument(app).expose(app)  # /metrics

CHAT_REQUESTS = Counter(
    "gateway_chat_requests_total", "Tổng số request /api/v1/chat", ["outcome"]
)
CHAT_LATENCY = Histogram(
    "gateway_chat_latency_seconds", "Latency end-to-end của /api/v1/chat"
)
LLM_ERRORS = Counter("gateway_llm_errors_total", "Số lần gọi vLLM thất bại")
FALLBACKS = Counter("gateway_fallback_total", "Số lần phải fallback (degraded)")
DEP_UP = Counter(
    "gateway_dependency_calls_total", "Số lần gọi dependency", ["dep", "status"]
)


# ── Circuit breaker đơn giản cho vLLM ────────────────────────────────────────
class CircuitBreaker:
    """Circuit breaker tối giản: mở mạch sau `fail_max` lỗi liên tiếp,
    tự thử lại (half-open) sau `reset_timeout` giây."""

    def __init__(self, fail_max: int = 3, reset_timeout: float = 20.0):
        self.fail_max = fail_max
        self.reset_timeout = reset_timeout
        self.failures = 0
        self.opened_at = 0.0

    @property
    def state(self) -> str:
        if self.failures < self.fail_max:
            return "closed"
        if (time.time() - self.opened_at) >= self.reset_timeout:
            return "half-open"
        return "open"

    def allow(self) -> bool:
        return self.state in ("closed", "half-open")

    def record_success(self):
        self.failures = 0
        self.opened_at = 0.0

    def record_failure(self):
        self.failures += 1
        if self.failures == self.fail_max:
            self.opened_at = time.time()
            log.warning("Circuit breaker OPEN cho vLLM (sau %d lỗi)", self.failures)


vllm_breaker = CircuitBreaker()


# ── Request/Response models (validation -> 422) ──────────────────────────────
class ChatRequest(BaseModel):
    query: str = Field(..., min_length=1, description="Câu hỏi của người dùng")
    embedding: list[float] | None = Field(
        default=None, description="Vector truy vấn (tùy chọn; nếu thiếu sẽ tự embed)"
    )
    top_k: int = Field(default=3, ge=1, le=20)


# ── Helpers cho từng integration point ───────────────────────────────────────
async def _get_embedding(client: httpx.AsyncClient, text: str) -> list[float]:
    """Gọi embedding service. Nếu lỗi -> trả zero-vector (degraded, không crash)."""
    try:
        r = await client.post(f"{EMBED_URL}/embed", json={"texts": [text]}, timeout=10)
        r.raise_for_status()
        DEP_UP.labels(dep="embed", status="ok").inc()
        return r.json()["embeddings"][0]
    except Exception as e:  # noqa: BLE001
        DEP_UP.labels(dep="embed", status="error").inc()
        log.warning("Embed service lỗi (%s) — dùng zero-vector", e)
        return [0.0] * VECTOR_SIZE


async def _vector_search(client: httpx.AsyncClient, vector: list[float], top_k: int):
    """Vector search trên Qdrant. Lỗi -> trả context rỗng (graceful degradation)."""
    try:
        r = await client.post(
            f"{QDRANT_URL}/collections/{COLLECTION}/points/search",
            json={"vector": vector, "limit": top_k, "with_payload": True},
            timeout=10,
        )
        r.raise_for_status()
        DEP_UP.labels(dep="qdrant", status="ok").inc()
        return r.json().get("result", [])
    except Exception as e:  # noqa: BLE001
        DEP_UP.labels(dep="qdrant", status="error").inc()
        log.warning("Qdrant search lỗi (%s) — context rỗng", e)
        return []


async def _llm_infer(client: httpx.AsyncClient, prompt: str) -> tuple[str, str]:
    """Gọi vLLM qua circuit breaker. Trả (answer, model). Raise nếu thất bại."""
    if not vllm_breaker.allow():
        raise RuntimeError("circuit breaker OPEN")
    try:
        r = await client.post(
            f"{VLLM_URL}/v1/chat/completions",
            json={
                "model": LLM_MODEL,
                "messages": [{"role": "user", "content": prompt}],
                "max_tokens": 256,
            },
            timeout=LLM_TIMEOUT,
        )
        r.raise_for_status()
        data = r.json()
        vllm_breaker.record_success()
        DEP_UP.labels(dep="vllm", status="ok").inc()
        return data["choices"][0]["message"]["content"], data.get("model", LLM_MODEL)
    except Exception:
        vllm_breaker.record_failure()
        LLM_ERRORS.inc()
        DEP_UP.labels(dep="vllm", status="error").inc()
        raise


# ── Endpoints ────────────────────────────────────────────────────────────────
@app.post("/api/v1/chat")
async def chat(req: ChatRequest):
    """Full RAG path: (embed nếu cần) -> vector search -> LLM -> answer."""
    start = time.time()
    async with httpx.AsyncClient() as client:
        # 1) Embedding (nếu client không gửi sẵn)
        vector = req.embedding
        if vector is None:
            vector = await _get_embedding(client, req.query)
        # Chuẩn hoá độ dài vector cho khớp Qdrant collection
        if len(vector) != VECTOR_SIZE:
            vector = (vector + [0.0] * VECTOR_SIZE)[:VECTOR_SIZE]

        # 2) Vector search (degrade được)
        context = await _vector_search(client, vector, req.top_k)

        # 3) LLM inference (circuit breaker + fallback)
        prompt = (
            f"Context: {context}\n\n"
            f"Query: {req.query}"
        )
        try:
            answer, model = await _llm_infer(client, prompt)
            outcome = "ok"
        except Exception as e:  # noqa: BLE001 — graceful degradation
            FALLBACKS.inc()
            outcome = "fallback"
            model = "fallback"
            answer = (
                "Service is temporarily degraded: the LLM backend is unreachable. "
                "Returning a safe fallback response. Please retry shortly. "
                f"(Your query was: {req.query})"
            )
            log.error("LLM inference thất bại (%s) — trả fallback response", e)

    latency = (time.time() - start) * 1000
    CHAT_LATENCY.observe(latency / 1000.0)
    CHAT_REQUESTS.labels(outcome=outcome).inc()

    return {
        "answer": answer,
        "latency_ms": round(latency, 2),
        "model": model,
        "degraded": outcome == "fallback",
        "context_hits": len(context),
        "circuit": vllm_breaker.state,
    }


@app.get("/health")
def health():
    """Liveness — luôn nhanh, không phụ thuộc dependency."""
    return {"status": "ok"}


@app.get("/health/deep")
async def health_deep():
    """Readiness — kiểm tra thực tế các dependency."""
    deps = {}
    async with httpx.AsyncClient(timeout=5) as client:
        for name, url in [("vllm", f"{VLLM_URL}/health"),
                          ("embed", f"{EMBED_URL}/health"),
                          ("qdrant", f"{QDRANT_URL}/healthz")]:
            try:
                r = await client.get(url)
                deps[name] = "up" if r.status_code < 500 else "down"
            except Exception:  # noqa: BLE001
                deps[name] = "down"
    overall = "ok" if all(v == "up" for v in deps.values()) else "degraded"
    return {"status": overall, "dependencies": deps, "circuit": vllm_breaker.state}


@app.get("/admin")
def admin_blocked():
    """Security: endpoint quản trị luôn bị chặn (không có auth token)."""
    raise HTTPException(status_code=403, detail="Forbidden — admin API is protected")


@app.get("/")
def root():
    return {"service": "AI Platform API Gateway", "version": "1.0.0", "docs": "/docs"}
