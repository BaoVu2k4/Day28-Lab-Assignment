# scripts/02_consume_to_delta.py
# Integration 2: Kafka -> pipeline -> Delta Lake (bản chạy trực tiếp trên host)
#
# Đây là bản pure-python phản chiếu logic của Prefect flow
# (prefect/flows/kafka_to_delta.py), để tạo dữ liệu Delta Lake một cách chắc
# chắn mà không phụ thuộc scheduler. Prefect flow vẫn được deploy song song.
import json
import os
import sys
from datetime import datetime

import pandas as pd
from kafka import KafkaConsumer

# In được tiếng Việt trên console Windows (cp1258) mà không lỗi encoding.
try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
TOPIC = os.environ.get("KAFKA_TOPIC", "data.raw")
DELTA_PATH = os.environ.get("DELTA_PATH", "delta-lake/raw")


def consume_and_process() -> list[dict]:
    # group_id=None => luôn đọc từ earliest, không commit offset: phù hợp
    # batch pipeline demo (mỗi lần chạy đọc lại toàn bộ topic). Timeout 15s để
    # đủ thời gian consumer join + fetch sau khi broker vừa khởi động.
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=BOOTSTRAP,
        auto_offset_reset="earliest",
        consumer_timeout_ms=15000,
        value_deserializer=lambda m: json.loads(m.decode()),
        group_id=None,
        enable_auto_commit=False,
    )
    records = [msg.value for msg in consumer]
    consumer.close()
    print(f"Consumed {len(records)} records from Kafka topic '{TOPIC}'")
    return records


def save_to_delta(records: list[dict]) -> int:
    if not records:
        print("No records to save")
        return 0
    df = pd.DataFrame(records)
    os.makedirs(DELTA_PATH, exist_ok=True)
    out = os.path.join(DELTA_PATH, f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet")
    df.to_parquet(out)
    print(f"Saved {len(df)} records to Delta Lake: {out}")
    return len(df)


if __name__ == "__main__":
    recs = consume_and_process()
    n = save_to_delta(recs)
    print(f"Integration 2 OK: Kafka -> Delta Lake ({n} records)")
