# scripts/05_embed_to_qdrant.py
# Integration 5: Data -> Vector Store (Embeddings -> Qdrant)
import glob
import os
import sys

import requests
import pandas as pd

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass
from qdrant_client import QdrantClient
from qdrant_client.models import Distance, VectorParams, PointStruct

# Mặc định dùng mock embedding local (8002). Đổi EMBED_NGROK_URL sang Kaggle nếu có.
EMBED_URL = os.environ.get("EMBED_NGROK_URL") or os.environ.get("EMBED_URL") or "http://localhost:8002"
EMBED_URL = EMBED_URL.rstrip("/")
QDRANT_HOST = os.environ.get("QDRANT_HOST", "localhost")
QDRANT_PORT = int(os.environ.get("QDRANT_PORT", "6333"))
DELTA_PATH = os.environ.get("DELTA_PATH", "delta-lake/raw")
COLLECTION = "documents"
VECTOR_SIZE = 384

qdrant = QdrantClient(host=QDRANT_HOST, port=QDRANT_PORT)


def ensure_collection():
    qdrant.recreate_collection(
        collection_name=COLLECTION,
        vectors_config=VectorParams(size=VECTOR_SIZE, distance=Distance.COSINE),
    )


def load_records() -> list[dict]:
    """Ưu tiên đọc doc đã ingest từ Delta Lake; fallback sample cứng."""
    files = glob.glob(os.path.join(DELTA_PATH, "*.parquet"))
    if files:
        df = pd.concat([pd.read_parquet(f) for f in files]).drop_duplicates(subset=["id"])
        return df[["id", "text"]].to_dict("records")
    return [
        {"id": "doc_001", "text": "AI platform integration test"},
        {"id": "doc_002", "text": "Kafka to Airflow pipeline"},
    ]


def embed_and_store(records: list[dict]):
    resp = requests.post(f"{EMBED_URL}/embed", json={"texts": [r["text"] for r in records]}, timeout=30)
    resp.raise_for_status()
    embeddings = resp.json()["embeddings"]

    points = [
        PointStruct(id=i, vector=emb, payload=rec)
        for i, (emb, rec) in enumerate(zip(embeddings, records))
    ]
    qdrant.upsert(collection_name=COLLECTION, points=points)
    print(f"Integration 5 OK: {len(points)} vectors stored in Qdrant collection '{COLLECTION}'")


if __name__ == "__main__":
    ensure_collection()
    recs = load_records()
    print(f"Embedding {len(recs)} records qua {EMBED_URL} ...")
    embed_and_store(recs)
