# Task Contract T-CAR-2 (체크인/체크아웃/돌봄 일지)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `car_*`)
- 관련 REQ: REQ-F-CAR-03(GPS 체크인), REQ-F-CAR-05(체크아웃 및 시간 확정), REQ-F-CAR-06(돌봄
  일지, 알레르기 항목 필수)
- 제외(범위 밖, 우선순위 문서 권고): REQ-F-CAR-04(안심 사진 전송) — 스토리지 자동삭제 정책 필요,
  후속 Task로 분리
- 선행: T-CAR-1(`care_sessions`, CONFIRMED 상태 전이) — dev 머지 완료(PR #11)

### 목표 (요구사항정의서 원문)
- REQ-F-CAR-03: "돌봄 시작 시 제공자가 체크인하며, 단말 GPS로 약속 장소 반경 내 여부를 확인해
  기록한다." 성공요건: "반경 밖 체크인 시 경고가 노출되고 사유 입력이 요구된다."
- REQ-F-CAR-05: "체크아웃 시각을 기준으로 실제 돌봄 시간을 확정하고 포인트 정산의 근거로
  사용한다." 성공요건: "체크인·체크아웃 차이만큼 포인트가 이동한다." (포인트 이동 자체는 PNT
  도메인 범위 — 이 Task는 "정산 근거"인 실제 분(minute) 확정까지)
- REQ-F-CAR-06: "식사·수면·기분·특이사항을 기록하고 요청자가 열람한다. 알레르기 관련 항목은
  기록 필수로 강제한다." 성공요건: "알레르기 등록 아동은 일지에서 해당 항목 미입력 시 저장이
  거부된다."

### 완료 정의
- [x] `care_sessions`에 `child_id`(대상 아동, FK `children.id`)·`meeting_h3`(약속 장소, T-ACC-2
      `residence_h3`와 동일 저장 방식) 컬럼 추가(REQ-F-CAR-01에서 T-CAR-1이 유보했던 필드,
      이번 Task의 체크인 반경 판정에 필요해 이번에 채움) — Alembic 마이그레이션(`care_sessions`
      ALTER)
- [x] 체크인: 제공자가 GPS 위경도를 보내면 `meeting_h3` 중심좌표와의 haversine 거리를 계산.
      반경 이내면 즉시 체크인 기록, 반경 밖인데 사유 미입력이면 400, 사유 입력 시 기록(경고
      노출은 프론트 책임, 백엔드는 `out_of_range` 플래그+사유를 응답/저장). 원본 GPS 좌표는
      저장하지 않고 계산된 거리(m)만 저장(REQ-NF-SEC-05 원칙 준용)
- [x] 체크아웃: 체크인 이후에만 가능(체크인 없이 시도 시 409). 체크아웃 시각과 체크인 시각의
      차이를 분 단위로 계산해 저장(포인트 정산 근거, 실제 정산은 T-PNT-1 범위 — 훅 주석만)
- [x] 체크인/체크아웃은 세션의 provider 본인만 가능, 세션이 CONFIRMED가 아니면 409
- [x] 돌봄 일지: 세션당 1건(upsert), 식사/수면/기분/특이사항 + 알레르기 항목. 대상 아동에
      `ChildSensitiveInfo.allergies`가 있는데 알레르기 항목이 비어있으면 400으로 저장 거부.
      작성은 provider만, 조회는 requester/provider 둘 다 가능
- [x] (공통) 새 컬럼/테이블은 Alembic 마이그레이션(`b7e4d1a08c53_care_checkin_journal.py`) +
      `docs/dev/ERD.dbml` v1.5 동기화
- [x] (공통) 테스트를 TDD로 먼저 작성(`app/tests/car_apis/**`: 반경 이내 체크인 성공, 반경 밖
      사유 없으면 400/사유 있으면 성공, 체크인 없이 체크아웃 409, 체크아웃 분 계산, 알레르기
      아동 일지 항목 누락 시 400/입력 시 성공), `uv run pytest -v` 통과(32 passed)
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

---

### 허용 경로
```
app/models/care_session.py       (child_id/meeting_h3 컬럼 추가)
app/models/care_log.py           (신규)
app/repositories/care_session_repository.py
app/repositories/care_log_repository.py  (신규)
app/services/care_session_service.py    (체크인/체크아웃 메서드 추가)
app/services/care_log_service.py         (신규)
app/dtos/care_session_dto.py
app/dtos/care_log_dto.py         (신규)
app/apis/v1/car_routers.py
app/core/db/migrations/versions/**  (신규 리비전 파일만 추가)
app/tests/car_apis/**
docs/dev/ERD.dbml
docs/tasks/T-CAR-2.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/models/children.py`, `app/models/guardian_profile.py` 등 CAR 외 도메인 모델
  (읽기 전용 재사용만)

### 의존하는 공유 계약 (읽기만)
- `app/repositories/child_repository.py` (`ChildRepository.get`) — 대상 아동 소유권·알레르기
  확인용
- `app/dependencies` — `get_current_user`

### 자율 판단 / 가정
- 체크인 반경은 요구사항정의서에 수치 명시가 없어 200m로 가정(향후 설정값화 후속 Task)
- `meeting_h3`는 요청 생성 시 요청자가 입력(H3 해상도 9, `guardian_profile.residence_h3`와
  동일 규칙) — 제공자/요청자 중 누구 집 기준인지는 명시가 없어 "약속 장소"를 별도 값으로 받음
- 안심 사진(REQ-F-CAR-04)은 범위 밖(위 참고)
- 알림 발송(양측 알림)은 NTFY 도메인 미구현으로 범위 밖(T-CAR-1과 동일 가정)

### 반드시 멈춰야 하는 경우
- 포인트 복식부기 원장(PNT) 실제 정산 로직이 필요해 보이는 경우 (T-PNT-1 범위, 훅 주석만 남기고 멈춤)

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고. 체크인 반경(200m)은 임의 가정값. 일지 작성은
  세션이 CONFIRMED 상태여야만 가능(체크인/체크아웃 여부와는 무관 — REQ에 시점 제약이 없어
  최소 제약으로 둠).
- 공유 계약 변경 필요 사항 (있다면): 없음(`child_repository`는 읽기만, T-MAT-1과 동일 재사용 패턴)
- 브랜치명: `feature/T-CAR-2-checkin-checkout-journal`
