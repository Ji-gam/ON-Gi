"""공공데이터 수집 — H1-a 검증용 (docs/plan/HYPOTHESIS_ROADMAP.md §3.5)

승인된 API 3종을 호출해 지역별 미충족 수요를 집계한다.
어린이집 정보(15013108)는 승인 대기 중이라 별도 추가 예정.

사용:
    python scripts/fetch_care_data.py --check          # 키·연결 확인만
    python scripts/fetch_care_data.py --region 서울    # 시도 필터
    python scripts/fetch_care_data.py --out data/      # CSV 저장

인증키는 .env 의 DATA_GO_KR_KEY 에서 읽는다. 코드·로그에 키를 남기지 않는다.
"""

from __future__ import annotations

import argparse
import csv
import os
import sys
from pathlib import Path
from typing import Any
from urllib.parse import urlencode
from urllib.request import urlopen
import json

# ── 엔드포인트 ────────────────────────────────────────────────────────────
BASE = "https://apis.data.go.kr/1383000/idis"

APIS = {
    "members": {  # 15078125 회원현황 — 대기정회원수(미충족 수요)
        "url": f"{BASE}/memberService/getMemberList",
        "label": "아이돌봄 회원현황",
    },
    "sitters": {  # 15078153 아이돌보미 현황 — 바로연계가능 인력(공급)
        "url": f"{BASE}/careGiverService/getCareGiverList",
        "label": "아이돌보미 현황",
    },
    "orgs": {  # 15078130 서비스제공기관 — 시도·시군구·좌표
        "url": f"{BASE}/serviceInstitutionService/getServiceInstitutionList",
        "label": "서비스제공기관",
    },
}


def load_key() -> str:
    """.env 에서 인증키를 읽는다. 값은 절대 출력하지 않는다."""
    key = os.environ.get("DATA_GO_KR_KEY")
    if key:
        return key.strip()

    for candidate in (
        Path(__file__).resolve().parents[1] / ".env",   # 워크트리
        Path("D:/AI_Healthcare/ON-Gi/.env"),            # 메인 저장소
        Path.cwd() / ".env",
    ):
        if candidate.exists():
            for line in candidate.read_text(encoding="utf-8").splitlines():
                if line.startswith("DATA_GO_KR_KEY="):
                    return line.split("=", 1)[1].strip()

    sys.exit("DATA_GO_KR_KEY 를 찾지 못했습니다. .env 를 확인하세요.")


def call(url: str, key: str, page: int = 1, rows: int = 100) -> dict[str, Any]:
    query = urlencode(
        {"serviceKey": key, "pageNo": page, "numOfRows": rows, "type": "json"},
        safe="%",  # 이미 인코딩된 키가 이중 인코딩되지 않도록
    )
    with urlopen(f"{url}?{query}", timeout=30) as resp:
        raw = resp.read().decode("utf-8", errors="replace")

    if raw.lstrip().startswith("<"):          # XML = 대개 에러 응답
        raise RuntimeError(f"XML 응답(키 미승인·반영대기 가능): {raw[:200]}")
    return json.loads(raw)


def rows_of(payload: dict[str, Any]) -> list[dict[str, Any]]:
    """포털 응답 구조가 서비스마다 조금씩 달라 방어적으로 파고든다."""
    node: Any = payload
    for _ in range(6):
        if isinstance(node, list):
            return [r for r in node if isinstance(r, dict)]
        if not isinstance(node, dict):
            return []
        for k in ("item", "items", "body", "response", "data"):
            if k in node:
                node = node[k]
                break
        else:
            return [node] if node else []
    return []


def fetch_all(name: str, key: str, max_pages: int = 400) -> list[dict[str, Any]]:
    """totalCount 를 보고 끝까지 받는다. 페이지 상한만 믿으면 조용히 잘린다."""
    spec = APIS[name]
    out: list[dict[str, Any]] = []
    total: int | None = None

    for page in range(1, max_pages + 1):
        payload = call(spec["url"], key, page=page)
        if total is None:
            total = _find_total(payload)
        batch = rows_of(payload)
        if not batch:
            break
        out.extend(batch)
        if total is not None and len(out) >= total:
            break
        if len(batch) < 100:
            break

    if total is not None and len(out) < total:
        print(f"  ! {spec['label']}: {len(out)}/{total}건만 수집됨(페이지 상한)")
    return out


def _find_total(payload: Any, depth: int = 0) -> int | None:
    if depth > 6 or not isinstance(payload, dict):
        return None
    if "totalCount" in payload:
        try:
            return int(str(payload["totalCount"]).strip())
        except ValueError:
            return None
    for v in payload.values():
        if isinstance(v, dict):
            found = _find_total(v, depth + 1)
            if found is not None:
                return found
    return None


def num(v: Any) -> int:
    try:
        return int(str(v).strip() or 0)
    except ValueError:
        return 0


def latest_month_only(rows: list[dict], ym_field: str = "crtrYm") -> tuple[list[dict], str]:
    """기관×월 시계열이므로 최신 월만 남긴다. 안 그러면 같은 기관을 여러 번 더한다."""
    months = {r.get(ym_field) for r in rows if r.get(ym_field)}
    if not months:
        return rows, "-"
    latest = max(months)
    return [r for r in rows if r.get(ym_field) == latest], latest


def summarize(members: list[dict], sitters: list[dict]) -> None:
    """대기 수요 대 가용 인력 — H1-a 성공 기준의 '미충족 수요' 항목."""
    m_rows, m_ym = latest_month_only(members)
    s_rows, s_ym = latest_month_only(sitters)

    waiting = sum(num(r.get("stdbyRglmbrCnt")) for r in m_rows)
    regular = sum(num(r.get("rglmbrCnt")) for r in m_rows)
    new_kids = sum(num(r.get("newChildCnt")) for r in m_rows)
    ready = sum(num(r.get("thmmStrhtLinkPsbltSittrCnt")) for r in s_rows)
    sitters_all = sum(num(r.get("thmmSittrCnt")) for r in s_rows)

    print("\n── 집계 (최신 기준연월만) ──────────────────")
    print(f"수요 기준월 {m_ym} · 공급 기준월 {s_ym}")
    print(f"기관 수                  {len(m_rows):>8,}")
    print(f"정회원(이용 중)          {regular:>8,}")
    print(f"대기 정회원              {waiting:>8,}   ← 공공이 못 받아내는 수요")
    print(f"신규 아동                {new_kids:>8,}")
    print(f"당월 돌보미              {sitters_all:>8,}")
    print(f"바로 연계 가능 돌보미    {ready:>8,}   ← 지금 투입 가능한 공급")
    if ready:
        print(f"대기 1명당 가용 돌보미   {ready / waiting:>8.2f}" if waiting else "")
    if regular:
        print(f"대기 비율                {waiting / regular * 100:>7.1f}%")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--check", action="store_true", help="연결 확인만")
    ap.add_argument("--out", type=Path, help="CSV 저장 디렉터리")
    args = ap.parse_args()

    key = load_key()
    print(f"인증키 로드 완료 ({len(key)}자)\n")

    collected: dict[str, list[dict]] = {}
    for name, spec in APIS.items():
        try:
            rows = fetch_all(name, key, max_pages=1 if args.check else 400)
            collected[name] = rows
            sample = ", ".join(list(rows[0])[:6]) if rows else "-"
            print(f"[OK]   {spec['label']:<16} {len(rows):>5}건   필드: {sample}")
        except Exception as exc:                      # noqa: BLE001
            collected[name] = []
            print(f"[FAIL] {spec['label']:<16} {exc}")

    if not args.check and collected.get("members"):
        summarize(collected["members"], collected.get("sitters", []))

    if args.out:
        args.out.mkdir(parents=True, exist_ok=True)
        for name, rows in collected.items():
            if not rows:
                continue
            path = args.out / f"{name}.csv"
            with path.open("w", newline="", encoding="utf-8-sig") as fh:
                writer = csv.DictWriter(fh, fieldnames=list(rows[0]))
                writer.writeheader()
                writer.writerows(rows)
            print(f"저장 {path} ({len(rows)}건)")


if __name__ == "__main__":
    main()
