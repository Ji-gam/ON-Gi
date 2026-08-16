# Task Contract T-ADM-1 (가설 검증 이벤트 로그 적재)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `adm_*`)
- 관련 REQ: REQ-F-ADM-04(가설 검증 이벤트 로그)
- 근거: `docs/decision_log/` 부재 시 `NEXT_PLAN_v1.md` §2-4 — "알림(COM-02)과 이벤트 로그
  (ADM-04)를 가장 먼저 세운다. 둘 다 다른 도메인의 완료 조건이자 횡단 관심사여서, 늦게
  넣을수록 이미 만든 서비스들을 다시 열어야 한다."
- 선행: 없음(W1 최초 착수 항목)

### 목표 (요구사항정의서 원문 취지)
- REQ-F-ADM-04: 상보 후보 보유율·L2→L3 전이율·재매칭률 등 가설 검증에 필요한 사용자 행동을
  시점별로 적재한다. 이 Task는 스키마 설계 + 7종 이벤트의 적재 훅만 범위. 집계/대시보드 API는
  T-ADM-3 범위.
- 7종 이벤트: 후보 노출(CANDIDATE_EXPOSURE) · 요청(REQUEST_CREATED) · 수락(REQUEST_ACCEPTED) ·
  거절(REQUEST_REJECTED) · 신뢰등급 전이(TRUST_LEVEL_TRANSITION) · 세션 완료(SESSION_COMPLETED) ·
  재요청(REMATCH_REQUESTED)

### 완료 정의
- [x] `hypothesis_events` 테이블 신설: `event_type`(7종 enum), `actor_user_id`(FK users, 행위자),
      `target_user_id`(FK users, nullable — 상대방), `payload`(JSON, 이벤트별 부가 데이터),
      `created_at`
- [x] `HypothesisEventService.log(...)`는 커밋하지 않는다 — 호출자(각 도메인 서비스)의 기존
      트랜잭션 커밋에 함께 실려야 한다(추가 라운드트립 없이 훅을 얹기 위함)
- [x] `MatchingService.find_candidates`: 정렬된 후보 목록이 확정된 시점에 후보별
      CANDIDATE_EXPOSURE 1건씩 적재(payload: total_score 등 점수 스냅샷). 이 메서드는 원래
      읽기 전용(커밋 없음)이었으므로 이벤트 적재를 위해 메서드 끝에 커밋 1회 추가
- [x] `CareSessionService.create_request`: REQUEST_CREATED 적재. 단, 같은 두 사용자 사이에
      과거 `checkout_at`이 있는(완료된) 세션이 이미 존재하면 REQUEST_CREATED 대신
      REMATCH_REQUESTED로 적재(REQ-F-MAT-09 재요청 개념 — 전용 재매칭 엔드포인트는 미구현이라
      일반 요청 생성 경로에 얹음)
- [x] `CareSessionService.accept` → REQUEST_ACCEPTED, `reject` → REQUEST_REJECTED,
      `checkout` → SESSION_COMPLETED(payload: actual_minutes) 적재
- [x] `TrustLevelService`: `grant_l1`(최초 L1 성립) · `schedule_joint_session`의 L1→L2 전이 ·
      `confirm_joint_session`의 L2→L3 전이 · `demote`의 강등 — 4개 지점 모두
      TRUST_LEVEL_TRANSITION 적재(payload: previous_level/new_level)
- [x] (공통) Alembic 마이그레이션(`f5a1c3e7b902_hypothesis_event.py`) + `docs/dev/ERD.dbml`
      동기화
- [x] (공통) TDD: `app/tests/adm_apis/test_hypothesis_event_hooks.py` — 각 훅 지점에서 올바른
      `event_type`/`actor_user_id`/`target_user_id`가 남는지 검증, `uv run pytest -v` 통과
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run mypy .` 통과

---

### 허용 경로
```
app/models/hypothesis_event.py            (신규)
app/repositories/hypothesis_event_repository.py  (신규)
app/services/hypothesis_event_service.py  (신규)
app/services/matching_service.py          (훅 추가만, 기존 로직 변경 없음)
app/services/care_session_service.py      (훅 추가만)
app/services/trust_level_service.py       (훅 추가만)
app/repositories/care_session_repository.py  (재요청 판정용 조회 메서드 1개 추가)
app/core/db/migrations/versions/**        (신규 리비전 파일만 추가)
app/tests/adm_apis/**                     (신규)
docs/dev/ERD.dbml
docs/tasks/T-ADM-1.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- MAT/CAR/TRS의 기존 판정 로직(하드필터, 상태 전이 조건, 포인트 정산) 자체 — 오직 이벤트
  적재 호출만 추가, 반환값/부수효과는 바꾸지 않는다

### 의존하는 공유 계약 (읽기만)
- `app/dependencies` — `get_current_user`(직접 사용 없음, 각 라우터가 이미 사용 중)
- 각 도메인 서비스의 기존 트랜잭션 경계(`session.commit()` 위치) — 이 Task는 그 경계 안에
  `event_service.log(...)`(커밋 없음)만 끼워 넣는다

### 자율 판단 / 가정
- payload 스키마는 요구사항정의서에 수치 명시가 없어 이벤트별 최소 스냅샷만 담음(추후
  T-ADM-3에서 집계 쿼리가 요구하는 필드가 늘어나면 그때 확장)
- 재요청/재매칭 판정 기준은 "과거 체크아웃 완료 세션 존재 여부"로 가정(전용 단골/재매칭
  테이블은 MAT-09 범위, 아직 미구현)
- CANDIDATE_EXPOSURE는 후보 1건당 1행(다건 적재) — 목록 전체를 하나의 이벤트로 뭉치면
  "상보 후보 보유율"(개별 후보 존재 여부) 집계가 불가능해지므로 개별 적재로 결정
- `grant_l1`은 `TrustLevelHistory`에는 기록되지 않는 최초 성립이지만, 가설 검증 관점에서는
  "L 전이"의 시작점이라 TRUST_LEVEL_TRANSITION(previous=None, new=L1)으로 함께 적재

### 반드시 멈춰야 하는 경우
- 집계/대시보드 API(ADM-02) 요구가 이 Task 범위로 새어 들어오는 경우 — T-ADM-3로 분리하고 멈춤
- payload에 아동 민감정보(알레르기 등)를 직접 담아야 할 것 같은 경우 — 사용자/세션 ID·점수
  스냅샷 이외의 개인정보는 담지 않고 멈춰서 보고

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고)
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항 (있다면): 없음(기존 서비스의 반환값/커밋 시점은 그대로, 로그 호출만
  추가)
- 브랜치명: `feature/T-ADM-1-hypothesis-event-log`
