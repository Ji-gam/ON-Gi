from fastapi import FastAPI
from fastapi.responses import ORJSONResponse

from app.apis.v1 import v1_routers
from app.core.db.databases import get_db
from auth_kit.router import get_session

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
app.dependency_overrides[get_session] = get_db
# TODO(T-ACC-1): 프로젝트 메일러/SMS 게이트웨이 연결 전까지는 인증 메일 링크·본인확인 코드가
# 로그로만 찍힌다.
# from auth_kit import router as auth_router_mod
# auth_router_mod.send_email = my_send_mail
# auth_router_mod.send_sms = my_send_sms


@app.get("/health", tags=["health"], summary="헬스체크")
async def health() -> dict[str, str]:
    return {"status": "ok"}
