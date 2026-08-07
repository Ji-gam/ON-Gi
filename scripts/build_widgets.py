"""기획서용 위젯을 독립 SVG + PNG로 굽는다.

대화창 위젯은 색·폰트를 호스트 CSS에서 받아쓰므로 그대로 저장하면 검게 나온다.
여기서는 팔레트를 인라인해 어디서 열어도 같게 보이는 파일을 만든다.

사용:
    python scripts/build_widgets.py            # SVG + PNG 모두
    python scripts/build_widgets.py --svg-only # Chrome 없이 SVG만

산출: docs/plan/widgets/*.svg, *.png (PNG는 2배 해상도)
"""

from __future__ import annotations

import argparse
import shutil
import subprocess
import sys
from pathlib import Path

OUT = Path("docs/plan/widgets")

CHROME_CANDIDATES = [
    r"C:\Program Files\Google\Chrome\Application\chrome.exe",
    r"C:\Program Files (x86)\Microsoft\Edge\Application\msedge.exe",
]

# 팔레트 — 라이트 모드 기준(50 채움 / 600 테두리 / 800 제목 / 600 부제)
RAMPS = {
    "gray":   ("#F1EFE8", "#5F5E5A", "#444441", "#5F5E5A"),
    "teal":   ("#E1F5EE", "#0F6E56", "#085041", "#0F6E56"),
    "coral":  ("#FAECE7", "#993C1D", "#712B13", "#993C1D"),
    "purple": ("#EEEDFE", "#534AB7", "#3C3489", "#534AB7"),
    "red":    ("#FCEBEB", "#A32D2D", "#791F1F", "#A32D2D"),
    "amber":  ("#FAEEDA", "#854F0B", "#633806", "#854F0B"),
}


def _style() -> str:
    rules = [
        "text{font-family:'Malgun Gothic','Segoe UI',sans-serif}",
        ".t{font-size:14px;fill:#191919}",
        ".ts{font-size:12px;fill:#5F5E5A}",
        ".th{font-size:14px;font-weight:500;fill:#191919}",
        ".box{fill:#FFFFFF;stroke:#B4B2A9}",
        ".arr{stroke:#888780;fill:none;stroke-width:1.5}",
        ".grid{stroke:#D3D1C7;stroke-width:0.5}",
        # 시간 띠는 인쇄에서 옅게 나와 한 단계 진한 100 스톱을 쓴다
        "rect.seg.c-teal{fill:#9FE1CB}",
        "rect.seg.c-coral{fill:#F5C4B3}",
        "rect.seg.c-gray{fill:#D3D1C7}",
        "rect.seg.c-amber{fill:#FAC775}",
    ]
    for name, (fill, stroke, title, sub) in RAMPS.items():
        c = f".c-{name}"
        rules.append(f"{c}>rect,{c}>circle,rect{c},circle{c}{{fill:{fill};stroke:{stroke}}}")
        rules.append(f"{c}>.th{{fill:{title}}}")
        rules.append(f"{c}>.ts{{fill:{sub}}}")
    return "\n".join(rules)


ARROW_DEF = (
    '<defs><marker id="arrow" viewBox="0 0 10 10" refX="8" refY="5" markerWidth="6" '
    'markerHeight="6" orient="auto-start-reverse"><path d="M2 1L8 5L2 9" fill="none" '
    'stroke="context-stroke" stroke-width="1.5" stroke-linecap="round" '
    'stroke-linejoin="round"/></marker></defs>'
)


def wrap(body: str, height: int, title: str) -> str:
    return (
        f'<svg xmlns="http://www.w3.org/2000/svg" width="680" height="{height}" '
        f'viewBox="0 0 680 {height}" role="img"><title>{title}</title>'
        f"<style>{_style()}</style>{ARROW_DEF}"
        f'<rect x="0" y="0" width="680" height="{height}" fill="#FFFFFF"/>'
        f"{body}</svg>"
    )


def strip(y: int, segments: list[tuple[int, int, str]], grid: bool = True) -> str:
    """48슬롯 시간 띠. segments = [(시작슬롯, 슬롯수, 램프)]"""
    parts = [f'<rect class="box" x="50" y="{y}" width="576" height="24" rx="4" stroke-width="0.5"/>']
    for start, count, ramp in segments:
        parts.append(
            f'<rect class="seg c-{ramp}" x="{50 + 12 * start}" y="{y}" '
            f'width="{12 * count}" height="24" rx="2" stroke-width="0.5"/>'
        )
    if grid:
        for x in (146, 242, 338, 434, 530):
            parts.append(f'<line class="grid" x1="{x}" y1="{y}" x2="{x}" y2="{y + 24}"/>')
    return "".join(parts)


def box(x: int, y: int, w: int, h: int, ramp: str, lines: list[str]) -> str:
    """가운데 정렬 박스. lines[0]은 제목(th), 나머지는 부제(ts)."""
    cx = x + w // 2
    slot = h // (len(lines) + 1)
    parts = [f'<g class="c-{ramp}"><rect x="{x}" y="{y}" width="{w}" height="{h}" rx="8" stroke-width="0.5"/>']
    for i, text in enumerate(lines):
        cls = "th" if i == 0 else "ts"
        cy = y + slot * (i + 1)
        parts.append(
            f'<text class="{cls}" x="{cx}" y="{cy}" text-anchor="middle" '
            f'dominant-baseline="central">{text}</text>'
        )
    return "".join(parts) + "</g>"


def down(x: int, y1: int, y2: int) -> str:
    return f'<line class="arr" x1="{x}" y1="{y1}" x2="{x}" y2="{y2}" marker-end="url(#arrow)"/>'


def label(x: int, y: int, text: str) -> str:
    return f'<text class="th" x="{x}" y="{y}" dominant-baseline="central">{text}</text>'


def legend(y: int, items: list[tuple[int, str, str]]) -> str:
    parts = []
    for x, ramp, text in items:
        parts.append(f'<circle class="c-{ramp}" cx="{x}" cy="{y}" r="5" stroke-width="0.5"/>')
        parts.append(f'<text class="ts" x="{x + 12}" y="{y}" dominant-baseline="central">{text}</text>')
    return "".join(parts)


# ── 위젯 1 · 매칭 전 과정 (기술 스택 + 태그 + 양육관) ─────────────────────
def widget_matching() -> tuple[str, int, str]:
    b = [
        box(50, 40, 580, 44, "gray", ["근무표 PDF·엑셀 → PyMuPDF·LLM 파싱 → 48슬롯 비트마스크"]),
        label(50, 104, "간호사 A · 3교대 야간조 22:00~06:00 · 근무 후 수면 07~13시"),
        strip(114, [(0, 12, "teal"), (44, 4, "teal"), (14, 12, "gray")]),
        label(50, 158, "소방관 B · 2교대 주간 09:00~21:00 (12시간) · 수면 23~07시"),
        strip(168, [(18, 24, "coral"), (0, 14, "gray"), (46, 2, "gray")]),
        label(50, 212, "BIT(48) AND → A가 8시간 · B가 8시간(밤샘) · 남는 4시간은 릴레이"),
        strip(222, [(0, 12, "coral"), (44, 4, "coral"), (26, 16, "teal"), (18, 8, "amber")],
              grid=False),
    ]
    for x, t in ((50, "00"), (146, "04"), (242, "08"), (338, "12"), (434, "16"), (530, "20"), (626, "24")):
        b.append(f'<text class="ts" x="{x}" y="262" text-anchor="middle" dominant-baseline="central">{t}</text>')

    b.append(label(50, 292, "Stage 1 하드 필터 · H3 반경 1km + 필수 태그 10개 (Set Cover)"))
    for i, t in enumerate(["알레르기 대응", "투약 관리", "응급처치 이수", "비흡연 가정"]):
        b.append(box(50 + i * 146, 302, 138, 28, "red", [t]).replace('class="th"', 'class="ts"'))
    for i, t in enumerate(["영아 돌봄", "밤샘 가능", "차량 보유", "다자녀", "집 제공", "펫 없음"]):
        b.append(box(50 + i * 97, 336, 90, 28, "gray", [t]).replace('class="th"', 'class="ts"'))

    b.append(label(50, 394, "Stage 2 소프트 점수 · 바움린드 2축을 8문항으로 → 코사인 0.87"))
    for i, t in enumerate(["수용", "반응", "애정", "대화", "규칙", "일관성", "훈육", "자율"]):
        b.append(box(50 + i * 72, 404, 68, 28, "purple", [t]).replace('class="th"', 'class="ts"'))
    b.append('<text class="ts" x="156" y="450" text-anchor="middle" dominant-baseline="central">온기(반응성) 4문항</text>')
    b.append('<text class="ts" x="480" y="450" text-anchor="middle" dominant-baseline="central">통제(요구성) 4문항</text>')

    b.append(down(340, 462, 476))
    b.append(box(50, 482, 580, 64, "purple", [
        "매칭 확정 + 근거 문장 자동 생성",
        "1km 안 · 낮 8시간은 A가, 밤 8시간은 B가 · 알레르기 대응 · 양육관 근접",
    ]))
    b.append(legend(568, [
        (62, "teal", "간호사 A"), (152, "coral", "소방관 B"), (242, "gray", "수면"),
        (300, "amber", "릴레이 필요"), (400, "red", "완화 불가 태그"), (524, "purple", "가치관 축"),
    ]))
    return "".join(b), 588, "품앗이온 매칭 전 과정 — 근무표 파싱부터 가치관 유사도까지"


# ── 위젯 2 · H1-a 개정 이력 ───────────────────────────────────────────────
def widget_hypothesis() -> tuple[str, int, str]:
    b = [
        box(50, 40, 580, 56, "gray", [
            "H1-a (v1) — 두 주장이 &#39;그리고&#39;로 묶여 있었다",
            "㈎ 1km 안 밀도가 충분하다 · ㈏ 공공 돌봄에 대기가 쌓여 있다",
        ]),
        down(190, 96, 110), down(490, 96, 110),
        box(50, 116, 280, 76, "amber", ["㈎ 밀도 — 미해결", "어린이집 좌표·현원 필요", "승인 대기 중"]),
        box(350, 116, 280, 76, "teal", ["㈏ 수요 — 닫힘", "대기 42번 중 41번 증가", "가용 18,722명 있는데도"]),
        down(490, 192, 206),
        box(50, 212, 580, 56, "purple", [
            "v2 — 반증 가능한 문장으로 고쳐 썼다",
            "&#39;대기가 있다&#39;는 통계상 항상 참 · &#39;인력 부족이 아니다&#39;는 틀릴 수 있다",
        ]),
        down(340, 268, 282),
        box(50, 288, 580, 64, "purple", [
            "H1-a (v3) — 시장 명제에서 기술 명제로",
            "공공데이터는 입력 조건, 검증 대상은 세 축 매칭 대 베이스라인",
        ]),
        legend(384, [
            (62, "teal", "닫힘"), (140, "amber", "진행 중"),
            (232, "purple", "가설 문장"), (330, "gray", "이전 버전"),
        ]),
    ]
    return "".join(b), 406, "H1-a 개정 이력 — v1에서 v3까지"


# ── 위젯 3 · 스택과 검증 근거의 대응 ──────────────────────────────────────
def widget_stack() -> tuple[str, int, str]:
    rows = [
        ("공공 API 수집 스크립트", "정부 통계 — 이미 닫힘", "teal"),
        ("H3 반경 인덱싱", "밀도 데이터를 입력으로", "purple"),
        ("48슬롯 비트마스크 상보성", "단위 테스트 · 반례", "purple"),
        ("문장 임베딩 코사인 유사도", "전문가 판정 50쌍", "purple"),
        ("가중합 랭킹 S", "베이스라인 B2 대비", "purple"),
        ("근무표 파싱 (PyMuPDF · LLM)", "사용자 확정본 필요", "amber"),
    ]
    b = []
    for i, (left, right, ramp) in enumerate(rows):
        y = 40 + i * 58
        b.append(box(50, y, 300, 44, "gray", [left]))
        b.append(f'<line class="arr" x1="352" y1="{y + 22}" x2="368" y2="{y + 22}" marker-end="url(#arrow)"/>')
        b.append(box(372, y, 258, 44, ramp, [right]))
    b.append(legend(396, [
        (62, "teal", "닫힘"), (140, "purple", "사용자 없이 지금 가능"), (308, "amber", "파일럿 필요"),
    ]))
    return "".join(b), 420, "기술 스택과 검증 근거의 대응"


# ── 위젯 4 · 임계 밀도 곡선 + 지역 대입 ──────────────────────────────────
DENSITY = [(10, 40.7), (20, 60.2), (30, 71.0), (50, 79.0), (80, 83.7), (120, 83.9)]
REGIONS = [("강남구", "0.40%"), ("성동구", "0.49%"), ("동작구", "0.51%"), ("마포구", "0.55%")]
BASE_Y, SCALE = 280, 2.2   # 0% 기준선과 1%p당 픽셀


def widget_density() -> tuple[str, int, str]:
    b = []
    for pct, text in ((83.9, "천장 84% — 더 모아도 안 오른다"), (60.0, "60% 성공 기준")):
        y = round(BASE_Y - pct * SCALE)
        b.append(f'<line x1="90" y1="{y}" x2="630" y2="{y}" stroke="#888780" '
                 f'stroke-width="0.5" stroke-dasharray="4 4"/>')
        b.append(f'<text class="ts" x="100" y="{y - 9}" dominant-baseline="central">{text}</text>')

    for i, (n, pct) in enumerate(DENSITY):
        x = 100 + i * 90
        h = round(pct * SCALE)
        ramp = "teal" if pct >= 60 else "gray"
        b.append(f'<g class="c-{ramp}"><rect x="{x}" y="{BASE_Y - h}" width="60" height="{h}" '
                 f'rx="4" stroke-width="0.5"/></g>')
        b.append(f'<text class="ts" x="{x + 30}" y="{BASE_Y - h - 9}" text-anchor="middle" '
                 f'dominant-baseline="central">{pct}%</text>')
        b.append(f'<text class="ts" x="{x + 30}" y="296" text-anchor="middle" '
                 f'dominant-baseline="central">{n}</text>')

    b.append(f'<line x1="90" y1="{BASE_Y}" x2="630" y2="{BASE_Y}" stroke="#888780" stroke-width="0.5"/>')
    b.append('<text class="ts" x="355" y="316" text-anchor="middle" '
             'dominant-baseline="central">한 지역에 모인 가구 수</text>')

    b.append(box(50, 340, 280, 64, "teal", ["임계 밀도 20가구", "이 규모부터 60%를 넘는다"]))
    b.append(box(350, 340, 280, 64, "gray", ["천장 84%의 정체", "주간 고정끼리는 서로 못 채운다"]))
    b.append(label(50, 428, "실제 지역에 대입 — 이용가구 중 몇 %를 모으면 되는가"))
    for i, (name, ratio) in enumerate(REGIONS):
        b.append(box(50 + i * 146, 440, 138, 44, "purple", [name, ratio]))
    b.append(legend(504, [
        (62, "teal", "기준 통과"), (164, "gray", "기준 미달"),
        (266, "purple", "공공데이터 실측 이용가구 기준"),
    ]))
    return "".join(b), 518, "임계 밀도 곡선과 지역별 필요 모집 비율"


# ── 위젯 5 · 지표를 바꾸자 순위가 뒤집혔다 (실측) ───────────────────────
OLD_RANK = [
    ("1", "M 상보성만", "78.0%", "amber"),
    ("2", "S 콜드스타트", "71.5%", "gray"),
    ("3", "B3 한 방향 피복", "63.4%", "gray"),
    ("4", "S 전체 가중치", "54.8%", "gray"),
    ("5", "B0 무작위", "16.6%", "gray"),
    ("6", "B2 단순 시간 겹침", "0.5%", "gray"),
    ("—", "조합 인지 선정", "측정 불가", "teal"),
]
NEW_RANK = [
    ("1", "조합 인지 선정", "78.6%", "teal"),
    ("2", "S 전체 가중치", "76.8%", "gray"),
    ("3", "B3 한 방향 피복", "70.2%", "gray"),
    ("4", "B0 무작위", "69.8%", "gray"),
    ("5", "S 콜드스타트", "69.7%", "gray"),
    ("6", "M 상보성만", "67.1%", "amber"),
    ("7", "B2 단순 시간 겹침", "25.4%", "gray"),
]


def _rank_row(x: int, y: int, rank: str, name: str, val: str, ramp: str) -> str:
    cls = "th" if ramp != "gray" else "ts"
    cy = y + 18
    return (f'<g class="c-{ramp}"><rect x="{x}" y="{y}" width="250" height="36" rx="4" '
            f'stroke-width="0.5"/>'
            f'<text class="{cls}" x="{x + 16}" y="{cy}" dominant-baseline="central">{rank}</text>'
            f'<text class="{cls}" x="{x + 40}" y="{cy}" dominant-baseline="central">{name}</text>'
            f'<text class="{cls}" x="{x + 234}" y="{cy}" text-anchor="end" '
            f'dominant-baseline="central">{val}</text></g>')


def widget_metric_change() -> tuple[str, int, str]:
    b = [
        '<text class="th" x="175" y="56" text-anchor="middle" '
        'dominant-baseline="central">Precision@5 · 옛 지표</text>',
        '<text class="th" x="505" y="56" text-anchor="middle" '
        'dominant-baseline="central">피복률@5 · 새 지표</text>',
    ]
    for i, row in enumerate(OLD_RANK):
        b.append(_rank_row(50, 80 + i * 44, *row))
    for i, row in enumerate(NEW_RANK):
        b.append(_rank_row(380, 80 + i * 44, *row))

    b.append('<path d="M304 98 L340 98 L340 318 L376 318" fill="none" stroke="#BA7517" '
             'stroke-width="1.5" marker-end="url(#arrow)"/>')
    b.append('<path d="M304 362 L352 362 L352 98 L376 98" fill="none" stroke="#1D9E75" '
             'stroke-width="1.5" marker-end="url(#arrow)"/>')
    b.append(box(50, 404, 580, 76, "red", [
        "같은 방법이 1위에서 6위로 — 지표가 결론을 바꾼다",
        "M은 상위 5명이 서로 중복돼 조합하면 못 덮는데, 옛 지표는 그걸 못 본다",
        "조합 인지 선정은 순위를 안 내놓아 옛 지표로는 측정 자체가 안 된다",
    ]))
    return "".join(b), 520, "지표를 바꾸자 순위가 뒤집혔다 — 실측값 비교"

# ── 위젯 6 · 피복률@5 대 호혜 충족률 ─────────────────────────────────────
TWO_AXIS = [
    ("무작위", 69.8, 49.2, "gray"),
    ("단순 시간 겹침", 25.4, 1.2, "red"),
    ("한 방향 피복", 70.2, 73.1, "gray"),
    ("S 전체 가중치", 76.8, 81.0, "gray"),
    ("S 콜드스타트", 69.7, 94.0, "gray"),
    ("M 상보성만", 67.1, 97.1, "gray"),
    ("조합 인지 선정", 78.6, 99.9, "teal"),
]


def widget_two_axis() -> tuple[str, int, str]:
    b = [
        '<text class="th" x="248" y="48" text-anchor="middle" '
        'dominant-baseline="central">피복률@5</text>',
        '<text class="th" x="490" y="48" text-anchor="middle" '
        'dominant-baseline="central">호혜 충족률</text>',
    ]
    for i, (name, cov, rec, ramp) in enumerate(TWO_AXIS):
        y = 62 + i * 38
        cy = y + 12
        cls = "th" if ramp == "teal" else "ts"
        b.append(f'<text class="{cls}" x="150" y="{cy}" text-anchor="end" '
                 f'dominant-baseline="central">{name}</text>')
        for x0, val in ((158, cov), (400, rec)):
            w = max(2, round(val * 1.8))
            b.append(f'<g class="c-{ramp}"><rect x="{x0}" y="{y}" width="{w}" height="24" '
                     f'rx="2" stroke-width="0.5"/></g>')
            b.append(f'<text class="ts" x="{x0 + w + 8}" y="{cy}" '
                     f'dominant-baseline="central">{val}%</text>')

    b.append(box(50, 338, 280, 64, "gray", ["무제약 상한 88.7%", "호혜를 안 따지고 덮기만 할 때"]))
    b.append(box(350, 338, 280, 64, "teal", ["호혜 제약 상한 78.6%", "조합 인지가 여기에 도달했다"]))
    b.append(box(50, 414, 580, 64, "purple", [
        "차이 10.1%p — 호혜를 요구하는 대가",
        "한쪽만 받는 관계를 허용하면 더 덮을 수 있지만 그 관계는 오래 못 간다",
    ]))
    b.append(legend(498, [
        (62, "teal", "우리 방식"), (164, "gray", "베이스라인·변형"),
        (304, "red", "흔히 쓰는 잘못된 방식"),
    ]))
    return "".join(b), 520, "피복률@5와 호혜 충족률 비교, 두 개의 상한"

# ── 위젯 7 · 실험 전체 요약 (입력 → 판정) ───────────────────────────────
def widget_experiment() -> tuple[str, int, str]:
    b = [
        label(50, 40, "① 무엇으로 실험했나"),
        box(50, 52, 180, 76, "teal", [
            "공공데이터 실측", "시군구별 이용가구 수", "강남 5,033가구 등"]),
        box(250, 52, 180, 76, "gray", [
            "합성 근무 패턴", "실제 교대 규칙 11종", "간호·소방·제조·물류"]),
        box(450, 52, 180, 76, "gray", [
            "규모와 반복", "N=10~120 · 시드 30", "쌍 전수 계산"]),

        label(50, 152, "② 무엇을 어떻게 쟀나"),
        box(50, 164, 280, 76, "gray", [
            "비교 대상 7가지", "무작위 · 단순 겹침 · 한 방향 피복",
            "S 3종 + 조합 인지 선정"]),
        box(350, 164, 280, 76, "purple", [
            "정답 정의", "양방향 피복률 50% 이상",
            "랭킹 점수와 독립 — 동어반복 차단"]),

        label(50, 264, "③ 나온 수치"),
        box(50, 276, 133, 76, "teal", ["20가구", "임계 밀도", "보유율 60.2%"]),
        box(199, 276, 133, 76, "teal", ["78.6%", "피복률@5", "B3 대비 +8.5%p"]),
        box(348, 276, 133, 76, "teal", ["99.9%", "호혜 충족률", "목표 95% 이상"]),
        box(497, 276, 133, 76, "teal", ["74.8%", "릴레이 완전피복", "1:1은 0.0%"]),

        label(50, 376, "④ 판정"),
        box(50, 388, 133, 76, "teal", ["통과", "임계 밀도", "20가구 확인"]),
        box(199, 388, 133, 76, "teal", ["통과", "피복률 상한 도달", "+8.5%p"]),
        box(348, 388, 133, 76, "teal", ["통과", "호혜 충족률", "99.9%"]),
        box(497, 388, 133, 76, "amber", ["미달", "야간 완전피복", "29.8% / 30%"]),

        box(50, 488, 580, 64, "gray", [
            "판정할 수 없는 것 — 가치관 축의 효용",
            "만족도 정답이 없다. 전문가 판정 50쌍이 나온 뒤에 판정한다"]),
    ]
    return "".join(b), 592, "H1-a v3 검증 실험 전체 — 입력부터 판정까지"

WIDGETS = {
    "01-matching-pipeline": widget_matching,
    "02-hypothesis-revision": widget_hypothesis,
    "03-stack-validation": widget_stack,
    "04-density-curve": widget_density,
    "05-metric-change": widget_metric_change,
    "06-coverage-reciprocity": widget_two_axis,
    "07-experiment-summary": widget_experiment,
}


def find_chrome() -> str | None:
    for path in CHROME_CANDIDATES:
        if Path(path).exists():
            return path
    return shutil.which("chrome") or shutil.which("msedge")


def to_png(chrome: str, svg: Path, png: Path, height: int) -> bool:
    cmd = [
        chrome, "--headless", "--disable-gpu", "--hide-scrollbars",
        f"--screenshot={png.resolve()}",
        f"--window-size=680,{height}",
        "--force-device-scale-factor=2",
        svg.resolve().as_uri(),
    ]
    result = subprocess.run(cmd, capture_output=True, timeout=120)
    return png.exists() and result.returncode == 0


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--svg-only", action="store_true")
    args = ap.parse_args()

    OUT.mkdir(parents=True, exist_ok=True)
    chrome = None if args.svg_only else find_chrome()
    if not args.svg_only and not chrome:
        sys.exit("Chrome·Edge 를 찾지 못했습니다. --svg-only 로 SVG만 만드세요.")

    for name, builder in WIDGETS.items():
        body, height, title = builder()
        svg = OUT / f"{name}.svg"
        svg.write_text(wrap(body, height, title), encoding="utf-8")
        print(f"SVG  {svg}  (680x{height})")

        if chrome:
            png = OUT / f"{name}.png"
            if to_png(chrome, svg, png, height):
                print(f"PNG  {png}  ({png.stat().st_size // 1024} KB)")
            else:
                print(f"  ! {name}: PNG 변환 실패 — SVG 를 직접 쓰세요")


if __name__ == "__main__":
    main()
