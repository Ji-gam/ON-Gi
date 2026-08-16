"""REQ-F-MAT-01/02/03/05/12. 매칭 후보 탐색 - 거리·태그 하드필터를 통과한 후보를
가치관 유사도(35%)+상보 스코어(35%)+거리/개월수유사도/신뢰점수(각 10%)로 정렬한다.

이 서비스는 신규 테이블을 만들지 않고 T-ACC-2/3, T-SCH-1의 기존 데이터를 읽기만 한다.
"""

import math
from dataclasses import dataclass
from datetime import date

import h3
from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.core.utils.guardian_tags import MANDATORY_GUARDIAN_TAG_CODES
from app.core.utils.matching_weights import (
    MAX_AGE_DIFF_MONTHS,
    MAX_DISTANCE_M,
    WEIGHT_AGE_SIMILARITY,
    WEIGHT_COMPLEMENTARY,
    WEIGHT_DISTANCE,
    WEIGHT_TRUST,
    WEIGHT_VALUES_SIMILARITY,
)
from app.core.utils.recommendation_reason import build_recommendation_reason
from app.core.utils.schedule_slots import FULL_AVAILABLE_MASK, SLOT_COUNT, complementary_slot_counts
from app.models.children import Child
from app.models.hypothesis_event import HypothesisEventType
from app.repositories.care_evaluation_repository import CareEvaluationRepository
from app.repositories.child_repository import ChildRepository
from app.repositories.guardian_profile_repository import GuardianProfileRepository
from app.repositories.parenting_values_repository import ParentingValuesRepository
from app.repositories.work_schedule_repository import WorkScheduleRepository
from app.services.hypothesis_event_service import HypothesisEventService
from app.services.trust_score_service import TrustScoreService
from auth_kit.models import User

_MAX_VALUES_DISTANCE = math.sqrt(4**2 + 4**2)  # warmth/control 각 1~5점 범위의 최대 유클리드 거리


@dataclass
class MatchCandidate:
    user_id: int
    nickname: str
    total_score: float
    values_similarity: float
    complementary_score: float
    distance_m: float
    age_similarity: float
    trust_score: float
    average_rating: float | None
    top_tags: list[str]
    reason: str


def _clamp(value: float, lo: float = 0.0, hi: float = 1.0) -> float:
    return max(lo, min(hi, value))


def _haversine_m(h3_a: str, h3_b: str) -> float:
    lat1, lng1 = h3.cell_to_latlng(h3_a)
    lat2, lng2 = h3.cell_to_latlng(h3_b)
    r = 6371000.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    d_phi = math.radians(lat2 - lat1)
    d_lambda = math.radians(lng2 - lng1)
    a = math.sin(d_phi / 2) ** 2 + math.cos(phi1) * math.cos(phi2) * math.sin(d_lambda / 2) ** 2
    return 2 * r * math.asin(math.sqrt(a))


def _avg_months_old(children: list[Child]) -> float | None:
    if not children:
        return None
    return sum(c.months_old for c in children) / len(children)


def _required_tags_for(children: list[Child]) -> set[str]:
    required = {"FIRST_AID_CERTIFIED", "NON_SMOKING_HOUSEHOLD"}
    if any(c.sensitive and c.sensitive.allergies for c in children):
        required.add("ALLERGY_RESPONSE")
    if any(c.sensitive and c.sensitive.medications for c in children):
        required.add("MEDICATION_MANAGEMENT")
    return required & MANDATORY_GUARDIAN_TAG_CODES


class MatchingService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.guardian_repo = GuardianProfileRepository(session)
        self.values_repo = ParentingValuesRepository(session)
        self.schedule_repo = WorkScheduleRepository(session)
        self.child_repo = ChildRepository(session)
        self.evaluation_repo = CareEvaluationRepository(session)
        self.trust_score_service = TrustScoreService(session)
        self.event_service = HypothesisEventService(session)

    async def find_candidates(self, user: User, for_date: date) -> list[MatchCandidate]:
        own_profile = await self.guardian_repo.get(user.id)
        if own_profile is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "먼저 보호자 프로필을 등록하세요.")

        own_children = await self.child_repo.list_by_user(user.id)
        own_values = await self.values_repo.get(user.id)
        own_schedule = await self.schedule_repo.get(user.id, for_date)
        own_mask = own_schedule.slot_bitmask if own_schedule else FULL_AVAILABLE_MASK
        own_required_tags = _required_tags_for(own_children)
        own_avg_months = _avg_months_old(own_children)

        candidates: list[MatchCandidate] = []
        for profile in await self.guardian_repo.list_all_except(user.id):
            candidate_user = await self.session.get(User, profile.user_id)
            if candidate_user is None or not candidate_user.is_active or candidate_user.is_sanctioned:
                continue

            distance_m = _haversine_m(own_profile.residence_h3, profile.residence_h3)
            if distance_m > MAX_DISTANCE_M:
                continue

            candidate_tags = set(await self.guardian_repo.list_tags(profile.user_id))
            if not own_required_tags.issubset(candidate_tags):
                continue

            candidate_values = await self.values_repo.get(profile.user_id)
            if own_values is None or candidate_values is None:
                continue
            values_distance = math.sqrt(
                (own_values.warmth_score - candidate_values.warmth_score) ** 2
                + (own_values.control_score - candidate_values.control_score) ** 2
            )
            values_similarity = _clamp(1 - values_distance / _MAX_VALUES_DISTANCE)

            candidate_schedule = await self.schedule_repo.get(profile.user_id, for_date)
            candidate_mask = candidate_schedule.slot_bitmask if candidate_schedule else FULL_AVAILABLE_MASK
            a_needs_b, b_needs_a = complementary_slot_counts(own_mask, candidate_mask)
            complementary_score = _clamp((a_needs_b + b_needs_a) / SLOT_COUNT)

            candidate_children = await self.child_repo.list_by_user(profile.user_id)
            candidate_avg_months = _avg_months_old(candidate_children)
            if own_avg_months is None or candidate_avg_months is None:
                age_similarity = 0.0
            else:
                age_similarity = _clamp(1 - abs(own_avg_months - candidate_avg_months) / MAX_AGE_DIFF_MONTHS)

            distance_score = _clamp(1 - distance_m / MAX_DISTANCE_M)
            trust_score = await self.trust_score_service.calculate_score(candidate_user.id)

            total_score = (
                WEIGHT_VALUES_SIMILARITY * values_similarity
                + WEIGHT_COMPLEMENTARY * complementary_score
                + WEIGHT_DISTANCE * distance_score
                + WEIGHT_AGE_SIMILARITY * age_similarity
                + WEIGHT_TRUST * trust_score
            )

            ratings = await self.evaluation_repo.list_ratings_for_evaluatee(candidate_user.id)
            average_rating = sum(ratings) / len(ratings) if ratings else None
            top_tags = await self.evaluation_repo.top_tags_for_evaluatee(candidate_user.id)
            reason = build_recommendation_reason(
                distance_m=distance_m,
                complementary_score=complementary_score,
                values_similarity=values_similarity,
                trust_score=trust_score,
            )

            candidates.append(
                MatchCandidate(
                    user_id=candidate_user.id,
                    nickname=candidate_user.nickname,
                    total_score=total_score,
                    values_similarity=values_similarity,
                    complementary_score=complementary_score,
                    distance_m=distance_m,
                    age_similarity=age_similarity,
                    trust_score=trust_score,
                    average_rating=average_rating,
                    top_tags=top_tags,
                    reason=reason,
                )
            )

        candidates.sort(key=lambda c: c.total_score, reverse=True)

        for candidate in candidates:
            self.event_service.log(
                HypothesisEventType.CANDIDATE_EXPOSURE,
                user.id,
                candidate.user_id,
                payload={"total_score": candidate.total_score, "for_date": for_date.isoformat()},
            )
        if candidates:
            await self.session.commit()

        return candidates
