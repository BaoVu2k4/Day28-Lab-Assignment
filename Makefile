# Makefile — Lab #28 (dùng với `make <target>`; trên Windows dùng run.ps1)
.PHONY: up down logs ps pipeline test readiness load clean deploy-flow

up:                 ## Build + start toàn bộ stack
	docker compose up -d --build

down:               ## Dừng stack
	docker compose down

clean:              ## Dừng + xoá volume
	docker compose down -v

ps:                 ## Trạng thái container
	docker compose ps

logs:               ## Xem log api-gateway
	docker compose logs -f api-gateway

pipeline:           ## Chạy toàn bộ data pipeline (01->02->03->05)
	python scripts/run_all_pipeline.py

deploy-flow:        ## Deploy Prefect flow (schedule 5')
	python prefect/flows/kafka_to_delta.py deploy

test:               ## Chạy smoke tests (8 test cases / 5 journeys)
	pytest smoke-tests/ -v

readiness:          ## Production readiness score
	python scripts/production_readiness_check.py

load:               ## Sinh traffic cho Grafana
	python scripts/load_test.py 40
