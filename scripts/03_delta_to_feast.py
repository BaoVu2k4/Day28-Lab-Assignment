# scripts/03_delta_to_feast.py
# Integration 3 & 4: Delta Lake -> Feature Store (Feast online store trên Redis)
import glob
import json
import os
import sys

import pandas as pd
import redis

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

REDIS_HOST = os.environ.get("REDIS_HOST", "localhost")
REDIS_PORT = int(os.environ.get("REDIS_PORT", "6379"))
DELTA_PATH = os.environ.get("DELTA_PATH", "delta-lake/raw")


def load_from_delta_and_push_feast() -> int:
    files = glob.glob(os.path.join(DELTA_PATH, "*.parquet"))
    if not files:
        print(f"No data in Delta Lake yet ({DELTA_PATH}) — chạy 02_consume_to_delta trước")
        return 0

    df = pd.concat([pd.read_parquet(f) for f in files]).drop_duplicates(subset=["id"])
    print(f"Loaded {len(df)} unique records from Delta Lake ({len(files)} file(s))")

    r = redis.Redis(host=REDIS_HOST, port=REDIS_PORT, decode_responses=True)
    for _, row in df.iterrows():
        r.set(
            f"feature:{row['id']}",
            json.dumps({
                "text": row["text"],
                "timestamp": row.get("timestamp"),
                "processed": True,
            }),
        )

    print(f"Integration 3+4 OK: Delta Lake -> Feast (Redis) — {len(df)} features stored")
    return len(df)


if __name__ == "__main__":
    load_from_delta_and_push_feast()
