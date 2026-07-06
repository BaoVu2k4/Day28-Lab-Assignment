# scripts/load_test.py
# Sinh traffic tới API Gateway để Grafana/Prometheus có dữ liệu vẽ dashboard.
#   python scripts/load_test.py [số_request]
import sys
import time

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

URL = "http://localhost:8000/api/v1/chat"
QUERIES = [
    "What is platform engineering?",
    "Explain event-driven architecture for AI platforms",
    "How does observability work?",
    "Why use Kafka instead of direct calls?",
    "What is a feature store?",
]


def main(n: int = 40):
    ok = fail = 0
    t0 = time.time()
    for i in range(n):
        q = QUERIES[i % len(QUERIES)]
        try:
            r = requests.post(URL, json={"query": f"{q} (#{i})"}, timeout=30)
            if r.status_code == 200:
                ok += 1
                if i % 10 == 0:
                    print(f"[{i}] {r.json()['latency_ms']} ms | degraded={r.json()['degraded']}")
            else:
                fail += 1
        except Exception as e:  # noqa: BLE001
            fail += 1
            print(f"[{i}] error: {e}")
    dt = time.time() - t0
    print(f"\nLoad test xong: {ok} OK / {fail} fail trong {dt:.1f}s "
          f"(~{n/dt:.1f} req/s). Mở Grafana http://localhost:3000 để xem.")


if __name__ == "__main__":
    n = int(sys.argv[1]) if len(sys.argv) > 1 else 40
    main(n)
