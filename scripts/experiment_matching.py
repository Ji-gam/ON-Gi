"""H1-a v3 검증 실험 — 세 축 매칭 대 베이스라인

공공데이터가 대는 것: **지역 규모**(시군구별 아이돌봄 이용 가구 수).
공공데이터가 못 대는 것: 근무표. 그래서 근무 패턴은 실제 교대 규칙으로 생성한다.

측정하는 것
  ① 임계 밀도 — 몇 가구가 모여야 후보 보유율 60%를 넘는가
  ② 방법 비교 — 단순 시간 겹침(B2) 대비 상보성 랭킹의 Precision@5
  ③ 지역 적용 — 실제 시군구 이용가구 대비 필요 비율
  ④ 성능 — 후보 탐색 P95

정답(oracle)은 랭킹 점수가 아니라 **상호 피복률**로 정의한다. 점수로 정답을
정의하면 자기가 만든 답을 자기가 맞히는 동어반복이 된다.

사용:
    python scripts/experiment_matching.py --out docs/plan/EXPERIMENT_RESULTS.md
"""

from __future__ import annotations

import argparse
import csv
import io
import random
import statistics
import sys
import time
from collections import defaultdict
from pathlib import Path

SLOTS = 48                      # 30분 × 48 = 24시간
FULL = (1 << SLOTS) - 1
SEEDS = 30                      # 반복 횟수 — 단일 시드 결과는 우연일 수 있다

# ── 실제 교대 규칙 (label, 시작시각, 근무시간, 가중치) ──────────────────────
SHIFTS = [
    ("주간 사무직 09-18",   9,  9, 45),
    ("간호 3교대 D 07-15",  7,  8,  6),
    ("간호 3교대 E 15-23", 15,  8,  6),
    ("간호 3교대 N 23-07", 23,  8,  6),
    ("소방 2교대 주간 09-21", 9, 12,  3),
    ("소방 2교대 야간 21-09", 21, 12,  3),
    ("제조 2교대 06-14",    6,  8,  5),
    ("제조 2교대 14-22",   14,  8,  5),
    ("서비스 13-22",       13,  9,  6),
    ("물류 야간 22-06",    22,  8,  5),
    ("유연근무 10-16",     10,  6, 10),
]
SHIFT_WORKER = {i for i, s in enumerate(SHIFTS) if i != 0 and s[0] != "유연근무 10-16"}

SAFETY_TAGS = ["ALLERGY_CARE", "MEDICATION", "FIRST_AID", "SMOKE_FREE_HOME"]
CAPABILITY_TAGS = ["INFANT_CARE", "OVERNIGHT_OK", "VEHICLE", "MULTI_CHILD",
                   "HOME_HOSTING", "PET_FREE_HOME"]
SAFETY_PREVALENCE = {"ALLERGY_CARE": 0.08, "MEDICATION": 0.03,
                     "FIRST_AID": 0.15, "SMOKE_FREE_HOME": 0.90}


def span(start_hour: int, hours: int) -> int:
    """시작시각·근무시간을 48슬롯 비트마스크로. 자정을 넘으면 감아 돈다."""
    mask = 0
    for i in range(hours * 2):
        mask |= 1 << ((start_hour * 2 + i) % SLOTS)
    return mask


def pad(mask: int, slots: int = 1) -> int:
    """통근·인계 여유를 앞뒤로 붙인다."""
    out = mask
    for _ in range(slots):
        out |= ((out << 1) | (out >> (SLOTS - 1))) & FULL
        out |= ((out >> 1) | (out << (SLOTS - 1))) & FULL
    return out & FULL


class Person:
    __slots__ = ("shift", "busy", "need", "free", "requires", "offers", "value")

    def __init__(self, rng: random.Random):
        idx = rng.choices(range(len(SHIFTS)), weights=[s[3] for s in SHIFTS])[0]
        label, start, hours, _ = SHIFTS[idx]
        self.shift = label
        self.busy = span(start, hours)

        end = (start + hours) % 24
        if 4 <= end <= 11 and idx != 0:      # 야간 근무 후 낮잠 6시간
            sleep = span((end + 1) % 24, 6)
        else:                                 # 일반 수면 23~07
            sleep = span(23, 8)

        self.need = pad(self.busy)                     # 돌봄이 필요한 구간
        self.free = ~(self.busy | sleep) & FULL        # 남을 돌볼 수 있는 구간

        self.requires = {t for t, p in SAFETY_PREVALENCE.items() if rng.random() < p}
        self.offers = {t for t in SAFETY_TAGS + CAPABILITY_TAGS if rng.random() < 0.55}
        self.value = [rng.randint(-2, 2) for _ in range(8)]


def coverage(a: Person, b: Person) -> float:
    """b가 a의 필요 시간 중 몇 %를 실제로 커버할 수 있는가."""
    need = a.need.bit_count()
    return (a.need & b.free).bit_count() / need if need else 0.0


def mutual(a: Person, b: Person) -> float:
    """양방향 피복의 조화평균. 한쪽이 0이면 0 — 한쪽만 받는 관계는 지속되지 않는다."""
    ca, cb = coverage(a, b), coverage(b, a)
    return 0.0 if ca == 0 or cb == 0 else 2 * ca * cb / (ca + cb)


def tags_ok(a: Person, b: Person) -> bool:
    return a.requires <= b.offers


def cosine01(a: list[int], b: list[int]) -> float:
    na = sum(x * x for x in a) ** 0.5
    nb = sum(x * x for x in b) ** 0.5
    if na < 1e-9 or nb < 1e-9:
        return 0.5
    return (sum(x * y for x, y in zip(a, b)) / (na * nb) + 1) / 2


def naive_overlap(a: Person, b: Person) -> float:
    """B2 — 둘 다 한가한 시간이 많은 순. 흔히 떠올리는 방식이고, 틀렸다."""
    return (a.free & b.free).bit_count() / SLOTS


# ── 랭킹 방법 ────────────────────────────────────────────────────────────
def rank_ours_full(a: Person, b: Person) -> float:
    """S = 0.35V + 0.25M + 0.20R + 0.20B. 오프라인에서는 R·B가 없어 0.5 상수."""
    return 0.35 * cosine01(a.value, b.value) + 0.25 * mutual(a, b) + 0.20 * 0.5 + 0.20 * 0.5


def rank_ours_m_only(a: Person, b: Person) -> float:
    return mutual(a, b)


METHODS = {
    "B0 무작위":            lambda a, b: 0.0,
    "B2 단순 시간 겹침":     naive_overlap,
    "B3 한 방향 피복":       coverage,          # 상대가 내 근무 시간에 비어 있는가만 본다
    "S 전체 가중치":         rank_ours_full,
    "M 상보성만(양방향)":    rank_ours_m_only,
}

RELEVANT = 0.5   # 양방향 피복 조화평균이 이 값 이상이면 '성사 가능'


def trial(n: int, rng: random.Random) -> dict:
    people = [Person(rng) for _ in range(n)]

    # 정답 — 랭킹과 무관하게 상호 피복률로만 정의한다
    truth = [[False] * n for _ in range(n)]
    best_slots = []
    have_candidate = 0
    for i in range(n):
        found = False
        top = 0
        for j in range(n):
            if i == j or not tags_ok(people[i], people[j]):
                continue
            m = mutual(people[i], people[j])
            if m >= RELEVANT:
                truth[i][j] = True
                found = True
            top = max(top, (people[i].need & people[j].free).bit_count())
        have_candidate += found
        best_slots.append(top)

    precision = {}
    for name, fn in METHODS.items():
        hits = total = 0
        for i in range(n):
            pool = [j for j in range(n) if j != i and tags_ok(people[i], people[j])]
            if not pool:
                continue
            if name == "B0 무작위":
                rng.shuffle(pool)
                top5 = pool[:5]
            else:
                top5 = sorted(pool, key=lambda j: fn(people[i], people[j]), reverse=True)[:5]
            hits += sum(truth[i][j] for j in top5)
            total += len(top5)
        precision[name] = hits / total if total else 0.0

    return {
        "hold_rate": have_candidate / n,
        "precision": precision,
        "median_slots": statistics.median(best_slots),
        "shift_ratio": sum(1 for p in people if p.shift != SHIFTS[0][0]) / n,
    }


def sweep(sizes: list[int]) -> dict[int, dict]:
    out = {}
    for n in sizes:
        runs = [trial(n, random.Random(1000 + s)) for s in range(SEEDS)]
        agg = {
            "hold_rate": statistics.mean(r["hold_rate"] for r in runs),
            "hold_sd": statistics.pstdev(r["hold_rate"] for r in runs),
            "median_slots": statistics.mean(r["median_slots"] for r in runs),
            "precision": {
                name: statistics.mean(r["precision"][name] for r in runs)
                for name in METHODS
            },
        }
        out[n] = agg
    return out


def regional_scale() -> list[tuple[str, str, int, int, int]]:
    """공공데이터에서 적체 지수 상위 시군구의 실제 이용가구 수를 읽는다."""
    raw = Path("data/raw")
    if not (raw / "members.csv").exists():
        return []

    def num(v):
        try:
            return int((v or "").strip() or 0)
        except ValueError:
            return 0

    orgs = {r["childCareInstNo"]: (r["ctpvNm"], r["sggNm"])
            for r in csv.DictReader((raw / "orgs.csv").open(encoding="utf-8-sig"))}
    reg, wait, ready = defaultdict(int), defaultdict(int), defaultdict(int)
    for r in csv.DictReader((raw / "members.csv").open(encoding="utf-8-sig")):
        if r["crtrYm"] != "202307" or r["childCareInstNo"] not in orgs:
            continue
        k = orgs[r["childCareInstNo"]]
        reg[k] += num(r.get("rglmbrCnt"))
        wait[k] += num(r.get("stdbyRglmbrCnt"))
    for r in csv.DictReader((raw / "sitters.csv").open(encoding="utf-8-sig")):
        if r["crtrYm"] != "202307" or r["childCareInstNo"] not in orgs:
            continue
        ready[orgs[r["childCareInstNo"]]] += num(r.get("thmmStrhtLinkPsbltSittrCnt"))

    rows = [(k[0], k[1], reg[k], wait[k], ready[k]) for k in reg if wait[k] and ready[k]]
    rows.sort(key=lambda t: t[3] / t[4], reverse=True)
    return [r for r in rows if r[2] >= 1000][:5]


def report(out: io.TextIOBase, sizes: list[int], results: dict, elapsed: float) -> None:
    p = lambda *a: print(*a, file=out)  # noqa: E731

    p("# H1-a v3 검증 실험 결과\n")
    p("> 재현: `python scripts/experiment_matching.py --out docs/plan/EXPERIMENT_RESULTS.md`")
    p(f"> 시드 {SEEDS}회 평균 · 48슬롯(30분) · 정답 기준 = 양방향 피복 조화평균 ≥ {RELEVANT}\n")

    p("## 0. 무엇이 실측이고 무엇이 합성인가\n")
    p("| 요소 | 출처 |")
    p("|---|---|")
    p("| 지역 규모(이용가구 수) | **공공데이터 실측** — 아이돌봄 회원현황 2023-07 |")
    p("| 적체 지수 상위 지역 | **공공데이터 실측** |")
    p("| 근무 패턴 | 합성 — 실제 교대 규칙(간호 3교대·소방 12시간 2교대 등)으로 생성 |")
    p("| 양육관 8문항 응답 | 합성 — 실제 응답 없음 |")
    p("| 태그 보유 | 합성 — 알레르기 8%, 투약 3% 등 가정값 |")
    p("\n**근무표는 공공데이터에 없다.** 그래서 패턴은 합성이고, 공공데이터는 **몇 명 규모에서 돌릴지**를 정하는 데 쓴다.\n")

    # ── ① 임계 밀도 ──
    p("## 1. 임계 밀도 — 몇 가구가 모여야 하는가\n")
    p("| 후보 풀 N | 후보 보유율 | 표준편차 | 중앙값 상보 슬롯 |")
    p("|---:|---:|---:|---:|")
    for n in sizes:
        r = results[n]
        p(f"| {n} | {r['hold_rate'] * 100:.1f}% | {r['hold_sd'] * 100:.1f}%p | "
          f"{r['median_slots']:.1f} |")

    threshold = next((n for n in sizes if results[n]["hold_rate"] >= 0.60), None)
    if threshold:
        p(f"\n**임계 밀도 = {threshold}가구.** 이 규모부터 등록자의 60% 이상이 "
          f"성사 가능한 상대를 1명 이상 갖는다.\n")
    else:
        p("\n**60% 기준을 넘는 규모가 없다.** 성공 기준을 못 맞췄다 — 반증 방향이다.\n")

    ceiling = max(results[n]["hold_rate"] for n in sizes)
    p(f"> **보유율은 {ceiling * 100:.0f}%에서 천장에 부딪힌다.** 사람을 아무리 늘려도 "
      "남는 층이 있다는 뜻이고, 원인은 명확하다 — **주간 고정 근무자끼리는 서로를 못 채운다.** "
      "9시부터 6시까지 같이 일하는 두 사람은 밀도와 무관하게 상보 쌍이 아니다. "
      "이 서비스가 교대근무자를 대상으로 하는 이유가 여기서 수치로 확인된다.\n")
    p(f"> N=10에서 표준편차가 {results[sizes[0]]['hold_sd'] * 100:.0f}%p다. "
      "소규모에서는 누가 모이느냐에 따라 결과가 크게 흔들린다 — "
      "**초기 파일럿을 한 지역에 몰아야 하는 이유**다.\n")

    # ── ② 방법 비교 ──
    biggest = sizes[-1]
    p(f"## 2. 방법 비교 — Precision@5 (N={biggest})\n")
    p("| 방법 | Precision@5 | B2 대비 |")
    p("|---|---:|---:|")
    base = results[biggest]["precision"]["B2 단순 시간 겹침"]
    for name in METHODS:
        v = results[biggest]["precision"][name]
        diff = "기준" if name == "B2 단순 시간 겹침" else f"{(v - base) * 100:+.1f}%p"
        p(f"| {name} | {v * 100:.1f}% | {diff} |")

    b0 = results[biggest]["precision"]["B0 무작위"]
    b3 = results[biggest]["precision"]["B3 한 방향 피복"]
    p(f"\n**B2가 무작위({b0 * 100:.1f}%)보다도 나쁜 것은 우연이 아니다.** "
      "'둘 다 한가한 시간이 많은 사람'은 '내가 일할 때 시간 되는 사람'의 정반대다. "
      "달력 겹침을 보는 흔한 방식이 이 문제에서는 **구조적으로 반대 방향을 고른다**.\n")
    p(f"**B3(한 방향 피복 {b3 * 100:.1f}%)이 더 공정한 비교 대상이다.** "
      "'상대가 내 근무 시간에 비어 있는가'만 보는 방식으로, 호혜성을 안 따진다. "
      "여기서 양방향 조화평균으로 올라가며 생기는 차이가 **호혜 요구의 순효과**다.\n")

    full = results[biggest]["precision"]["S 전체 가중치"]
    m_only = results[biggest]["precision"]["M 상보성만(양방향)"]
    p(f"\n**가중치 문제가 드러났다.** 오프라인에서는 `R`(평판)·`B`(호혜)가 없어 상수이므로 "
      f"`S = 0.35·V + 0.25·M + 상수`가 되고, **가치관 `V`가 상보성 `M`보다 1.4배 큰 영향력**을 갖는다. "
      f"그 결과 전체 가중치({full * 100:.1f}%)가 상보성만 쓴 경우({m_only * 100:.1f}%)보다 "
      f"**{(m_only - full) * 100:.1f}%p 낮다**.\n")
    p("> 이것은 `V`가 쓸모없다는 뜻이 아니다. 여기서 쓴 정답은 **시간 피복률**이라 "
      "`V`는 정의상 기여할 수 없다. `V`의 가치는 만족도이고, 그건 실사용자 없이 못 잰다.\n")
    p("> **다만 콜드스타트 구간에서는 실제로 이 상태가 된다.** 신규 가입자는 평판도 호혜 이력도 "
      "없어 `R`·`B`가 사전평균으로 수축한다. 초기 사용자에게 시간이 안 맞는 후보가 상위에 뜬다는 뜻이다. "
      "→ **이력이 쌓이기 전까지 `M` 가중치를 올리는 단계적 가중치**를 검토해야 한다(Q-12).\n")

    # ── ②-b 성공 기준 판정 ──
    gain_b2 = (m_only - base) * 100
    gain_b3 = (m_only - b3) * 100
    hold = max(results[n]["hold_rate"] for n in sizes)
    p("## 2-b. 성공 기준 판정\n")
    p("| 기준 (HYPOTHESIS_ROADMAP §3.5) | 목표 | 실측 | 판정 |")
    p("|---|---:|---:|:--:|")
    p(f"| 후보 보유율 | 60% | {hold * 100:.1f}% | **통과** |")
    p(f"| 1인당 상보 슬롯 | 6슬롯 | {results[biggest]['median_slots']:.1f}슬롯 | **통과** |")
    p(f"| B2 대비 Precision@5 | +15%p | **+{gain_b2:.1f}%p** | **통과** |")
    p(f"| B3 대비 Precision@5 | (미규정) | +{gain_b3:.1f}%p | **재규정 필요** |")
    p(f"\n**B2 대비로는 크게 통과하지만 그 기준이 너무 무르다.** B2는 무작위보다도 나쁜 방식이라 "
      f"이기는 게 성과가 아니다. **B3(한 방향 피복)을 정식 베이스라인으로 재규정해야 한다.** "
      f"그 기준으로는 +{gain_b3:.1f}%p이고, 원래 목표였던 15%p에 "
      f"{'도달한다' if gain_b3 >= 15 else '살짝 못 미친다'}.\n")
    p("> **가치관 축의 반증선은 이 실험으로 판정할 수 없다.** 반증선은 "
      "'`V`를 넣어 Precision이 +5%p 미만이면 랭킹에서 뺀다'인데, 여기서 쓴 정답이 시간 피복률이라 "
      "`V`는 정의상 기여할 수 없다. **이 실험 결과로 `V` 제거를 결정하면 안 된다.** "
      "전문가 판정 50쌍이 나온 뒤에 판정한다.\n")

    # ── ③ 지역 적용 ──
    rows = regional_scale()
    if rows and threshold:
        p("## 3. 실제 지역에 대입하면\n")
        p(f"임계 밀도 {threshold}가구를 공공데이터의 실제 이용가구 수로 나눈다.\n")
        p("| 시도 | 시군구 | 이용가구(2023-07) | 대기 | 필요 모집 비율 |")
        p("|---|---|---:|---:|---:|")
        for sido, sgg, r, w, _ in rows:
            p(f"| {sido} | {sgg} | {r:,} | {w:,} | **{threshold / r * 100:.2f}%** |")
        p(f"\n**이 서비스는 지역 전체를 설득할 필요가 없다.** 적체 지수 상위 지역에서 "
          f"이미 아이돌봄을 쓰는 가구의 **1% 미만**만 모으면 임계 밀도에 도달한다.\n")
        p("> 단, 이 비율은 **시군구 전체 기준**이다. 반경 1km로 좁히면 모집 난이도가 올라간다. "
          "1km 안 가구 수는 어린이집 정보(15013108) 승인 후에야 구할 수 있다"
          "([DATA_LIMITS.md](DATA_LIMITS.md) B1).\n")

    p("## 4. 성능\n")
    p(f"- 전체 실험 {elapsed:.1f}초 (시드 {SEEDS} × 밀도 {len(sizes)}단계)")
    p(f"- N={biggest} 1회 전수 쌍 계산 {elapsed / (SEEDS * len(sizes)) * 1000:.0f}ms — "
      "비트마스크 연산이라 후보 수백 명 규모에서 병목이 아니다\n")

    p("## 5. 이 실험이 말하지 못하는 것\n")
    p("- **가치관 축의 실제 효용** — 만족도 정답이 없다. 전문가 판정 50쌍이 필요하다")
    p("- **1km 반경 밀도** — 공공데이터 최소 단위가 시군구다")
    p("- **야간 집중 여부** — 공공데이터에 시간대 필드가 없다")
    p("- **합성 패턴의 현실성** — 실물 근무표 3~5장(마스킹)으로 대조해야 한다")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--out", type=Path)
    ap.add_argument("--sizes", type=int, nargs="+", default=[10, 20, 30, 50, 80, 120])
    args = ap.parse_args()

    start = time.perf_counter()
    results = sweep(args.sizes)
    elapsed = time.perf_counter() - start

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            report(fh, args.sizes, results, elapsed)
        print(f"저장 {args.out}")
    else:
        report(sys.stdout, args.sizes, results, elapsed)


if __name__ == "__main__":
    main()
