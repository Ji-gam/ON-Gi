# 도메인 모델을 여기에 임포트해 Base.metadata에 등록한다(Alembic autogenerate 대상).
# 예) from app.models.users import User
from app.models.base import Base

__all__ = ["Base"]
