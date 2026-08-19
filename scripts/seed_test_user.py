"""로컬 개발용 테스트 계정 시딩.

실행 중인 FastAPI 서버(기본 http://localhost:8000)에 실제 회원가입 API를 호출해
test@example.com 계정을 만든다. 이미 가입되어 있으면(409) 조용히 넘어간다.

사용법:
    uv run python scripts/seed_test_user.py
"""

import sys

import httpx

BASE_URL = "http://localhost:8000"

TEST_USER = {
    "email": "test@example.com",
    "password": "Qwer1234!!",
    "name": "테스트유저",
    "nickname": "시딩테스트",
    "birth_date": "1995-01-01",
    "gender": "M",
    "phone_number": "010-9999-9999",
}


def main() -> None:
    with httpx.Client(base_url=BASE_URL, timeout=10) as client:
        terms = client.get("/api/v1/auth/terms").raise_for_status().json()["terms"]
        agreements = [
            {"terms_type": t["terms_type"], "version": t["version"], "agreed": t["is_required"]} for t in terms
        ]

        response = client.post(
            "/api/v1/auth/signup",
            json={**TEST_USER, "agreements": agreements},
        )

        if response.status_code == 409:
            print(f"이미 존재하는 계정입니다: {TEST_USER['email']}")
            return

        response.raise_for_status()
        user = response.json()["user"]
        print(f"테스트 계정 생성 완료: email={TEST_USER['email']} password={TEST_USER['password']} id={user['id']}")


if __name__ == "__main__":
    try:
        main()
    except httpx.ConnectError:
        print(f"{BASE_URL}에 연결할 수 없습니다. 백엔드 서버를 먼저 실행하세요.", file=sys.stderr)
        sys.exit(1)
