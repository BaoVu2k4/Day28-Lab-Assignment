# smoke-tests/conftest.py — nạp biến môi trường từ .env trước khi test chạy
import os

try:
    from dotenv import load_dotenv

    root = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
    load_dotenv(os.path.join(root, ".env"))
except Exception:  # noqa: BLE001 — dotenv là optional
    pass
