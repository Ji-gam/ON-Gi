# Task Contract T-PNT-1 (포인트 복식부기 원장 + 돌봄 정산)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `pnt_*`)
- 관련 REQ: REQ-F-PNT-01(복식부기 원장), REQ-F-PNT-02(돌봄 정산), REQ-F-PNT-03(잔액·내역
  조회), REQ-F-PNT-04(시드 포인트 및 한도)
- 선행: T-CAR-2(`care_sessions.actual_minutes` — 정산 근거)
- 후속 연동: `care_session_service.checkout()`의
  `# TODO(T-CAR-2→T-PNT-1): actual_minutes를 포인트 정산 근거로 연결` 훅 해소

### 목표 (요구사항정의서 원문)
- REQ-F-PNT-01: "모든 포인트 이동을 차변·대변 한 쌍으로 기록하며, 거래별 합계가 항상 0임을
  저장 시점에 검증한다." 검증 기준: "임의 거래 100건 생성 후 전체 합이 0이다."
- REQ-F-PNT-02: "돌봄 완료 시 제공자에게 적립, 요청자에게 차감을 동시에 기록한다. 정산 단위는
  30분이다." 검증 기준: "2시간 돌봄 완료 시 양측 잔액이 ±4슬롯만큼 변동한다."
- REQ-F-PNT-03: "현재 잔액과 거래 내역(일시, 상대, 사유, 증감)을 조회한다." 검증 기준: "정산
  직후 내역 목록 최상단에 해당 거래가 표시된다."
- REQ-F-PNT-04: "신규 가입 시 시드 포인트를 지급하고, 마이너스 잔액 한도를 초과하면 신규 요청
  생성을 제한한다." 검증 기준: "한도 초과 계정이 요청 생성 시 안내와 함께 차단된다."
  (REQ-F-PNT-05/06은 우선순위 문서상 범위 밖 — 홀드/노쇼 페널티/구독은 별도 Task)

### 완료 정의
- [x] `app/models/point_account.py`: `PointAccount`(user_id PK, balance) — 최초 조회 시
      시드 포인트로 지연 생성(트러스트 가중치/설정과 동일 패턴)
- [x] `app/models/point_ledger.py`: `PointTransaction`(reason, reference_type/id, 시각) +
      `PointEntry`(transaction_id, user_id, amount 부호 있음). 거래는 항상 정확히 2개의
      entry(+amount/-amount)로 구성되어 합계 0을 구조적으로 보장(REQ-F-PNT-01)
- [x] 돌봄 정산(REQ-F-PNT-02): `checkout()`에서 `actual_minutes // 30`(슬롯 수)만큼 요청자
      차감·제공자 적립을 한 거래로 기록. 0슬롯(30분 미만)이면 거래 생성 안 함
- [x] 잔액·내역 조회(REQ-F-PNT-03): 잔액 API, 상대·사유·증감·시각 포함한 내역 API(최신순)
- [x] 시드 포인트·한도(REQ-F-PNT-04): 계정 최초 생성 시 시드 지급, 잔액이 한도 이하이면
      `create_request` 차단(400)
- [x] (공통) 새 테이블은 Alembic 마이그레이션 + `docs/dev/ERD.dbml` v1.8 동기화
- [x] (공통) 테스트를 TDD로 먼저 작성(`app/tests/pnt_apis/**`: 거래 100건 합계 0, 2시간
      돌봄 완료 시 ±4슬롯, 30분 미만 정산 시 거래 미생성, 신규 계정 시드 지급, 한도 초과
      시 요청 생성 차단, 내역 최신순 조회), `uv run pytest -v` 통과(회귀 없음)
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

---

### 허용 경로
```
app/models/point_account.py         (신규)
app/models/point_ledger.py          (신규)
app/repositories/point_account_repository.py   (신규)
app/repositories/point_ledger_repository.py     (신규)
app/services/point_ledger_service.py   (신규)
app/services/care_session_service.py   (정산 훅 + 한도 게이트 추가)
app/dtos/point_dto.py               (신규)
app/apis/v1/pnt_routers.py          (신규)
app/apis/v1/__init__.py
app/core/db/migrations/versions/**  (신규 리비전 파일만 추가)
app/tests/pnt_apis/**                (신규)
app/tests/car_apis/**                 (한도 게이트 회귀 확인)
docs/dev/ERD.dbml
docs/tasks/T-PNT-1.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**` (시드 포인트는 회원가입 훅이 아니라 계정 최초 조회 시
  지연 생성으로 구현 — 아래 "자율 판단" §1)
- `app/models/care_session.py` (읽기 전용 재사용만)

### 의존하는 공유 계약 (읽기만)
- `app/repositories/care_session_repository.py` — 정산 대상 세션 조회
- `app/dependencies` — `get_current_user`

### 자율 판단 / 가정
1. **시드 포인트 지급 시점**: `auth_kit`은 금지 경로라 회원가입 훅에 직접 개입할 수 없다.
   T-TRS-1의 `TrustWeights`/T-TRS-2의 `TrustSettings`와 동일하게, 계정을 최초 조회하는
   시점(`get_or_create`)에 시드 포인트로 지연 생성한다. 사용자 입장에서는 가입 즉시 첫
   조회에서 시드가 잡혀 있으므로 요구사항의 "신규 가입 시 지급"과 동등하다.
2. **시드 포인트·한도 수치**: 요구사항정의서에 구체적 수치가 없어 30분=1슬롯 기준으로
   SEED_POINTS=12(6시간 상당), NEGATIVE_BALANCE_LIMIT=-12(시드와 동일한 한도까지 마이너스
   허용, 이후 차단)로 가정한다.
3. **정산 단위 절사**: `actual_minutes // 30`(내림)으로 슬롯 수를 계산한다. 30분 미만
   자투리는 이번 Task에서 별도 처리하지 않는다(원문에 절사/올림 명시 없음).
4. **한도 게이트 적용 시점**: "신규 요청 생성을 제한"이 명시적이라 `create_request`에서
   요청자(향후 차감될 쪽)의 현재 잔액만 검사한다. 제공자 측에는 적용하지 않는다.
5. **거래 무결성 보장 방식**: DB 제약이 아니라 서비스 계층에서 항상 대칭된 두 entry
   (+amount/-amount)만 생성하도록 강제해 합계 0을 구조적으로 보장한다(원장에 임의
   entry를 추가하는 경로를 두지 않음).

### 반드시 멈춰야 하는 경우
- 포인트 홀드/노쇼 페널티(REQ-F-PNT-05)나 구독 상태 관리(REQ-F-PNT-06)가 필요해 보이는 경우
  (범위 밖, 별도 Task)

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고), `uv run pytest -v` 55
  passed(회귀 없음), `ruff check`/`ruff format --check`/`uv run mypy .` 모두 통과
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항: `app/services/care_session_service.py`(T-CAR-1/2 소유)의
  `create_request`/`checkout`에 포인트 훅 추가 — 단일 백엔드 담당자 체제(SQUAD_MAP v3.0)라
  별도 조율 불필요, 기록으로만 남김
- 브랜치명: `feature/T-PNT-1-point-ledger`
