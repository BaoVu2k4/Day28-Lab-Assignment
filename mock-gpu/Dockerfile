FROM python:3.10-slim

WORKDIR /app

RUN pip install --no-cache-dir --retries 5 --timeout 120 \
    fastapi==0.115.6 \
    uvicorn==0.34.0 \
    pydantic==2.9.2 \
    prometheus-fastapi-instrumentator==7.0.0

COPY vllm_server.py embed_server.py ./

# APP_MODULE được set trong docker-compose để chọn server nào chạy
#   - vllm_server:app   (port 8001)
#   - embed_server:app  (port 8002)
ENV APP_MODULE=vllm_server:app
ENV APP_PORT=8001

CMD ["sh", "-c", "uvicorn ${APP_MODULE} --host 0.0.0.0 --port ${APP_PORT}"]
