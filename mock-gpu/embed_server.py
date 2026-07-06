# mock-gpu/embed_server.py
# -----------------------------------------------------------------------------
# Mock embedding server — thay cho sentence-transformers trên Kaggle GPU.
#
# Contract giống hệt service Kaggle trong đề bài:
#   - POST /embed  {"texts": [...]} -> {"embeddings": [[384 floats], ...]}
#   - GET  /health
#   - GET  /metrics  (Prometheus)
#
# Vector 384 chiều được sinh tất định từ hash của text (đủ để vector search
# hoạt động và tái lập được). Đổi EMBED_URL sang Kaggle để dùng model thật.
# -----------------------------------------------------------------------------
import hashlib
import math

from fastapi import FastAPI
from pydantic import BaseModel
from prometheus_fastapi_instrumentator import Instrumentator

VECTOR_SIZE = 384

app = FastAPI(title="Mock Embedding Server")
Instrumentator().instrument(app).expose(app)


class EmbedRequest(BaseModel):
    texts: list[str]


def _embed_one(text: str) -> list[float]:
    """Sinh vector 384 chiều tất định + đã chuẩn hoá L2 từ hash SHA-256.

    Cùng một text luôn cho cùng một vector (quan trọng để vector search
    có kết quả nhất quán giữa lần ingest và lần query).
    """
    vec: list[float] = []
    counter = 0
    while len(vec) < VECTOR_SIZE:
        h = hashlib.sha256(f"{text}::{counter}".encode()).digest()
        for b in h:
            # map byte 0..255 -> khoảng [-1, 1]
            vec.append((b / 127.5) - 1.0)
            if len(vec) >= VECTOR_SIZE:
                break
        counter += 1

    norm = math.sqrt(sum(v * v for v in vec)) or 1.0
    return [v / norm for v in vec]


@app.get("/health")
def health():
    return {"status": "ok", "backend": "mock-embed", "dim": VECTOR_SIZE}


@app.post("/embed")
def embed(req: EmbedRequest):
    return {"embeddings": [_embed_one(t) for t in req.texts]}
