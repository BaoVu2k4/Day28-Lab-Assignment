# scripts/capture_screenshots.py
# Chụp screenshot các dashboard/UI bằng Playwright headless -> screenshots/*.png
# Không cần Chrome extension. Chạy: python scripts/capture_screenshots.py
import os
import sys
import time

from playwright.sync_api import sync_playwright

try:
    sys.stdout.reconfigure(encoding="utf-8")
except Exception:  # noqa: BLE001
    pass

OUT = os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "screenshots")
os.makedirs(OUT, exist_ok=True)

# (tên file, URL, giây chờ thêm cho JS render)
PAGES = [
    ("api_docs.png",          "http://localhost:8000/docs", 3),
    ("grafana_dashboard.png", "http://localhost:3000/d/lab28-overview/ai-platform-lab28-overview?orgId=1&refresh=5s&from=now-5m&to=now&kiosk", 8),
    ("prometheus_targets.png","http://localhost:9090/targets", 3),
    ("qdrant_dashboard.png",  "http://localhost:6333/dashboard#/collections", 4),
    ("prefect_ui.png",        "http://localhost:4200/flow-runs", 6),
]


def main():
    with sync_playwright() as p:
        browser = p.chromium.launch(args=["--no-sandbox"])
        ctx = browser.new_context(viewport={"width": 1600, "height": 1000})
        page = ctx.new_page()
        for name, url, wait_s in PAGES:
            try:
                page.goto(url, wait_until="networkidle", timeout=45000)
            except Exception as e:  # noqa: BLE001
                print(f"[warn] {name}: networkidle timeout ({e}); tiếp tục")
            time.sleep(wait_s)
            path = os.path.join(OUT, name)
            page.screenshot(path=path)
            print(f"[ok] {name} <- {url}")
        browser.close()
    print(f"\nĐã lưu screenshots vào {OUT}")


if __name__ == "__main__":
    main()
