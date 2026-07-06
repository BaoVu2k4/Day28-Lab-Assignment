# scripts/production_readiness_check.py
# Production Readiness Checklist — chạy: python scripts/production_readiness_check.py
import subprocess
import sys

import requests
import redis

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

results = {}


def check(name, fn):
    try:
        fn()
        results[name] = "PASS"
        print(f"  [PASS] {name}")
    except Exception as e:  # noqa: BLE001
        results[name] = f"FAIL: {e}"
        print(f"  [FAIL] {name}: {e}")


print("\n=== RELIABILITY ===")
check("Health check endpoint", lambda:
    requests.get("http://localhost:8000/health", timeout=5).raise_for_status())
check("API Gateway docs responds", lambda:
    requests.get("http://localhost:8000/docs", timeout=5).raise_for_status())


def check_deep_health():
    r = requests.get("http://localhost:8000/health/deep", timeout=10)
    r.raise_for_status()
    assert r.json()["status"] in ("ok", "degraded")


check("Deep health (dependencies)", check_deep_health)


def check_chat_e2e():
    r = requests.post("http://localhost:8000/api/v1/chat",
                      json={"query": "readiness probe"}, timeout=30)
    r.raise_for_status()
    assert len(r.json()["answer"]) > 10


check("End-to-end chat inference", check_chat_e2e)

print("\n=== OBSERVABILITY ===")
check("Prometheus up", lambda:
    requests.get("http://localhost:9090/-/healthy", timeout=5).raise_for_status())
check("Grafana up", lambda:
    requests.get("http://localhost:3000/api/health", timeout=5).raise_for_status())
check("Metrics endpoint exposed", lambda:
    requests.get("http://localhost:8000/metrics", timeout=5).raise_for_status())


def check_custom_metrics():
    txt = requests.get("http://localhost:8000/metrics", timeout=5).text
    assert "gateway_chat_requests_total" in txt


check("Custom gateway metrics present", check_custom_metrics)


def check_prom_scraping():
    r = requests.get("http://localhost:9090/api/v1/query",
                     params={"query": "up{job='api-gateway'}"}, timeout=10)
    res = r.json()["data"]["result"]
    assert res and res[0]["value"][1] == "1"


check("Prometheus scrapes api-gateway", check_prom_scraping)

print("\n=== SECURITY ===")


def check_unauthorized():
    r = requests.get("http://localhost:8000/admin", timeout=5)
    assert r.status_code in [401, 403, 404]


check("Unauthorized/admin request rejected", check_unauthorized)


def check_bad_input():
    r = requests.post("http://localhost:8000/api/v1/chat", json={}, timeout=5)
    assert r.status_code in [400, 422]


check("Invalid input rejected (422)", check_bad_input)

print("\n=== MODEL SERVING (GPU tier) ===")
check("vLLM serving healthy", lambda:
    requests.get("http://localhost:8001/health", timeout=5).raise_for_status())
check("Embedding service healthy", lambda:
    requests.get("http://localhost:8002/health", timeout=5).raise_for_status())

print("\n=== VECTOR STORE ===")
check("Qdrant healthy", lambda:
    requests.get("http://localhost:6333/healthz", timeout=5).raise_for_status())


def check_collection_exists():
    requests.get("http://localhost:6333/collections/documents", timeout=5).raise_for_status()


check("Qdrant collection exists", check_collection_exists)

print("\n=== FEATURE STORE ===")
check("Redis reachable", lambda:
    redis.Redis(host="localhost", port=6379).ping())


def check_features_present():
    r = redis.Redis(host="localhost", port=6379, decode_responses=True)
    assert len(r.keys("feature:*")) > 0


check("Feature store populated", check_features_present)

print("\n=== KAFKA ===")


def check_kafka_topics():
    result = subprocess.run(
        ["docker", "exec", "lab28-kafka-1", "kafka-topics", "--list",
         "--bootstrap-server", "localhost:9092"],
        capture_output=True, text=True,
    )
    assert "data.raw" in result.stdout, result.stdout + result.stderr


check("Kafka topic data.raw exists", check_kafka_topics)

# ── Tổng kết ─────────────────────────────────────────────────────────────────
passed = sum(1 for v in results.values() if v == "PASS")
total = len(results)
score = (passed / total) * 100 if total else 0
print(f"\n{'='*44}")
print(f"Production Readiness Score: {passed}/{total} = {score:.0f}%")
print(f"Target: >80% — Status: {'READY' if score >= 80 else 'NOT READY'}")
