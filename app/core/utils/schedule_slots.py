"""REQ-F-SCH-03/06. 근무 일정을 30분 단위 48슬롯 비트마스크로 변환하는 순수 함수 모음.

비트 의미: 1=돌봄 가능, 0=근무 중(불가). slot idx 0=00:00-00:30 ... idx 47=23:30-24:00.
DB/ORM에 의존하지 않아 SCH(등록)와 MAT(상보 시간 계산) 양쪽에서 재사용한다.
"""

from enum import StrEnum

SLOT_COUNT = 48
FULL_AVAILABLE_MASK = (1 << SLOT_COUNT) - 1


class ShiftTemplate(StrEnum):
    DAY = "DAY"  # 07:00-15:00
    EVENING = "EVENING"  # 15:00-23:00
    NIGHT = "NIGHT"  # 23:00-07:00(익일)
    OFF = "OFF"


def _range_mask(start_idx: int, end_idx: int) -> int:
    """[start_idx, end_idx) 슬롯을 0(불가)으로 만드는 마스크. 나머지는 1(가용)."""
    unavailable = ((1 << (end_idx - start_idx)) - 1) << start_idx
    return FULL_AVAILABLE_MASK & ~unavailable


def template_masks(template: ShiftTemplate) -> tuple[int, int]:
    """(당일 마스크, 익일 마스크) 반환. 자정을 넘기지 않는 템플릿은 익일 마스크가 전부 가용."""
    if template == ShiftTemplate.DAY:
        return _range_mask(14, 30), FULL_AVAILABLE_MASK
    if template == ShiftTemplate.EVENING:
        return _range_mask(30, 46), FULL_AVAILABLE_MASK
    if template == ShiftTemplate.NIGHT:
        return _range_mask(46, 48), _range_mask(0, 14)
    return FULL_AVAILABLE_MASK, FULL_AVAILABLE_MASK


def complementary_slot_counts(mask_a: int, mask_b: int) -> tuple[int, int]:
    """REQ-F-MAT-01. (A가 근무라 B가 대신 봐줄 수 있는 슬롯 수, 그 반대) 반환."""
    a_needs_b = (~mask_a) & mask_b & FULL_AVAILABLE_MASK
    b_needs_a = (~mask_b) & mask_a & FULL_AVAILABLE_MASK
    return a_needs_b.bit_count(), b_needs_a.bit_count()
