# prefect/flows/kafka_to_delta.py
# Integration 2: Kafka -> Prefect Pipeline -> Delta Lake
#
# Cách dùng:
#   python kafka_to_delta.py          -> chạy flow ngay (ephemeral)
#   python kafka_to_delta.py deploy   -> deploy + schedule 5 phút/lần lên Orion
#
# Env: KAFKA_BOOTSTRAP (mặc định localhost:9092), DELTA_PATH (delta-lake/raw)
import json
import os
import sys
from datetime import datetime

import pandas as pd
from kafka import KafkaConsumer
from prefect import flow, task

KAFKA_BOOTSTRAP = os.environ.get("KAFKA_BOOTSTRAP", "localhost:9092")
DELTA_PATH = os.environ.get("DELTA_PATH", "delta-lake/raw")
TOPIC = os.environ.get("KAFKA_TOPIC", "data.raw")


@task
def consume_and_process():
    """Consume data từ Kafka topic."""
    consumer = KafkaConsumer(
        TOPIC,
        bootstrap_servers=KAFKA_BOOTSTRAP,
        auto_offset_reset="earliest",
        consumer_timeout_ms=15000,
        value_deserializer=lambda m: json.loads(m.decode()),
        group_id=None,
        enable_auto_commit=False,
    )
    records = [msg.value for msg in consumer]
    consumer.close()
    print(f"Consumed {len(records)} records from Kafka")
    return records


@task
def save_to_delta(records):
    """Lưu records vào Delta Lake (parquet format)."""
    if not records:
        print("No records to save")
        return 0
    df = pd.DataFrame(records)
    os.makedirs(DELTA_PATH, exist_ok=True)
    path = os.path.join(DELTA_PATH, f"batch_{datetime.now().strftime('%Y%m%d_%H%M%S')}.parquet")
    df.to_parquet(path)
    print(f"Saved {len(df)} records to Delta Lake: {path}")
    return len(df)


@flow(name="Kafka to Delta Pipeline")
def kafka_to_delta_flow():
    """Main flow: consume từ Kafka và lưu vào Delta Lake."""
    records = consume_and_process()
    return save_to_delta(records)


if __name__ == "__main__":
    if len(sys.argv) > 1 and sys.argv[1] == "deploy":
        # Deploy + schedule (chạy 5 phút/lần) lên Prefect Orion.
        from prefect.client.schemas.schedules import CronSchedule

        kafka_to_delta_flow.serve(
            name="kafka-to-delta",
            schedule=CronSchedule(cron="*/5 * * * *"),
        )
    else:
        # Chạy flow ngay lập tức (không cần server) — tạo dữ liệu Delta Lake.
        kafka_to_delta_flow()
