# Phiên bản chạy trên Kaggle GPU

Thư mục này cung cấp **2 cách chạy trên Kaggle**. Cả hai đều cần bật **GPU T4 x2**
(Settings → Accelerator → GPU T4 x2) trước khi Run All.

| Notebook | Mục đích | Cần gì thêm |
|----------|----------|-------------|
| **`lab28_kaggle_allinone.ipynb`** ⭐ | Chạy **toàn bộ mini-platform ngay trên Kaggle** (vLLM + embedding + Qdrant in-memory + RAG Gateway + MLflow + smoke test). Không cần Docker/local. | Không (ngrok chỉ tùy chọn ở Cell 8) |
| `lab28_kaggle_gpu.ipynb` | Chỉ chạy **tầng GPU** (vLLM + embedding + MLflow) rồi **expose qua ngrok** để stack local (Docker) gọi vào — đúng mô hình hybrid trong đề. | ngrok token |

> 2 file `build_*.py` chỉ là script sinh ra notebook; nộp/chạy dùng file `.ipynb`.

## Secret ngrok

Trong Kaggle, vào **Add-ons → Secrets** và tạo secret tên `NGROK_AUTHTOKEN`.
Notebook sẽ tự đọc secret này; nếu chưa có, cell ngrok sẽ hỏi nhập token thủ công.

---

## Cách 1 — All-in-One (khuyến nghị để demo nhanh "chạy bằng Kaggle")

1. Upload `lab28_kaggle_allinone.ipynb` lên Kaggle, bật GPU T4 x2.
2. Run All. Notebook sẽ:
   - Cell 2: khởi động vLLM trên GPU (chờ ~1–3 phút load model).
   - Cell 3–4: nạp embedding + Qdrant in-memory + ingest 5 doc.
   - Cell 5: dựng RAG API Gateway (FastAPI) trong notebook (port 8000).
   - Cell 6: log MLflow (Integration 6+7).
   - Cell 7: **smoke test end-to-end** — RAG thật trên GPU, in ra `SMOKE TEST PASSED`.
3. (Tùy chọn) Cell 8: điền ngrok token để lấy public URL cho người chấm gọi vào.

## Cách 2 — Hybrid (Kaggle GPU + Docker local)

1. Chạy `lab28_kaggle_gpu.ipynb` trên Kaggle → copy `VLLM_NGROK_URL` và `EMBED_NGROK_URL` in ra.
2. Ở máy local, dán 2 URL vào `.env`:
   ```
   VLLM_NGROK_URL=https://xxxx.ngrok-free.app
   EMBED_NGROK_URL=https://yyyy.ngrok-free.app
   ```
3. `docker compose up -d` (tắt/không cần mock GPU nữa) — API Gateway tự gọi GPU Kaggle
   thay vì mock, **không phải sửa code** (nhờ thiết kế `VLLM_URL=${VLLM_NGROK_URL:-http://mock-vllm:8001}`).

---

## Vì sao có 2 bản?

- Bản **local (Docker)** thể hiện đầy đủ kiến trúc hybrid có Kafka/Prefect/Grafana — nhưng
  các thành phần này khó dựng trên Kaggle (Kaggle không có Docker).
- Bản **Kaggle all-in-one** chứng minh đúng phần *chạy được trên Kaggle GPU*: RAG serving
  end-to-end (embed → vector search → LLM) trên chính GPU, đúng tinh thần "phiên bản chạy bằng Kaggle".
