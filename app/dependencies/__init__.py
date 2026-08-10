"""로그인 사용자 인증 의존성. 도메인 라우터는 여기서 가져다 쓴다.

CODING_RULES.md §2-1: JWT payload는 user_id만 담는다. 아동(Child) 데이터를 다루는 엔드포인트는
`Depends(get_current_user)`로 User를 받고, 그 User가 소유한 Child인지 서비스 계층에서 확인한다.
"""

from auth_kit.router import get_current_user  # noqa: F401
