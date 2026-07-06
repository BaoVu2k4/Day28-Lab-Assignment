# scripts/01_ingest_to_kafka.py
# Integration 1: Data Ingestion -> Kafka
# Chạy trên host: python scripts/01_ingest_to_kafka.py
import json
import os
import sys
import time

from kafka import KafkaProducer

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass
from kafka.errors import NoBrokersAvailable

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "data.raw")


def get_producer(retries: int = 10) -> KafkaProducer:
    """Kết nối Kafka có retry (broker có thể chưa sẵn sàng ngay sau up)."""
    for attempt in range(1, retries + 1):
        try:
            return KafkaProducer(
                bootstrap_servers=BOOTSTRAP,
                value_serializer=lambda v: json.dumps(v).encode(),
                acks="all",
                retries=5,
            )
        except NoBrokersAvailable:
            print(f"[{attempt}/{retries}] Kafka chưa sẵn sàng, thử lại sau 3s...")
            time.sleep(3)
    raise RuntimeError(f"Không kết nối được Kafka tại {BOOTSTRAP}")


def ingest_data(records: list[dict]):
    producer = get_producer()
    for record in records:
        producer.send(TOPIC, value=record)
        print(f"Sent: {record['id']}")
    producer.flush()
    producer.close()


SAMPLE_DATA = [
    {"id": "doc_001", "text": "AI platform integration test", "timestamp": time.time()},
    {"id": "doc_002", "text": "Kafka to Airflow pipeline", "timestamp": time.time()},
    {"id": "doc_003", "text": "Event-driven architecture decouples producers and consumers", "timestamp": time.time()},
    {"id": "doc_004", "text": "Platform engineering builds paved-road infrastructure for ML teams", "timestamp": time.time()},
    {"id": "doc_005", "text": "Observability relies on metrics, logs and traces", "timestamp": time.time()},
]


if __name__ == "__main__":
    ingest_data(SAMPLE_DATA)
    print(f"Integration 1 OK: {len(SAMPLE_DATA)} records -> Kafka topic '{TOPIC}'")
