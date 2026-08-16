# Task Contract T-PNT-2 (포인트 예치·노쇼 페널티 + 취소/노쇼 세션 처리)

### 참조
- 담당: 백엔드(`docs/SQUAD_MAP.md` §2, 접두어 `pnt_*`/`car_*`)
- 관련 REQ: REQ-F-PNT-05(포인트 예치 및 노쇼 페널티), REQ-F-CAR-07(취소·노쇼 처리)
- 선행: T-PNT-1(복식부기 원장), T-CAR-2(체크인/체크아웃)
- 후속 연동: `docs/tasks/T-PNT-1.md` "반드시 멈춰야 하는 경우"에 명시된 홀드/노쇼 범위 밖 항목,
  `trust_score_service.py`의 `# TODO(...후속 노쇼 Task)` 훅 해소
- 근거: `NEXT_PLAN_v1.md` §4 T-PNT-2, §2-4(알림·이벤트 로그 다음으로 횡단 관심사 선행 원칙)

### 목표 (요구사항정의서 원문)
- REQ-F-PNT-05: "요청 확정 시 예상 돌봄 시간만큼 요청자 포인트를 홀드하고, 완료 시 정산으로
  전환한다. 취소 마감 시각 이후 취소나 노쇼가 발생하면 홀드분의 일부를 상대에게 이전하고
  사유를 원장에 기록한다. 현금 보증금·PG 연동은 P1로 이월한다." 검증 기준: "노쇼 처리 시
  홀드된 포인트가 상대에게 이전되고 원장의 차변·대변 합이 0으로 유지된다."
- REQ-F-CAR-07: "세션 취소 사유와 시점을 기록하고, 무단 불참(노쇼)은 신뢰 점수에 반영한다."
  검증 기준: "노쇼 처리 시 이력이 남고 신뢰 점수가 감점된다."

### 완료 정의
- [x] `app/models/point_account.py`: `held_balance` 컬럼 추가(홀드 중인 포인트, `balance`와 분리)
- [x] `app/models/point_hold.py`(신규): `PointHold`(세션당 1건, HELD/SETTLED/RELEASED/FORFEITED)
- [x] `app/models/care_session.py`: `CareSessionStatus`에 `CANCELLED`/`NO_SHOW` 추가,
      `cancelled_at`/`cancel_reason`/`at_fault_user_id` 컬럼 추가
- [x] 홀드 생성(REQ-F-PNT-05): `accept()` 시 `end_slot - start_slot` 슬롯만큼 요청자 계정에서
      `balance`→`held_balance`로 예약(상대에게는 아직 이전되지 않으므로 원장 거래 없음)
- [x] 홀드 정산: `checkout()` 시 실제 슬롯만큼만 정산(원장 거래 생성), 미사용 홀드분은 요청자에게
      반환. 실제 슬롯이 홀드보다 많아도 홀드 한도로 clamp
- [x] 취소(REQ-F-CAR-07): 요청자·제공자 모두 체크인 전까지 취소 가능. 취소 마감
      (`CANCELLATION_DEADLINE_HOURS`=2시간 전, 가정치) 이전 취소는 귀책과 무관하게 홀드 전액
      반환. 마감 이후 취소는 취소한 본인이 귀책자로 기록되고, 귀책자가 요청자(홀드 보유자)이면
      홀드가 제공자에게 이전, 제공자면 요청자에게 반환(제공자 잘못으로 요청자가 손해볼 근거 없음)
- [x] 노쇼(REQ-F-CAR-07/PNT-05): 세션 종료 시각이 지나도록 체크인이 없으면 상대 당사자가 신고.
      신고자의 반대편이 귀책자로 기록되며, 요청자 귀책이면 홀드가 제공자에게 이전(원장에 사유
      기록), 제공자 귀책이면 요청자에게 홀드 전액 반환
- [x] 신뢰 점수 연동: `trust_score_service.py`의 `NO_SHOW_RATE_STUB` 제거, `CareSession.status
      == NO_SHOW` + `at_fault_user_id`로 실제 노쇼율 계산(완료 또는 노쇼 처리된 세션 대비 본인
      귀책 노쇼 비율). 귀책 없는 취소는 노쇼가 아니므로 분모·분자 어디에도 포함하지 않음
- [x] API: `POST /car/requests/{id}/cancel`, `POST /car/requests/{id}/no-show`,
      `GET /pnt/balance` 응답에 `held_balance` 추가
- [x] (공통) 새 컬럼/테이블은 Alembic 마이그레이션(`f1a2b3c4d5e6_point_hold_care_cancel.py`) +
      `docs/dev/ERD.dbml` v1.9 동기화
- [x] (공통) 테스트를 TDD로 먼저 작성(`app/tests/pnt_apis/test_point_hold_service.py`,
      `app/tests/car_apis/test_care_session_cancel_noshow.py`, `test_trust_score_service.py`
      노쇼 회귀 1건 추가), `uv run --group app pytest -v` 67 passed(회귀 없음)
- [x] (공통) `ruff check .` / `ruff format --check .` / `uv run --group app mypy .` 통과

---

### 허용 경로
```
app/models/point_account.py            (확장 — held_balance)
app/models/point_hold.py                (신규)
app/models/care_session.py              (확장 — CANCELLED/NO_SHOW, cancel_*/at_fault_user_id)
app/repositories/point_hold_repository.py  (신규)
app/services/point_ledger_service.py    (홀드 생성/정산/반환/몰수)
app/services/care_session_service.py    (cancel/report_no_show 추가, accept() 훅)
app/services/trust_score_service.py     (NO_SHOW_RATE_STUB 제거, 실계산)
app/dtos/care_session_dto.py            (CancelRequest/NoShowReportRequest, 응답 필드 확장)
app/dtos/point_dto.py                   (held_balance)
app/apis/v1/car_routers.py              (cancel/no-show 엔드포인트)
app/apis/v1/pnt_routers.py              (balance 응답 확장)
app/core/db/migrations/versions/**      (신규 리비전 파일만 추가)
app/tests/pnt_apis/**                    (신규 테스트)
app/tests/car_apis/**                     (신규 테스트, 기존 파일 회귀 확인만)
app/tests/trs_apis/test_trust_score_service.py  (노쇼 회귀 테스트 추가)
docs/dev/ERD.dbml
docs/tasks/T-PNT-2.md
docs/tasks/_active.json (등록/해제만)
```

### 금지 경로
- `auth_kit/**`, `security_kit/**`
- `app/models/trust_weights.py`, `app/repositories/trust_weight_repository.py` (읽기 전용)

### 의존하는 공유 계약 (읽기만)
- `app/core/db/migrations/versions/e4a7b1d0c9f2_point_ledger.py` — 마이그레이션 체인 head
- `app/dependencies` — `get_current_user`

### 자율 판단 / 가정
1. **홀드 구현 방식**: 두 당사자 간 실제 이동이 아니라 요청자 본인 계정 내 예약이므로
   `PointTransaction`/`PointEntry`(원장)를 생성하지 않고 `PointAccount.balance`→`held_balance`
   이동 + `PointHold` 행으로만 추적한다. 실제로 상대에게 넘어가는 시점(정산/몰수)에만 원장 거래를
   기록해 T-PNT-1의 "합계 0 구조적 보장" 불변식을 그대로 유지한다.
2. **취소 마감 시각 수치**: 요구사항정의서에 구체 수치 없음 — `CANCELLATION_DEADLINE_HOURS=2`
   (세션 시작 2시간 전)로 가정(T-PNT-1의 SEED_POINTS/한도 가정과 동일한 성격).
3. **"홀드분의 일부를 상대에게 이전"의 비율**: 원문이 구체적 비율을 명시하지 않아 MVP 가정으로
   전액(100%) 이전한다. 부분 몰수 정책(예: 50%)이 필요하면 후속 Task에서 정책값을 추가한다.
4. **노쇼 판정 방식**: 이 시스템은 제공자만 체크인을 수행하므로(요청자 측 확인 액션 없음),
   시스템이 자동으로 노쇼를 판정하지 않고 세션 종료 시각 경과 후 당사자 신고(`report_no_show`)
   방식으로 처리한다. 신고자의 반대편이 자동으로 귀책자가 된다(상호 허위 신고 방지 로직은
   범위 밖 — 분쟁 처리는 REQ-F-CAR-08, 별도 Task).
5. **취소 마감 이후 취소의 귀책 판정**: "취소한 사람이 귀책자"로 가정한다. 즉 제공자가 마감 이후
   취소해도 요청자의 홀드는 몰수되지 않고 전액 반환된다(요청자에게 잘못이 없으므로).
6. **신뢰 점수 노쇼율 분모**: "완료(체크아웃)되었거나 노쇼 처리된 세션" 중 본인 귀책 노쇼 비율로
   계산한다. 귀책 없는 취소(마감 전 취소, 상대 귀책 취소)는 무단 불참이 아니므로 분모에도
   포함하지 않는다 — REQ-F-CAR-07 원문이 "무단 불참(노쇼)"만 신뢰 점수 반영 대상으로 명시하기
   때문.

### 반드시 멈춰야 하는 경우
- 현금 보증금·PG 연동(REQ-F-PNT-05 명시적으로 P1 이월 대상) — 착수하지 않음
- 분쟁 A/B/C 처리(REQ-F-CAR-08)로 인한 포인트 홀드 정책 변경이 필요한 경우 (별도 Task)
- 노쇼/취소 알림 발송(COM-02 연동) — 알림 도메인이 아직 없어 훅만 남기고 발송은 후속 Task

---

### 완료 보고
- 완료 정의 체크리스트 결과: 전항목 완료(위 "완료 정의" [x] 참고), `uv run --group app pytest -v`
  67 passed(회귀 없음), `ruff check .`/`ruff format --check .`/`uv run --group app mypy .` 모두 통과
- 가정(Assumptions): 위 "자율 판단 / 가정" 참고
- 공유 계약 변경 필요 사항: 없음(단일 백엔드 담당자 체제, SQUAD_MAP v3.0)
- 브랜치명: `feature/T-PNT-2-point-hold-noshow`
