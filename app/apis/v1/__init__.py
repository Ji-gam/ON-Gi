from fastapi import APIRouter

# 각 도메인 라우터는 여기에 include_router로 등록한다.
# 예) from app.apis.v1.auth_routers import auth_router
#     v1_routers.include_router(auth_router)
v1_routers = APIRouter(prefix="/api/v1")
