# run.ps1 — Helper cho Windows PowerShell. Dùng: .\run.ps1 <lệnh>
param([Parameter(Position = 0)][string]$cmd = "help")

switch ($cmd) {
    "up"        { docker compose up -d --build }
    "down"      { docker compose down }
    "clean"     { docker compose down -v }
    "ps"        { docker compose ps }
    "logs"      { docker compose logs -f api-gateway }
    "pipeline"  { python scripts/run_all_pipeline.py }
    "deploy"    { python prefect/flows/kafka_to_delta.py deploy }
    "test"      { pytest smoke-tests/ -v }
    "readiness" { python scripts/production_readiness_check.py }
    "load"      { python scripts/load_test.py 40 }
    "all" {
        docker compose up -d --build
        Write-Host "Chờ services khởi động (60s)..." -ForegroundColor Cyan
        Start-Sleep -Seconds 60
        python scripts/run_all_pipeline.py
        pytest smoke-tests/ -v
        python scripts/production_readiness_check.py
    }
    default {
        Write-Host "Các lệnh: up | down | clean | ps | logs | pipeline | deploy | test | readiness | load | all"
    }
}
