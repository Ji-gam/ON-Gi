from fastapi import FastAPI

from ai_worker.core.logger import setup_logger
from ai_worker.routers import api_router

logger = setup_logger("ai_worker.main")

app = FastAPI(
    title="ON-Gi AI Worker Service",
    description="RAG 파이프라인 및 백그라운드 워커 API 템플릿",
    version="0.1.0",
)

app.include_router(api_router)
