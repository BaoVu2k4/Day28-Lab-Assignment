# Lab #28 — Full Platform Integration Sprint

AI platform hoàn chỉnh, kiến trúc **hybrid** (Local Docker + Kaggle GPU), ghép toàn bộ stack N16–N27: **Kafka → Prefect → Delta Lake → Feast (Redis) → Qdrant → Prometheus/Grafana → API Gateway**, cùng tầng serving **vLLM + Embedding + MLflow** trên GPU.

> **SV:** Vũ Quang Bảo — **MSV:** 2A202600610

---

## 2 chế độ chạy

| Chế độ | vLLM / Embedding | Khi nào dùng |
|--------|------------------|--------------|
| **Self-contained (mặc định)** | `mock-vllm` + `mock-embed` chạy local trong Docker | Chấm/demo không cần GPU, chạy được ngay, mọi test PASS |
| **Production (Kaggle GPU)** | vLLM + sentence-transformers trên Kaggle T4, expose qua ngrok | Có tài khoản Kaggle GPU + ngrok |

Chuyển sang chế độ Kaggle: điền `VLLM_NGROK_URL` / `EMBED_NGROK_URL` trong `.env` (contract OpenAI-compatible **giống hệt** nên không phải sửa code). Xem `kaggle/lab28_kaggle_gpu.ipynb`.
Notebook Kaggle ưu tiên đọc secret `NGROK_AUTHTOKEN` từ **Kaggle Secrets**; không hard-code token vào notebook.

---

## Kiến trúc

```
┌────────────────────────── LOCAL (Docker Compose) ──────────────────────────┐
│  Kafka ─► Prefect ─► Delta Lake ─► Feast (Redis)                            │
│    │                                                                        │
│    └─► (embed) ─► Qdrant ◄─────────────┐                                    │
│                                        │                                    │
│  Prometheus ◄─ scrape ─ API Gateway ───┘   Grafana ◄─ Prometheus            │
│                    │                                                        │
│                    ▼  (VLLM_URL / EMBED_URL)                                │
│           mock-vllm : mock-embed   ── hoặc ──►  Kaggle GPU (ngrok)          │
└─────────────────────────────────────────────────────────────────────────────┘
```

---

## Yêu cầu

- Docker Desktop đang chạy
- Python 3.10+ (đã test trên 3.12)
- (Tùy chọn) Kaggle GPU + ngrok cho chế độ production

---

## Quick Start (chế độ self-contained — khuyến nghị)

```powershell
# 1. Cấu hình env (để trống 2 URL Kaggle => tự dùng mock local)
copy .env.example .env

# 2. Cài dependencies host (LƯU Ý: kafka-python-ng cho Python 3.12)
pip install -r requirements.txt

# 3. Build + khởi động toàn bộ stack
docker compose up -d --build
docker compose ps          # tất cả services Up/healthy

# 4. Chạy toàn bộ data pipeline (Integration 1->5)
python scripts/run_all_pipeline.py

# 5. (Tùy chọn) Deploy Prefect flow có schedule
python prefect/flows/kafka_to_delta.py deploy

# 6. Smoke tests — kỳ vọng 8/8 test case PASS (5 journeys)
pytest smoke-tests/ -v

# 7. Production readiness — kỳ vọng >80%
python scripts/production_readiness_check.py

# 8. Sinh traffic cho Grafana có biểu đồ
python scripts/load_test.py 40
```

Trên Windows có thể dùng helper: `.\run.ps1 all`

**Truy cập UI:**
- API Gateway docs: http://localhost:8000/docs
- Prefect UI: http://localhost:4200
- Grafana: http://localhost:3000 (admin/admin — dashboard "AI Platform — Lab28 Overview" tự load)
- Qdrant: http://localhost:6333/dashboard
- Prometheus: http://localhost:9090

---

## 10 Integration Points

| # | Luồng | File |
|---|-------|------|
| 1 | Data → Kafka | `scripts/01_ingest_to_kafka.py` |
| 2 | Kafka → Prefect → Delta Lake | `scripts/02_consume_to_delta.py`, `prefect/flows/kafka_to_delta.py` |
| 3+4 | Delta Lake → Feast (Redis) | `scripts/03_delta_to_feast.py` |
| 5 | Data → Embedding → Qdrant | `scripts/05_embed_to_qdrant.py` |
| 6+7 | MLflow → Model Registry → vLLM | `kaggle/lab28_kaggle_gpu.ipynb` (Cell 6) |
| 8 | Serving → API Gateway | `api-gateway/main.py` |
| 9 | Prometheus/Grafana metrics | `monitoring/`, `/metrics` |
| 10 | LangSmith tracing | `api-gateway/main.py`, `scripts/09_verify_observability.py` |

---

## API Gateway

```bash
# Health
curl http://localhost:8000/health
# Deep health (kiểm tra dependencies)
curl http://localhost:8000/health/deep
# Chat (embedding tùy chọn — thiếu thì gateway tự embed)
curl -X POST http://localhost:8000/api/v1/chat \
  -H "Content-Type: application/json" \
  -d '{"query": "Explain event-driven architecture for AI platforms"}'
```

Tính năng: **circuit breaker** cho vLLM, **graceful degradation** (Qdrant/embed/vLLM lỗi → fallback không 500), validation → **422**, **custom Prometheus metrics**, `/admin` → **403**.

---

## Cấu trúc thư mục

```
Day28-Lab-Assignment/
├── docker-compose.yml          # 12 services (có mock GPU + healthcheck)
├── .env / .env.example
├── requirements.txt            # host deps
├── Makefile / run.ps1          # helper
├── api-gateway/                # FastAPI gateway (circuit breaker, fallback)
├── mock-gpu/                   # mock vLLM + mock embed (thay Kaggle)
├── prefect/flows/              # Kafka → Delta flow
├── scripts/                    # 10 integration + orchestrator + load test
├── monitoring/                 # prometheus.yml + grafana provisioning + dashboard
├── smoke-tests/                # 8 e2e test cases / 5 journeys
├── kaggle/                     # notebook GPU tier (vLLM/embed/MLflow)
├── screenshots/                # ảnh demo
└── BAO_CAO.md                  # báo cáo tiếng Việt + trả lời 5 câu hỏi
```

---

## Troubleshooting

- **Services không start:** `docker compose logs <service>` → `docker compose down -v && docker compose up -d --build`
- **kafka lỗi trên Python 3.12:** dùng `kafka-python-ng` (đã ghi trong requirements), không dùng `kafka-python` gốc.
- **Qdrant collection trống:** chạy `python scripts/05_embed_to_qdrant.py` (hoặc `run_all_pipeline.py`).

## Nộp bài

Xem `BAO_CAO.md` (báo cáo + trả lời 5 câu hỏi) và `SUBMISSION.md`.
