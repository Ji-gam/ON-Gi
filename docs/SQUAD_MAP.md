# SQUAD_MAP.md — 담당자 매핑 (유일 출처)

v3.0 · 이력: `git log docs/SQUAD_MAP.md`. "이 파일/기능 담당자"의 유일 출처 — 다른 문서에 같은 표 중복 금지. 짝문서: `CONTRIBUTING.md` §2, `CODING_RULES.md` §2,§3-6.

> v3.0: 품앗이온(ON) 실제 팀 기준으로 재작성(배경: `docs/decision_log/2026-08-10.md`).
> 팀 온기 = 기획 1 · AI 1 · 백엔드 1 · 프론트엔드 1, 총 4명(정윤아·권순현·이은호·정다이).
> **역할↔이름 매핑은 요구사항정의서에 없어 미확정 — 담당자 칸 채우기 전 실제 배정 확인 필요.**
> 인원이 적어 ReMedi 템플릿처럼 "백엔드 도메인마다 다른 사람"을 가정한 세분화된 스쿼드
> 구조는 쓰지 않는다. 백엔드 1인이 전 도메인(ACC/SCH/MAT/TRS/CAR/PNT/COM/ADM)을 담당하고,
> 도메인 코드는 여러 에이전트가 동시에 작업할 때 충돌을 줄이는 파일명 접두어로만 쓴다.

1. 역할↔담당자 (TODO: 실제 이름 채우기)
기획 — (미확정) — 요구사항정의서/화면설계서/기능목록표 갱신, REQ-ID 발급
AI — (미확정) — `ai_worker/`, 매칭 근거문장 생성(REQ-F-MAT-06), 분쟁 B단계 챗봇(REQ-F-CAR-08/10)
백엔드 — (미확정) — `app/` 전 도메인(ACC/SCH/MAT/TRS/CAR/PNT/COM/ADM)
프론트엔드 — (미확정) — `frontend/` 전 화면

2. 도메인 코드 (파일명 접두어, `docs/CODING_RULES.md` §2 — 담당자는 위 "백엔드" 1인, 접두어는 병행작업 시 파일 충돌 방지용)
ACC 계정·프로필·아동 — REQ-F-ACC-01~11 — 접두어 `acc_*`
SCH 근무표·시간 — REQ-F-SCH-01~06 — 접두어 `sch_*`
MAT 매칭 — REQ-F-MAT-01~13 — 접두어 `mat_*`
TRS 신뢰·평판 — REQ-F-TRS-01~10 — 접두어 `trs_*`
CAR 돌봄세션 — REQ-F-CAR-01~10 — 접두어 `car_*`
PNT 포인트 — REQ-F-PNT-01~06 — 접두어 `pnt_*`
COM 커뮤니케이션 — REQ-F-COM-01~05 — 접두어 `com_*`
ADM 운영 — REQ-F-ADM-01~06 — 접두어 `adm_*`

3. 백엔드 공통모듈 소유자 (`app/services/*`, 접두어 없음 — 담당자 외 임의수정 금지, 동시수정시 충돌집중)
계정/인증공통 — `app/services/auth.py`(auth_kit 연동), `security_kit`/`auth_kit` — 백엔드
아동(Child) 공통 조회/수정 — `app/repositories/child_repository.py` — 백엔드
48슬롯 비트마스크 변환·상보 계산 — `app/services/schedule_bitmask_service.py`(신설예정) — 백엔드
매칭 점수 산출(하드필터→소프트점수) — `app/services/matching_service.py`(신설예정) — 백엔드
신뢰 등급 상태머신·신뢰 점수 산식 — `app/services/trust_service.py`(신설예정) — 백엔드
포인트 복식부기 원장 — `app/services/point_ledger_service.py`(신설예정) — 백엔드
매칭 근거문장 생성(LLM+RAG)·분쟁 B단계 컨텍스트 바인더 — `ai_worker/`, `app/services/llm_stub.py` — AI

4. 프론트 공통모듈 소유자 (`CODING_RULES.md` §3-6이 참조)
API클라이언트베이스 — `frontend/src/api/client.ts` — 프론트엔드
인증상태공유훅 — `frontend/src/hooks/useAuth.tsx` — 프론트엔드
근무표 48슬롯 캘린더 공통컴포넌트 — `frontend/src/components/common/ScheduleGrid.tsx`(신설예정) — 프론트엔드
