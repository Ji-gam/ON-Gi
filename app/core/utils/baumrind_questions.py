"""REQ-F-ACC-07 바움린드(Baumrind) 양육유형 이론 기반 8문항. 요구사항정의서에 실제 문항
텍스트가 없어(`docs/tasks/T-ACC-3.md` 가정 참고) 이론(온기=반응성, 통제=요구성)에 근거해 직접
작성했다 - 실제 설문 검수 시 이 파일만 교체하면 된다.

응답은 1~5점 5점 척도. 앞 4문항은 온기(WARMTH), 뒤 4문항은 통제(CONTROL) 차원이다.
"""

from enum import StrEnum
from typing import NamedTuple


class ParentingDimension(StrEnum):
    WARMTH = "WARMTH"
    CONTROL = "CONTROL"


class BaumrindQuestion(NamedTuple):
    text: str
    dimension: ParentingDimension


BAUMRIND_QUESTIONS: tuple[BaumrindQuestion, ...] = (
    BaumrindQuestion("아이가 속상해할 때 먼저 다가가 마음을 물어봐 준다.", ParentingDimension.WARMTH),
    BaumrindQuestion("아이의 생각이나 의견을 존중해 대화에 반영한다.", ParentingDimension.WARMTH),
    BaumrindQuestion("아이에게 애정 표현(칭찬, 스킨십 등)을 자주 한다.", ParentingDimension.WARMTH),
    BaumrindQuestion("아이가 실수했을 때 다그치기보다 이유를 들어준다.", ParentingDimension.WARMTH),
    BaumrindQuestion("정해진 규칙(취침 시간, 미디어 사용 등)을 예외 없이 지키게 한다.", ParentingDimension.CONTROL),
    BaumrindQuestion("아이의 하루 일정과 행동을 세세히 파악하고 관리한다.", ParentingDimension.CONTROL),
    BaumrindQuestion("잘못된 행동에는 분명한 기준으로 제지하거나 훈육한다.", ParentingDimension.CONTROL),
    BaumrindQuestion("아이 스스로 결정하게 두기보다 부모가 방향을 정해준다.", ParentingDimension.CONTROL),
)

_MIDPOINT = 3.0


class ParentingTypeLabel(StrEnum):
    AUTHORITATIVE = "AUTHORITATIVE"  # 권위있는(고온기·고통제)
    AUTHORITARIAN = "AUTHORITARIAN"  # 권위주의적(저온기·고통제)
    PERMISSIVE = "PERMISSIVE"  # 허용적(고온기·저통제)
    NEGLECTFUL = "NEGLECTFUL"  # 방임적(저온기·저통제)


def classify_type(warmth_score: float, control_score: float) -> ParentingTypeLabel:
    high_warmth = warmth_score >= _MIDPOINT
    high_control = control_score >= _MIDPOINT
    if high_warmth and high_control:
        return ParentingTypeLabel.AUTHORITATIVE
    if not high_warmth and high_control:
        return ParentingTypeLabel.AUTHORITARIAN
    if high_warmth and not high_control:
        return ParentingTypeLabel.PERMISSIVE
    return ParentingTypeLabel.NEGLECTFUL
