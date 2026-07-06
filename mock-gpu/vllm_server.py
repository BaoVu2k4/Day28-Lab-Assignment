# mock-gpu/vllm_server.py
# -----------------------------------------------------------------------------
# Mock vLLM server — OpenAI-compatible API.
#
# Thay thế cho vLLM chạy trên Kaggle GPU khi không có GPU / không có ngrok.
# Cung cấp đúng contract mà API Gateway mong đợi:
#   - POST /v1/chat/completions   (OpenAI Chat Completions schema)
#   - GET  /v1/models
#   - GET  /health
#   - GET  /metrics               (Prometheus)
#
# Trên production thật: đổi VLLM_URL trong .env sang ngrok URL của Kaggle,
# contract giống hệt nên API Gateway không cần sửa gì.
# -----------------------------------------------------------------------------
import time
import os
import hashlib

from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

MODEL_NAME = os.environ.get("MOCK_MODEL_NAME", "Qwen/Qwen2.5-7B-Instruct-GPTQ-Int4")

app = FastAPI(title="Mock vLLM Server (OpenAI-compatible)")
Instrumentator().instrument(app).expose(app)


class Message(BaseModel):
    role: str
    content: str


class ChatRequest(BaseModel):
    model: str | None = None
    messages: list[Message]
    max_tokens: int | None = 256
    temperature: float | None = 0.7


def _generate_answer(prompt: str) -> str:
    """Sinh câu trả lời tất định (deterministic) dựa trên nội dung prompt.

    Không phải LLM thật nhưng đủ để chứng minh luồng end-to-end: nhận context
    từ vector search + query của user và trả lời mạch lạc, dài > 10 ký tự.
    """
    p = prompt.lower()
    # Vài "tri thức" đóng gói sẵn để câu trả lời trông có ý nghĩa.
    if "event-driven" in p or "kafka" in p:
        topic = (
            "Event-driven architecture decouples producers and consumers through "
            "a message broker such as Kafka. Producers publish events to topics "
            "without knowing who consumes them, enabling replay, back-pressure "
            "handling, and independent scaling of each stage in the AI platform."
        )
    elif "platform engineering" in p or "platform" in p:
        topic = (
            "Platform engineering builds the paved-road infrastructure that lets "
            "ML teams ship models reliably: ingestion, feature stores, vector "
            "databases, model serving, and full observability — all wired together "
            "so a request flows end-to-end with metrics, traces, and fallbacks."
        )
    elif "observability" in p or "metric" in p:
        topic = (
            "Observability rests on three pillars — metrics (Prometheus), logs, "
            "and traces (LangSmith). Together they answer what broke, where, and "
            "why, and drive alerting and SLO dashboards in Grafana."
        )
    else:
        topic = (
            "This is a mock LLM response generated locally to demonstrate the "
            "full request path: API Gateway -> vector search -> LLM inference. "
            "Swap VLLM_URL to a real Kaggle vLLM endpoint for production answers."
        )

    # Trích query của user (dòng cuối cùng thường là 'Query: ...').
    user_q = prompt.strip().splitlines()[-1] if prompt.strip() else ""
    return f"{topic}\n\n(Answering: {user_q[:160]})"


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL_NAME, "backend": "mock-vllm"}


@app.get("/v1/models")
def list_models():
    return {
        "object": "list",
        "data": [{"id": MODEL_NAME, "object": "model", "owned_by": "lab28-mock"}],
    }


@app.post("/v1/chat/completions")
def chat_completions(req: ChatRequest):
    prompt = "\n".join(m.content for m in req.messages)
    answer = _generate_answer(prompt)

    # Ước lượng token đơn giản để response giống thật.
    prompt_tokens = max(1, len(prompt.split()))
    completion_tokens = max(1, len(answer.split()))
    rid = hashlib.md5(prompt.encode()).hexdigest()[:12]

    return {
        "id": f"chatcmpl-{rid}",
        "object": "chat.completion",
        "created": int(time.time()),
        "model": req.model or MODEL_NAME,
        "choices": [
            {
                "index": 0,
                "message": {"role": "assistant", "content": answer},
                "finish_reason": "stop",
            }
        ],
        "usage": {
            "prompt_tokens": prompt_tokens,
            "completion_tokens": completion_tokens,
            "total_tokens": prompt_tokens + completion_tokens,
        },
    }
