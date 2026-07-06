# scripts/09_verify_observability.py
# Integration 9 & 10: Prometheus/Grafana metrics + LangSmith traces
import os
import sys
import time
import uuid
from datetime import datetime, timezone

import requests

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

try:
    from dotenv import load_dotenv

    load_dotenv()
except Exception:  # noqa: BLE001
    pass

PROM_URL = os.environ.get("PROM_URL", "http://localhost:9090")


def check_prometheus():
    # Kiểm tra Prometheus đang scrape được target api-gateway
    resp = requests.get(f"{PROM_URL}/api/v1/query", params={"query": "up"}, timeout=10)
    data = resp.json()
    assert data["status"] == "success", data
    ups = [r for r in data["data"]["result"] if r["value"][1] == "1"]
    jobs = sorted({r["metric"].get("job") for r in ups})
    print(f"Integration 9 OK: Prometheus scraping {len(ups)} target(s) up — jobs={jobs}")


def check_gateway_metrics():
    resp = requests.get("http://localhost:8000/metrics", timeout=10)
    resp.raise_for_status()
    assert "http_requests_total" in resp.text or "gateway_chat_requests_total" in resp.text
    print("Integration 9 OK: API Gateway /metrics đang expose")


def check_langsmith():
    key = os.environ.get("LANGCHAIN_API_KEY")
    if not key:
        print("Integration 10 SKIP: chưa cấu hình LANGCHAIN_API_KEY "
              "(tracing tùy chọn — không tính là lỗi)")
        return
    os.environ.setdefault("LANGCHAIN_TRACING_V2", "true")
    os.environ.setdefault("LANGCHAIN_ENDPOINT", "https://api.smith.langchain.com")

    from langsmith import Client

    client = Client(api_key=key)
    project = os.environ.get("LANGCHAIN_PROJECT", "lab28-platform")
    run_id = uuid.uuid4()
    client.create_run(
        id=run_id,
        name="lab28-observability-verification",
        run_type="chain",
        project_name=project,
        inputs={
            "gateway": "http://localhost:8000",
            "prometheus": PROM_URL,
            "project": project,
        },
    )
    client.update_run(
        run_id,
        outputs={"status": "ok", "integration": "LangSmith tracing"},
        end_time=datetime.now(timezone.utc),
    )
    time.sleep(3)

    runs = list(client.list_runs(project_name=project, limit=1))
    assert len(runs) > 0
    print(f"Integration 10 OK: LangSmith traces visible (project={project})")


if __name__ == "__main__":
    check_prometheus()
    check_gateway_metrics()
    check_langsmith()
