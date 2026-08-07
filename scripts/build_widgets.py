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
        label(50, 104, "간호사 A · 주간조 07:00~15:00"),
        strip(114, [(0, 12, "gray"), (46, 2, "gray"), (14, 16, "teal")]),
        label(50, 158, "소방관 B · 저녁조 15:00~23:00"),
        strip(168, [(0, 14, "gray"), (30, 16, "coral")]),
        label(50, 212, "서로 맡아줄 수 있는 구간 · BIT(48) AND 연산 → 각 16슬롯 8시간"),
        strip(222, [(14, 16, "coral"), (30, 16, "teal")], grid=False),
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
        "1km 안 · 근무가 정확히 엇갈리고 · 알레르기 대응이 되며 · 양육관이 가깝다",
    ]))
    b.append(legend(568, [
        (62, "teal", "간호사 A"), (152, "coral", "소방관 B"), (242, "gray", "수면·선택 태그"),
        (372, "red", "완화 불가 태그"), (502, "purple", "가치관 축"),
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


WIDGETS = {
    "01-matching-pipeline": widget_matching,
    "02-hypothesis-revision": widget_hypothesis,
    "03-stack-validation": widget_stack,
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
