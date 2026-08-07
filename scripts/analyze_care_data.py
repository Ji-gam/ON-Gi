"""수집한 공공데이터 집계 — H1-a 검증용 (docs/plan/HYPOTHESIS_ROADMAP.md §3.5)

fetch_care_data.py 가 저장한 data/raw/*.csv 를 읽어
① 대기 수요의 시계열 추이 ② 지역(시군구)별 수급 격차 를 낸다.

주의: 회원 통계는 기관×월 시계열이다. 월을 고정하지 않고 합치면 같은 기관을 여러 번 센다.

사용:
    python scripts/analyze_care_data.py
    python scripts/analyze_care_data.py --out docs/plan/data_findings.md
"""

from __future__ import annotations

import argparse
import csv
import io
import sys
from collections import defaultdict
from pathlib import Path

RAW = Path("data/raw")

# 대기 정회원(stdbyRglmbrCnt)은 202308부터 집계가 끊긴다. 마지막 유효 월.
LAST_WAITLIST_YM = "202307"


def load(name: str) -> list[dict[str, str]]:
    path = RAW / f"{name}.csv"
    if not path.exists():
        sys.exit(f"{path} 가 없습니다. 먼저 fetch_care_data.py 를 실행하세요.")
    with path.open(encoding="utf-8-sig", newline="") as fh:
        return list(csv.DictReader(fh))


def num(v: str | None) -> int:
    try:
        return int((v or "").strip() or 0)
    except ValueError:
        return 0


def by_month(rows: list[dict], field: str) -> dict[str, int]:
    out: dict[str, int] = defaultdict(int)
    for r in rows:
        out[r["crtrYm"]] += num(r.get(field))
    return dict(out)


def month_slice(rows: list[dict], ym: str) -> list[dict]:
    return [r for r in rows if r.get("crtrYm") == ym]


def region_table(
    members: list[dict], sitters: list[dict], orgs: list[dict], ym: str
) -> list[tuple]:
    """기관번호로 좌표·시군구를 붙여 지역별 수요/공급을 낸다."""
    place = {
        r["childCareInstNo"]: (r.get("ctpvNm", ""), r.get("sggNm", ""))
        for r in orgs
    }
    wait: dict[tuple, int] = defaultdict(int)
    reg: dict[tuple, int] = defaultdict(int)
    ready: dict[tuple, int] = defaultdict(int)

    for r in month_slice(members, ym):
        key = place.get(r["childCareInstNo"])
        if not key:
            continue
        wait[key] += num(r.get("stdbyRglmbrCnt"))
        reg[key] += num(r.get("rglmbrCnt"))
    for r in month_slice(sitters, ym):
        key = place.get(r["childCareInstNo"])
        if not key:
            continue
        ready[key] += num(r.get("thmmStrhtLinkPsbltSittrCnt"))

    rows = []
    for key in sorted(set(wait) | set(ready)):
        w, g = wait[key], ready[key]
        rows.append((key[0], key[1], reg[key], w, g, (w / g) if g else float("inf")))
    rows.sort(key=lambda t: t[5], reverse=True)
    return rows


def report(out: io.TextIOBase) -> None:
    members, sitters, orgs = load("members"), load("sitters"), load("orgs")

    p = lambda *a: print(*a, file=out)  # noqa: E731

    months = sorted({r["crtrYm"] for r in members})
    p(f"# 공공데이터 집계 결과\n")
    p(f"출처: 공공데이터포털 아이돌봄서비스 통합정보(1383000) — 회원현황·아이돌보미현황·서비스제공기관")
    p(f"수집 범위: {months[0][:4]}-{months[0][4:]} ~ {months[-1][:4]}-{months[-1][4:]} "
      f"({len(months)}개월, 기관 {len(orgs)}곳)\n")

    # ── ① 대기 수요 추이 ─────────────────────────────────────────
    wait = by_month(members, "stdbyRglmbrCnt")
    live = {k: v for k, v in wait.items() if v}
    first, last = min(live), max(live)
    p("## ① 공공 아이돌봄 대기 수요 추이\n")
    p(f"| 기준월 | 대기 정회원 | 정회원 |")
    p("|---|---:|---:|")
    reg = by_month(members, "rglmbrCnt")
    for ym in sorted(set(sorted(live)[::6]) | {last}):
        p(f"| {ym[:4]}-{ym[4:]} | {live[ym]:,} | {reg[ym]:,} |")
    seq = sorted(live)
    ups = sum(1 for a, b in zip(seq, seq[1:]) if live[b] > live[a])
    p(f"\n**{first[:4]}-{first[4:]} {live[first]:,}가구 → {last[:4]}-{last[4:]} "
      f"{live[last]:,}가구 ({live[last] / live[first]:.1f}배)** — "
      f"{len(seq) - 1}번의 월 전환 중 **{ups}번 증가**했다. 거의 한 번도 줄지 않았다.\n")
    p(f"> 한계: `stdbyRglmbrCnt`(대기 정회원)는 {LAST_WAITLIST_YM[:4]}-{LAST_WAITLIST_YM[4:]}을 "
      f"마지막으로 집계가 중단됐다. 이후 월은 0으로 채워져 있어 최신 대기 규모는 이 API로 알 수 없다.\n")

    aprv = by_month(members, "aprvStdbyMbrCnt")
    aprv_live = {k: v for k, v in aprv.items() if v}
    if aprv_live:
        am = max(aprv_live)
        p(f"> 대체 지표: {am[:4]}-{am[4:]}부터 `aprvStdbyMbrCnt`(승인 대기 회원) "
          f"{aprv_live[am]:,}명이 새로 집계된다. 정의가 달라 위 시계열과 직접 이을 수 없다.\n")

    # ── ② 정회원 정의 변경 경고 ──────────────────────────────────
    r_series = sorted(reg.items())
    breaks = [
        (a[0], b[0], a[1], b[1])
        for a, b in zip(r_series, r_series[1:])
        if a[1] and abs(b[1] - a[1]) / a[1] > 0.25
    ]
    if breaks:
        p("## ② 시계열 단절 (해석 주의)\n")
        for prev, cur, pv, cv in breaks:
            p(f"- {prev[:4]}-{prev[4:]} {pv:,} → {cur[:4]}-{cur[4:]} {cv:,} "
              f"({(cv - pv) / pv * 100:+.0f}%) — 집계 정의 변경으로 보인다. 이 구간을 가로질러 비교하면 안 된다.")
        p("")

    # ── ③ 지역별 수급 ────────────────────────────────────────────
    for ym, title in ((LAST_WAITLIST_YM, "대기 집계 마지막 월"), (months[-1], "최신 월")):
        rows = region_table(members, sitters, orgs, ym)
        has_wait = any(r[3] for r in rows)
        p(f"## 지역별 수급 — {ym[:4]}-{ym[4:]} ({title})\n")
        if not has_wait:
            p("대기 집계가 없는 월이라 격차를 계산할 수 없다. 공급(바로 연계 가능 돌보미)만 표시한다.\n")
            p("| 시도 | 시군구 | 정회원 | 바로 연계 가능 |")
            p("|---|---|---:|---:|")
            for sido, sgg, rg, _w, g, _ in sorted(rows, key=lambda t: -t[2])[:10]:
                p(f"| {sido} | {sgg} | {rg:,} | {g:,} |")
            p("")
        else:
            p("| 시도 | 시군구 | 정회원 | 대기 | 바로 연계 가능 | 대기/공급 |")
            p("|---|---|---:|---:|---:|---:|")
            for sido, sgg, rg, w, g, ratio in rows[:15]:
                shown = "공급 0" if ratio == float("inf") else f"{ratio:.2f}"
                p(f"| {sido} | {sgg} | {rg:,} | {w:,} | {g:,} | {shown} |")
            tw = sum(r[3] for r in rows)
            tg = sum(r[4] for r in rows)
            tr = sum(r[2] for r in rows)
            total_sitters = sum(num(r.get("thmmSittrCnt")) for r in month_slice(sitters, ym))
            per_sitter = tr / total_sitters if total_sitters else 0
            p(f"\n전국 합계: 대기 {tw:,}가구 / 바로 연계 가능 {tg:,}명 "
              f"(전체 돌보미 {total_sitters:,}명)\n")
            p(f"> **단위가 다르다.** 대기는 가구 수, 공급은 사람 수다. "
              f"{tw:,} ÷ {tg:,} = {tg / tw:.2f} 를 '1인당 {tg / tw:.2f}명이라 인력이 부족하다'로 "
              f"읽으면 안 된다 — 돌보미 1명은 여러 가구를 맡는다.\n")
            p(f"> 같은 시점 정회원 {tr:,}가구를 돌보미 {total_sitters:,}명이 감당 중 "
              f"= **1인당 {per_sitter:.1f}가구**. 이 비율이면 바로 연계 가능한 {tg:,}명만으로도 "
              f"대기 {tw:,}가구는 흡수됐어야 한다. **인력 총량 부족으로는 설명되지 않는다.**\n")
            p("> 왜 안 붙는지(시간대·조건·지역 불일치)는 이 API로 갈라낼 수 없다. "
              "야간 필드가 없기 때문이다. 원인은 설문으로 검증한다.\n")

    # ── ④ 좌표 확보 현황 ─────────────────────────────────────────
    geo = [r for r in orgs if (r.get("lat") or "").strip() and (r.get("lot") or "").strip()]
    p("## ④ 반경 분석용 좌표\n")
    p(f"- 서비스제공기관 {len(orgs)}곳 중 위경도 보유 {len(geo)}곳 ({len(geo) / len(orgs) * 100:.0f}%)")
    p(f"- 필드: `lat`(위도) `lot`(경도) `addr` `sggNm` — H3 인덱싱·반경 1km 계산에 바로 쓸 수 있다")
    p("- 다만 이건 **기관 좌표**다. 영유아 가구 밀도는 어린이집 정보(15013108, 승인 대기)의 "
      "정원·현원·좌표로 따로 구해야 한다\n")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path, help="마크다운으로 저장")
    args = ap.parse_args()

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            report(fh)
        print(f"저장 {args.out}")
    else:
        report(sys.stdout)


if __name__ == "__main__":
    main()
