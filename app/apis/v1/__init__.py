from fastapi import APIRouter

from app.apis.v1.acc_routers import acc_router
from app.apis.v1.car_routers import car_router
from app.apis.v1.com_routers import com_router
from app.apis.v1.mat_routers import mat_router
from app.apis.v1.pnt_routers import pnt_router
from app.apis.v1.sch_routers import sch_router
from app.apis.v1.trs_routers import trs_router
from auth_kit.router import auth_router

# 각 도메인 라우터는 여기에 include_router로 등록한다.
v1_routers = APIRouter(prefix="/api/v1")
v1_routers.include_router(auth_router)
v1_routers.include_router(acc_router)
v1_routers.include_router(sch_router)
v1_routers.include_router(mat_router)
v1_routers.include_router(car_router)
v1_routers.include_router(trs_router)
v1_routers.include_router(pnt_router)
v1_routers.include_router(com_router)
