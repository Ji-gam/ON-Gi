from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers

app = FastAPI(
    title="ON-Gi API",
    summary="ON-Gi 백엔드 API",
    description=(
        "레이어 우선 구조(Router → Service → Repository)의 FastAPI 백엔드 템플릿입니다. "
        "구조/규칙은 `docs/CODING_RULES.md`, 기여 방법은 `docs/CONTRIBUTING.md`를 참고하세요."
    ),
    version="0.1.0",
    default_response_class=ORJSONResponse,
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json",
)

app.include_router(v1_routers)


@app.get("/health", tags=["health"], summary="헬스체크")
async def health() -> dict[str, str]:
    return {"status": "ok"}
