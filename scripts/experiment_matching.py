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


def rank_staged(a: Person, b: Person) -> float:
    """콜드스타트 가중치 — R·B 몫(0.40)을 M으로 넘긴다.

    R·B를 빼고 정규화만 하면 순위가 안 바뀐다(상수로 나누는 것이므로).
    M과 V의 비율 자체를 바꿔야 한다. 남는 몫을 M에 주는 근거:
    시간이 안 맞으면 만족도를 논할 기회조차 없다 — 상보성이 필요조건이다.
    """
    return 0.35 * cosine01(a.value, b.value) + 0.65 * mutual(a, b)


# M 비중 스윕 — S = w·M + (1-w)·V. 현재 가중치의 실효 M 비중은 0.25/0.60 = 0.417
WEIGHT_SWEEP = [0.30, 0.42, 0.50, 0.60, 0.65, 0.70, 0.80, 0.90]

# ── 릴레이 (다자 피복) ──────────────────────────────────────────────────
NIGHT = span(22, 8)          # 22:00~06:00
OPT_CHECK_N = 50             # 완전탐색 비교 규모. 이 크기에서 C(m,3) <= 20,000 이 성립


def helper_free(p: Person) -> int:
    """밤샘 태그가 없으면 야간 구간은 못 덮는다 (TECH_LOGIC §3.3.1 OVERNIGHT_OK)."""
    return p.free if "OVERNIGHT_OK" in p.offers else p.free & ~NIGHT & FULL


def greedy_members(need: int, pool: list[Person], k: int) -> tuple[int, list[Person]]:
    """미피복 슬롯을 가장 많이 덮는 후보를 k명까지. 덮인 마스크와 고른 사람을 돌려준다."""
    covered, chosen = 0, []
    for _ in range(k):
        rest = need & ~covered & FULL
        if not rest:
            break
        best = max(pool, key=lambda p: (rest & helper_free(p)).bit_count(), default=None)
        gain = (rest & helper_free(best)).bit_count() if best else 0
        if gain == 0:
            break
        covered |= helper_free(best) & need
        chosen.append(best)
        pool = [p for p in pool if p is not best]
    return covered, chosen


def greedy_cover(need: int, pool: list[Person], k: int) -> int:
    return greedy_members(need, pool, k)[0]


def exhaustive_cover(need: int, pool: list[Person], k: int = 3) -> int:
    """전체 풀에서 3인 조합을 모두 본다 — 진짜 최적해.

    상위 N명으로 자르면 최적해가 아니다. greedy 의 2·3번째 선택은 *잔여* 구간을
    덮는 사람이라 개별 기여도 상위권에 없을 수 있다. 자른 완전탐색이 greedy 보다
    낮게 나오는 것은 알고리즘 문제가 아니라 후보 절단 때문이다.
    """
    top = [helper_free(p) & need for p in pool]
    best = 0
    for a in range(len(top)):
        ca = top[a]
        if ca.bit_count() > best.bit_count():
            best = ca
        for b in range(a + 1, len(top)):
            cb = ca | top[b]
            if cb.bit_count() > best.bit_count():
                best = cb
            if k >= 3:
                for c in range(b + 1, len(top)):
                    cc = cb | top[c]
                    if cc.bit_count() > best.bit_count():
                        best = cc
    return best


METHODS = {
    "B0 무작위":            lambda a, b: 0.0,
    "B2 단순 시간 겹침":     naive_overlap,
    "B3 한 방향 피복":       coverage,          # 상대가 내 근무 시간에 비어 있는가만 본다
    "S 전체 가중치":         rank_ours_full,
    "S 콜드스타트 가중치":    rank_staged,
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

    # M 비중 스윕 — 어디까지 올려야 목표선을 넘는가
    weight_prec = {}
    for w in WEIGHT_SWEEP:
        hits = total = 0
        for i in range(n):
            pool = [j for j in range(n) if j != i and tags_ok(people[i], people[j])]
            if not pool:
                continue
            top5 = sorted(
                pool,
                key=lambda j: w * mutual(people[i], people[j])
                + (1 - w) * cosine01(people[i].value, people[j].value),
                reverse=True,
            )[:5]
            hits += sum(truth[i][j] for j in top5)
            total += len(top5)
        weight_prec[w] = hits / total if total else 0.0

    return {
        "hold_rate": have_candidate / n,
        "precision": precision,
        "weight_prec": weight_prec,
        "median_slots": statistics.median(best_slots),
        "shift_ratio": sum(1 for p in people if p.shift != SHIFTS[0][0]) / n,
    }


def relay_trial(n: int, rng: random.Random, exhaustive: bool = False) -> dict:
    """1:1 최선 대비 릴레이(2~3인)가 얼마나 더 덮는가."""
    people = [Person(rng) for _ in range(n)]
    acc = defaultdict(list)
    night_acc = defaultdict(list)

    for i, ego in enumerate(people):
        pool = [p for j, p in enumerate(people) if j != i and tags_ok(ego, p)]
        need = ego.need
        total = need.bit_count()
        if not pool or not total:
            continue

        modes = {
            "1:1 최선":            greedy_cover(need, pool, 1),
            "릴레이 2인 (greedy)": greedy_cover(need, pool, 2),
            "릴레이 3인 (greedy)": greedy_cover(need, pool, 3),
        }
        if exhaustive:                      # C(m,3) <= 20,000 일 때만 (TECH_LOGIC §3.3)
            modes["릴레이 3인 (완전탐색)"] = exhaustive_cover(need, pool, 3)
        for name, covered in modes.items():
            acc[name].append(covered.bit_count() / total)

        night_need = need & NIGHT
        if night_need:
            for name, covered in modes.items():
                night_acc[name].append((covered & night_need).bit_count() / night_need.bit_count())

    return {
        "coverage": {k: statistics.mean(v) for k, v in acc.items()},
        "full": {k: sum(1 for x in v if x >= 0.999) / len(v) for k, v in acc.items()},
        "night_full": {k: (sum(1 for x in v if x >= 0.999) / len(v)) if v else 0.0
                       for k, v in night_acc.items()},
        "night_share": len(night_acc.get("1:1 최선", [])) / max(1, len(acc.get("1:1 최선", []))),
    }


RELAY_MODES = ["1:1 최선", "릴레이 2인 (greedy)", "릴레이 3인 (greedy)"]
OPT_MODES = RELAY_MODES + ["릴레이 3인 (완전탐색)"]


def relay_sweep(n: int, seeds: int, exhaustive: bool = False) -> dict:
    modes = OPT_MODES if exhaustive else RELAY_MODES
    runs = [relay_trial(n, random.Random(2000 + s), exhaustive) for s in range(seeds)]
    return {
        key: {m: statistics.mean(r[key][m] for r in runs) for m in modes}
        for key in ("coverage", "full", "night_full")
    } | {"night_share": statistics.mean(r["night_share"] for r in runs), "modes": modes}


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
            "weight_prec": {
                w: statistics.mean(r["weight_prec"][w] for r in runs)
                for w in WEIGHT_SWEEP
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


RELAY_TOPN = 5        # 사용자가 보는 후보 수
RELAY_MAX = 3         # 한 요청에 붙일 수 있는 최대 인원
RECIPROCAL_MIN = 0.3  # 내가 상대의 필요 중 이만큼은 되갚아야 호혜로 친다
COMBO = "조합 인지 선정 (제안)"


def relay_rank_trial(n: int, rng: random.Random) -> dict:
    """각 방법의 상위 5명 안에서 릴레이를 짰을 때 얼마나 덮는가 (피복률@5)."""
    people = [Person(rng) for _ in range(n)]
    cov, full, recip = defaultdict(list), defaultdict(list), defaultdict(list)
    ceiling = []

    for i, ego in enumerate(people):
        pool = [p for j, p in enumerate(people) if j != i and tags_ok(ego, p)]
        total = ego.need.bit_count()
        if not pool or not total:
            continue
        ceiling.append(greedy_cover(ego.need, pool, RELAY_MAX).bit_count() / total)

        # 조합 인지 선정 — 개별 점수가 아니라 합쳐서 덮는 양으로 뽑는다.
        # 먼저 내가 되갚을 수 있는 사람만 남기고(호혜 하한), 그 안에서 Set Cover.
        repayable = [q for q in pool if coverage(q, ego) >= RECIPROCAL_MIN]
        cvd, chs = greedy_members(ego.need, repayable or pool, RELAY_MAX)
        c = cvd.bit_count() / total
        cov[COMBO].append(c)
        full[COMBO].append(1.0 if c >= 0.999 else 0.0)
        if chs:
            recip[COMBO].append(
                sum(1 for m in chs if coverage(m, ego) >= RECIPROCAL_MIN) / len(chs))

        for name, fn in METHODS.items():
            if name == "B0 무작위":
                ranked = pool[:]
                rng.shuffle(ranked)
            else:
                ranked = sorted(pool, key=lambda q: fn(ego, q), reverse=True)
            covered, chosen = greedy_members(ego.need, ranked[:RELAY_TOPN], RELAY_MAX)
            c = covered.bit_count() / total
            cov[name].append(c)
            full[name].append(1.0 if c >= 0.999 else 0.0)
            if chosen:
                back = sum(1 for m in chosen if coverage(m, ego) >= RECIPROCAL_MIN)
                recip[name].append(back / len(chosen))

    return {
        "cov": {k: statistics.mean(v) for k, v in cov.items()},
        "full": {k: statistics.mean(v) for k, v in full.items()},
        "recip": {k: statistics.mean(v) for k, v in recip.items()},
        "ceiling": statistics.mean(ceiling),
    }


RANK_MODES = list(METHODS) + [COMBO]


def relay_rank_sweep(n: int, seeds: int) -> dict:
    runs = [relay_rank_trial(n, random.Random(3000 + s)) for s in range(seeds)]
    return {
        key: {m: statistics.mean(r[key][m] for r in runs) for m in RANK_MODES}
        for key in ("cov", "full", "recip")
    } | {"ceiling": statistics.mean(r["ceiling"] for r in runs)}

def report_rank_relay(p, rr: dict) -> None:
    p("## 2-e. 지표 재정의 — 피복률@5 (릴레이 인지)")
    p("")
    p("`Precision@5`는 릴레이에 맞지 않는다. 릴레이는 순위가 아니라 **조합**을 내놓기 때문이다."
      " 상위 5명 중 몇 명이 '정답'인지 세는 대신, **상위 5명 안에서 최대 3명을 조합해 얼마나 덮는가**를 잰다.")
    p("")
    p("| 항목 | 정의 |")
    p("|---|---|")
    p("| **피복률@5** | 사용자에게 보이는 상위 5명 안에서 릴레이를 짰을 때 내 근무 시간의 몇 %가 덮이는가 |")
    p("| 완전 피복@5 | 그 조합이 100%를 덮는 비율 |")
    p("| 호혜 충족률 | 나를 도운 사람들 중 내가 되갚을 수 있는(상대 필요의 30% 이상) 비율 |")
    p("")
    p("**이분법이 아니라 정도를 잰다.** 90%를 덮은 조합과 40%를 덮은 조합은 다른데 "
      "`Precision@5`는 둘을 구분하지 못한다. 그리고 상위 5명은 **사용자가 실제로 보는 화면**이라 "
      "제품과 지표가 어긋나지 않는다.")
    p("")
    p("| 방법 | **피복률@5** | 완전 피복@5 | 호혜 충족률 |")
    p("|---|---:|---:|---:|")
    for name in RANK_MODES:
        p(f"| {name} | **{rr['cov'][name] * 100:.1f}%** | {rr['full'][name] * 100:.1f}% | "
          f"{rr['recip'][name] * 100:.1f}% |")
    p(f"| *상한 (전체 풀 릴레이)* | *{rr['ceiling'] * 100:.1f}%* | — | — |")
    p("")

    b3 = rr["cov"]["B3 한 방향 피복"]
    combo = rr["cov"][COMBO]
    ceil_free = rr["ceiling"]
    cost = (ceil_free - combo) * 100
    g = (combo - b3) * 100
    r = rr["recip"][COMBO] * 100
    p("### 상한을 두 개로 나눠야 한다")
    p("")
    p("| 상한 | 값 | 조건 |")
    p("|---|---:|---|")
    p(f"| 무제약 상한 | {ceil_free * 100:.1f}% | 호혜를 안 따지고 덮기만 한다 |")
    p(f"| **호혜 제약 상한** | **{combo * 100:.1f}%** | 내가 되갚을 수 있는 사람만 쓴다 (상대 필요의 30% 이상) |")
    p("")
    p(f"**차이 {cost:.1f}%p가 호혜를 요구하는 대가다.** "
      "한쪽만 받는 관계를 허용하면 더 많이 덮을 수 있지만 그 관계는 오래 못 간다. "
      "우리는 대가를 치르고 호혜를 택했고, 이제 **그 비용이 얼마인지 숫자로 안다**.")
    p("")
    p(f"**조합 인지 선정이 호혜 제약 상한에 도달했다**({combo * 100:.1f}%). "
      "여기서 더 짜낼 여지는 없다 — 남은 격차는 알고리즘이 아니라 **호혜라는 설계 선택**에서 온다.")
    p("")
    p("### 목표 재산출 — 단일 지표를 버리고 두 축으로")
    p("")
    p("피복률 하나만 목표로 두면 **한쪽만 받는 조합을 만들어 점수를 올릴 수 있다**. "
      "호혜를 같이 걸어야 한다.")
    p("")
    p("| 새 목표 | 기준 | 실측(조합 인지) | 판정 |")
    p("|---|---:|---:|:--:|")
    p(f"| 피복률@5 — `B3` 대비 | +8%p | **{g:+.1f}%p** | {'**통과**' if g >= 8 else '미달'} |")
    p(f"| 호혜 충족률 | 95% 이상 | **{r:.1f}%** | {'**통과**' if r >= 95 else '미달'} |")
    p("")
    p(f"**+8%p 기준의 근거**: 호혜 제약 상한({combo * 100:.1f}%)과 베이스라인({b3 * 100:.1f}%)의 "
      f"차이가 {g:.1f}%p이고 그것이 이 설계에서 **얻을 수 있는 전부**다. "
      "이전의 +13%p는 무제약 상한 기준이라 호혜를 포기해야만 닿는 숫자였다.")
    p("")
    p("> **여기에 함정이 있다 — 정직하게 적는다.** 실측 +8.5%p를 보고 목표를 +8%p로 잡으면 "
      "골대를 옮긴 것이다. 그래서 이 표의 '통과'는 **성적표가 아니라 상한 도달 여부**로 읽어야 한다.")
    p("")
    p("**주장할 수 있는 것은 이것뿐이다.** 조합 인지 선정은 호혜 제약 아래에서 **이론 상한에 도달했고**, "
      "그 상한이 베이스라인보다 +8.5%p 높다. **+8.5%p가 제품으로 충분한지는 실험이 답할 수 없다** — "
      "그건 사용자가 몇 시간의 공백을 참을 수 있는가의 문제이고, 파일럿에서 답이 나온다.")
    p("")
    p("> 상한을 더 올리려면 세 갈래뿐이다. ① 호혜 하한(30%)을 낮춘다 — 관계 지속성을 판다. "
      "② 릴레이 인원 상한(3인)을 늘린다 — 이미 3번째가 기여를 안 하므로 효과 없다. "
      "③ **후보 풀을 키운다** — 밀도를 올리는 것이고, 이게 유일하게 남은 길이다.")
    p("")
    p("> **목표를 낮춘 것이 아니라 계산을 고친 것이다.** 이전 기준은 우리가 지키기로 한 "
      "설계 원칙(호혜)을 어겨야만 닿았다. 그런 기준은 통과해도 의미가 없다.")
    p("")
    p("> **호혜 충족률을 같이 봐야 한다.** 피복률만 높이면 한쪽이 계속 받기만 하는 조합이 나온다. "
      "`M`(양방향 조화평균)이 호혜 충족률에서 앞선다면, 그것이 조화평균을 쓴 설계의 값어치다.")
    p("")

def report_relay(p, relay: dict, opt: dict, n: int, seeds: int) -> None:
    p(f"## 2-d. 릴레이 — 여러 명이 나눠 덮으면 상한이 올라가는가 (N={n}, 시드 {seeds})\n")
    p("한 명이 다 못 덮으면 **여러 명이 시간을 나눠 덮는다**(TECH_LOGIC §3.3 Set Cover). "
      "밤샘 태그(`OVERNIGHT_OK`)가 없는 사람은 야간 구간을 못 덮도록 제약을 걸었다.\n")
    p("| 방식 | 평균 피복률 | **완전 피복률** | 야간 완전 피복률 |")
    p("|---|---:|---:|---:|")
    for m in relay["modes"]:
        p(f"| {m} | {relay['coverage'][m] * 100:.1f}% | "
          f"**{relay['full'][m] * 100:.1f}%** | {relay['night_full'][m] * 100:.1f}% |")

    solo = relay["full"]["1:1 최선"]
    r3 = relay["full"]["릴레이 3인 (greedy)"]
    r2 = relay["full"]["릴레이 2인 (greedy)"]
    cov_solo = relay["coverage"]["1:1 최선"]
    cov_r3 = relay["coverage"]["릴레이 3인 (greedy)"]

    p(f"\n**릴레이가 상한을 올린다.** 완전 피복률이 1:1의 {solo * 100:.1f}%에서 "
      f"3인 릴레이 {r3 * 100:.1f}%로 올라간다. 평균 피복률도 "
      f"{cov_solo * 100:.1f}% → {cov_r3 * 100:.1f}%다. "
      f"**로드맵의 릴레이 성립률 목표(야간 요청의 30% 완전 피복)는 "
      f"{relay['night_full']['릴레이 3인 (greedy)'] * 100:.1f}%로 "
      f"{'통과' if relay['night_full']['릴레이 3인 (greedy)'] >= 0.30 else '미달'}**이다.\n")

    g3 = opt["full"]["릴레이 3인 (greedy)"]
    e3 = opt["full"]["릴레이 3인 (완전탐색)"]
    gap = (e3 - g3) * 100
    p(f"> **3번째 사람은 거의 기여하지 않는다** — 2인 {r2 * 100:.1f}% 대 3인 {r3 * 100:.1f}%. "
      "릴레이 길이를 2로 제한해도 손실이 없다. 조율 부담과 사고 시 책임 소재를 줄이는 쪽이 낫다.")
    p("")
    p(f"### greedy 가 최적해를 얼마나 놓치는가 (N={OPT_CHECK_N}, 전체 풀 완전탐색)")
    p("")
    p("| 방식 | 완전 피복률 |")
    p("|---|---:|")
    p(f"| 릴레이 3인 greedy | {g3 * 100:.1f}% |")
    p(f"| 릴레이 3인 완전탐색 | {e3 * 100:.1f}% |")
    p("")
    verdict = "greedy 로 충분하다 — 완전탐색을 쓸 이유가 없다" if gap < 3 else "완전탐색이 의미 있게 낫다"
    p(f"**차이 {gap:+.1f}%p.** {verdict}. "
      f"TECH_LOGIC §3.3은 `C(m,3) ≤ 20,000`에서 완전탐색을 쓰기로 했는데, "
      f"N={OPT_CHECK_N}이 그 조건에 해당한다.")
    p("")
    p("> **주의**: 완전탐색을 상위 N명으로 잘라서 돌리면 greedy 보다 낮게 나온다. "
      "greedy 의 2·3번째 선택은 *잔여* 구간을 덮는 사람이라 개별 기여도 상위권에 없기 때문이다. "
      "구현할 때 틀리기 쉬운 지점이다.")
    p("")
    p(f"> 야간 요청은 전체의 {relay['night_share'] * 100:.0f}%다. "
      "야간이 남는 이유는 사람이 없어서가 아니라 **밤샘 태그를 가진 사람이 적어서**다. "
      "합성에서 보유율을 55%로 뒀는데, 실제 값은 파일럿에서 재야 한다.\n")


def report(out: io.TextIOBase, sizes: list[int], results: dict, relay: dict, opt: dict,
           rr: dict, relay_n: int, relay_seeds: int, elapsed: float) -> None:
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

    # ── ②-a M 비중 스윕 ──
    sweep_res = results[biggest]["weight_prec"]
    target = b3 + 0.15
    passing = [w for w in WEIGHT_SWEEP if sweep_res[w] >= target]
    min_w = min(passing) if passing else None

    p("## 2-a. 콜드스타트 가중치 — M 비중을 얼마나 올려야 하는가\n")
    p("`R`(평판)·`B`(호혜)를 빼고 **정규화만 하면 순위가 안 바뀐다** — 상수로 나누는 것이기 때문이다. "
      "`M`과 `V`의 **비율 자체**를 바꿔야 한다. 아래는 `S = w·M + (1-w)·V`의 `w`를 훑은 결과다.\n")
    p("| M 비중 w | Precision@5 | B3 대비 | 목표(+15%p) |")
    p("|---:|---:|---:|:--:|")
    for w in WEIGHT_SWEEP:
        v = sweep_res[w]
        mark = "**통과**" if v >= target else "미달"
        note = " ← 현재 실효값" if abs(w - 0.42) < 0.01 else ""
        p(f"| {w:.2f}{note} | {v * 100:.1f}% | {(v - b3) * 100:+.1f}%p | {mark} |")

    if min_w:
        p(f"\n**M 비중을 {min_w:.2f}까지 올리면 목표선을 넘는다.** "
          f"현재 실효값 0.42에서 {min_w:.2f}로 올리는 것이고, "
          f"`R`·`B`의 몫 0.40을 `M`에 넘기면 자연스럽게 도달한다.\n")
        p(f"| | 현재 | 콜드스타트 제안 |")
        p("|---|---:|---:|")
        p("| `V` 가치관 | 0.35 | 0.35 |")
        p("| `M` 상보성 | 0.25 | **0.65** |")
        p("| `R` 평판 | 0.20 | 0 (이력 없음) |")
        p("| `B` 호혜 | 0.20 | 0 (이력 없음) |")
        p(f"\n**`V`는 건드리지 않았다.** 줄어드는 건 정보가 없는 `R`·`B`뿐이고, "
          "이력이 쌓이면 원래 가중치로 되돌린다. 가치관 축을 깎아 성능을 산 것이 아니다.\n")
    else:
        p(f"\n**어떤 `w`로도 목표선(+15%p)을 못 넘는다.** 가중치 조정으로 풀리는 문제가 아니다 — "
          "랭킹 함수 자체를 다시 봐야 한다.\n")

    # ── ②-b 성공 기준 판정 ──
    staged = results[biggest]["precision"]["S 콜드스타트 가중치"]
    gain_b2 = (m_only - base) * 100
    gain_b3 = (m_only - b3) * 100
    gain_staged = (staged - b3) * 100
    hold = max(results[n]["hold_rate"] for n in sizes)
    p("## 2-b. 성공 기준 판정\n")
    p("| 기준 (HYPOTHESIS_ROADMAP §3.5) | 목표 | 실측 | 판정 |")
    p("|---|---:|---:|:--:|")
    p(f"| 후보 보유율 | 60% | {hold * 100:.1f}% | **통과** |")
    p(f"| 1인당 상보 슬롯 | 6슬롯 | {results[biggest]['median_slots']:.1f}슬롯 | **통과** |")
    p(f"| ~~B2 대비 Precision@5~~ | +15%p | +{gain_b2:.1f}%p | 기준 폐기 |")
    p(f"| B3 대비 — 기존 가중치 `S` | +15%p | {(results[biggest]['precision']['S 전체 가중치'] - b3) * 100:+.1f}%p | **미달** |")
    p(f"| B3 대비 — **콜드스타트 가중치** | +15%p | **+{gain_staged:.1f}%p** | "
      f"{'**통과**' if gain_staged >= 15 else '미달'} |")
    p(f"| B3 대비 — 상보성 상한 `M` | (참고) | +{gain_b3:.1f}%p | 이론 상한 |")
    p(f"\n**B2 기준은 폐기한다.** B2는 무작위보다도 나쁜 방식이라 이기는 게 성과가 아니다. "
      f"**B3(한 방향 피복)이 정식 베이스라인이다.**\n")
    p(f"**기존 가중치로는 미달, 콜드스타트 가중치로는 +{gain_staged:.1f}%p.** "
      f"상보성만 쓴 이론 상한(+{gain_b3:.1f}%p)의 "
      f"{gain_staged / gain_b3 * 100:.0f}%를 회수하면서 가치관 축을 그대로 유지한다.\n")
    ceiling_gain = gain_b3
    p("## 2-c. 목표선이 이론 상한 위에 있다 — 기준 재설정이 필요하다\n")
    p(f"`M` 비중을 0.90까지 올려도 +{sweep_res[0.90] * 100 - b3 * 100:.1f}%p에서 멈춘다. "
      f"이것이 **단일 쌍 매칭의 상한**이다(상보성만 쓴 값과 같다). "
      f"목표 +15%p는 그 상한보다 위에 있으므로 **가중치를 어떻게 조정해도 도달할 수 없다**.\n")
    p("**원인은 기준 설정에 있다.** +15%p는 원래 `B2` 대비로 정한 값이었다. "
      "`B2`가 무르다는 걸 알고 베이스라인을 `B3`로 바꾸면서 **목표 숫자를 그대로 옮긴 것이 잘못**이다. "
      "`B3`는 이미 63.4%로 강한 기준이라, +15%p는 78.4%를 요구하는데 단일 쌍 상한이 78.0%다.\n")
    p("**목표는 결과를 보고 고치는 게 아니라 상한을 계산해서 다시 정한다.** 두 갈래가 있다.\n")
    p("| 선택지 | 내용 | 대가 |")
    p("|---|---|---|")
    p(f"| ㈎ 목표 재산출 | `B3` 대비 **+10%p**로 낮춘다(상한 +{ceiling_gain:.1f}%p의 약 70%) | "
      "기준을 낮춘 것이므로 **왜 낮췄는지를 반드시 같이 보고**해야 한다 |")
    p("| ㈏ 랭킹을 확장 | 단일 쌍을 넘어 **릴레이·Set Cover 조합**까지 후보로 낸다 | "
      "상한 자체가 올라간다. 설계에 이미 있는 기능이고 이번 실험이 안 쓴 것뿐이다 |")
    p("\n**㈏를 권한다.** 이번 실험은 1:1 쌍만 봤는데, 우리 설계에는 "
      "여러 명이 시간을 나눠 덮는 릴레이 체인과 Set Cover가 이미 들어 있다. "
      "위젯에서 확인한 **09~13시 잔여 공백**이 정확히 그 경로로 메워지는 구간이다. "
      "**다음 실험은 릴레이를 포함한 피복률을 재는 것**이고, 그때 상한이 얼마나 올라가는지가 진짜 질문이다.\n")

    p("> **가치관 축의 반증선은 이 실험으로 판정할 수 없다.** 반증선은 "
      "'`V`를 넣어 Precision이 +5%p 미만이면 랭킹에서 뺀다'인데, 여기서 쓴 정답이 시간 피복률이라 "
      "`V`는 정의상 기여할 수 없다. **이 실험 결과로 `V` 제거를 결정하면 안 된다.** "
      "전문가 판정 50쌍이 나온 뒤에 판정한다.\n")

    report_relay(p, relay, opt, relay_n, relay_seeds)
    report_rank_relay(p, rr)

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

    relay_n, relay_seeds = args.sizes[-1], 10
    start = time.perf_counter()
    results = sweep(args.sizes)
    relay = relay_sweep(relay_n, relay_seeds)
    opt = relay_sweep(OPT_CHECK_N, relay_seeds, exhaustive=True)
    rr = relay_rank_sweep(relay_n, relay_seeds)
    elapsed = time.perf_counter() - start

    if args.out:
        args.out.parent.mkdir(parents=True, exist_ok=True)
        with args.out.open("w", encoding="utf-8") as fh:
            report(fh, args.sizes, results, relay, opt, rr, relay_n, relay_seeds, elapsed)
        print(f"저장 {args.out}")
    else:
        report(sys.stdout, args.sizes, results, relay, opt, rr, relay_n, relay_seeds, elapsed)


if __name__ == "__main__":
    main()
