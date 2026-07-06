# scripts/run_all_pipeline.py
# Orchestrator: chạy toàn bộ luồng data end-to-end trên host theo đúng thứ tự.
#   01 ingest -> 02 consume->delta -> 03 delta->feast -> 05 embed->qdrant
import runpy
import sys
import time

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

STEPS = [
    ("Integration 1: Ingest -> Kafka", "scripts/01_ingest_to_kafka.py"),
    ("Integration 2: Kafka -> Delta Lake", "scripts/02_consume_to_delta.py"),
    ("Integration 3+4: Delta Lake -> Feast", "scripts/03_delta_to_feast.py"),
    ("Integration 5: Embed -> Qdrant", "scripts/05_embed_to_qdrant.py"),
]


def main():
    for title, path in STEPS:
        print("\n" + "=" * 60)
        print(f">>> {title}  ({path})")
        print("=" * 60)
        runpy.run_path(path, run_name="__main__")
        time.sleep(1)
    print("\n" + "=" * 60)
    print("PIPELINE HOÀN TẤT: dữ liệu đã chảy qua toàn bộ 5 integration đầu tiên.")
    print("=" * 60)


if __name__ == "__main__":
    sys.exit(main())
