"""REQ-F-TRS-01/02/03/04. 신뢰 등급 상태머신 L1(매칭)→L2(공동육아 진행 중)→L3(단독 위탁 해금).
승급은 시스템이 규칙 기반으로 자동 판정하고, 강등은 운영자만 사유를 남기고 수동으로 수행한다
(신고 도메인 미구현, docs/tasks/T-TRS-2.md 가정 §5).
"""

from datetime import date

from fastapi import HTTPException, status
from sqlalchemy.ext.asyncio import AsyncSession

from app.models.hypothesis_event import HypothesisEventType
from app.models.joint_care_session import JointCareSession, JointCareSessionStatus
from app.models.notification import NotificationType
from app.models.trust_level import TrustLevel, TrustLevelHistory, TrustRelationship
from app.models.trust_settings import MIN_REQUIRED_JOINT_COUNT, TrustSettings
from app.repositories.joint_care_session_repository import JointCareSessionRepository
from app.repositories.trust_relationship_repository import TrustRelationshipRepository
from app.repositories.trust_settings_repository import TrustSettingsRepository
from app.services.hypothesis_event_service import HypothesisEventService
from app.services.notification_service import NotificationService
from auth_kit.models import User

SOLO_REQUEST_BLOCKED_MESSAGE = "단독 위탁 요청은 상대와의 신뢰 등급이 L3일 때만 생성할 수 있습니다."


class TrustLevelService:
    def __init__(self, session: AsyncSession):
        self.session = session
        self.relationship_repo = TrustRelationshipRepository(session)
        self.joint_repo = JointCareSessionRepository(session)
        self.settings_repo = TrustSettingsRepository(session)
        self.event_service = HypothesisEventService(session)
        self.notification_service = NotificationService(session)

    def _notify_transition(self, user_a_id: int, user_b_id: int, new_level: TrustLevel) -> None:
        message = f"신뢰 등급이 {new_level.value}(으)로 변경됐어요."
        for user_id in (user_a_id, user_b_id):
            self.notification_service.notify(
                user_id, NotificationType.TRUST_LEVEL_TRANSITION, message, payload={"new_level": new_level.value}
            )

    async def get_relationship(self, user_a_id: int, user_b_id: int) -> TrustRelationship | None:
        return await self.relationship_repo.get(user_a_id, user_b_id)

    async def require_l3(self, requester_id: int, provider_id: int) -> None:
        """단독 위탁 요청(`is_solo=True`)에만 적용되는 게이트(REQ-F-TRS-04). 일반 돌봄
        요청(재요청 포함, REQ-F-MAT-09)은 이 게이트를 통과하지 않는다."""
        relationship = await self.relationship_repo.get(requester_id, provider_id)
        if relationship is None or relationship.level != TrustLevel.L3:
            raise HTTPException(status.HTTP_403_FORBIDDEN, SOLO_REQUEST_BLOCKED_MESSAGE)

    async def grant_l1(self, user_a_id: int, user_b_id: int) -> TrustRelationship:
        relationship = await self.relationship_repo.get(user_a_id, user_b_id)
        if relationship is not None:
            return relationship
        low, high = (user_a_id, user_b_id) if user_a_id < user_b_id else (user_b_id, user_a_id)
        relationship = TrustRelationship(user_a_id=low, user_b_id=high, level=TrustLevel.L1)
        self.relationship_repo.add(relationship)
        self.event_service.log(
            HypothesisEventType.TRUST_LEVEL_TRANSITION,
            user_a_id,
            user_b_id,
            payload={"previous_level": None, "new_level": TrustLevel.L1.value},
        )
        self._notify_transition(user_a_id, user_b_id, TrustLevel.L1)
        await self.session.commit()
        await self.session.refresh(relationship)
        return relationship

    async def _required_count(self, relationship: TrustRelationship) -> int:
        settings_a = await self.settings_repo.get_or_create(relationship.user_a_id)
        settings_b = await self.settings_repo.get_or_create(relationship.user_b_id)
        return max(settings_a.required_joint_count, settings_b.required_joint_count)

    async def schedule_joint_session(
        self, initiator: User, partner_id: int, place: str, scheduled_date: date
    ) -> JointCareSession:
        relationship = await self.relationship_repo.get(initiator.id, partner_id)
        if relationship is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "매칭 관계가 없습니다. 먼저 돌봄 요청을 주고받으세요.")

        joint_session = JointCareSession(
            initiator_id=initiator.id, partner_id=partner_id, place=place, scheduled_date=scheduled_date
        )
        self.joint_repo.add(joint_session)

        if relationship.level == TrustLevel.L1:
            self.relationship_repo.add_history(
                TrustLevelHistory(
                    relationship_id=relationship.id, previous_level=TrustLevel.L1, new_level=TrustLevel.L2
                )
            )
            relationship.level = TrustLevel.L2
            self.event_service.log(
                HypothesisEventType.TRUST_LEVEL_TRANSITION,
                relationship.user_a_id,
                relationship.user_b_id,
                payload={"previous_level": TrustLevel.L1.value, "new_level": TrustLevel.L2.value},
            )
            self._notify_transition(relationship.user_a_id, relationship.user_b_id, TrustLevel.L2)

        await self.session.commit()
        await self.session.refresh(joint_session)
        return joint_session

    async def confirm_joint_session(self, joint_session_id: int, user: User) -> JointCareSession:
        joint_session = await self.joint_repo.get(joint_session_id)
        if joint_session is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "공동육아 일정을 찾을 수 없습니다.")

        if user.id == joint_session.initiator_id:
            joint_session.confirmed_by_initiator = True
        elif user.id == joint_session.partner_id:
            joint_session.confirmed_by_partner = True
        else:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "일정 당사자만 완료 확인할 수 있습니다.")

        if (
            joint_session.confirmed_by_initiator
            and joint_session.confirmed_by_partner
            and joint_session.status != JointCareSessionStatus.COMPLETED
        ):
            joint_session.status = JointCareSessionStatus.COMPLETED
            relationship = await self.relationship_repo.get(joint_session.initiator_id, joint_session.partner_id)
            assert relationship is not None
            relationship.joint_session_count += 1
            required = await self._required_count(relationship)
            if relationship.level == TrustLevel.L2 and relationship.joint_session_count >= required:
                self.relationship_repo.add_history(
                    TrustLevelHistory(
                        relationship_id=relationship.id, previous_level=TrustLevel.L2, new_level=TrustLevel.L3
                    )
                )
                relationship.level = TrustLevel.L3
                self.event_service.log(
                    HypothesisEventType.TRUST_LEVEL_TRANSITION,
                    relationship.user_a_id,
                    relationship.user_b_id,
                    payload={"previous_level": TrustLevel.L2.value, "new_level": TrustLevel.L3.value},
                )
                self._notify_transition(relationship.user_a_id, relationship.user_b_id, TrustLevel.L3)

        await self.session.commit()
        await self.session.refresh(joint_session)
        return joint_session

    async def set_required_count(self, user: User, count: int) -> TrustSettings:
        if count < MIN_REQUIRED_JOINT_COUNT:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST, f"필요 횟수는 {MIN_REQUIRED_JOINT_COUNT}회 이상이어야 합니다."
            )
        settings = await self.settings_repo.get_or_create(user.id)
        settings.required_joint_count = count
        await self.session.commit()
        await self.session.refresh(settings)
        return settings

    async def demote(self, admin: User, user_a_id: int, user_b_id: int, reason: str) -> TrustRelationship:
        if not admin.is_admin:
            raise HTTPException(status.HTTP_403_FORBIDDEN, "운영자만 등급을 강등할 수 있습니다.")
        relationship = await self.relationship_repo.get(user_a_id, user_b_id)
        if relationship is None:
            raise HTTPException(status.HTTP_404_NOT_FOUND, "관계를 찾을 수 없습니다.")
        if relationship.level == TrustLevel.L1:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "이미 최저 등급(L1)입니다.")

        previous_level = relationship.level
        new_level = TrustLevel.L2 if previous_level == TrustLevel.L3 else TrustLevel.L1
        relationship.level = new_level
        self.relationship_repo.add_history(
            TrustLevelHistory(
                relationship_id=relationship.id,
                previous_level=previous_level,
                new_level=new_level,
                changed_by_user_id=admin.id,
                reason=reason,
            )
        )
        self.event_service.log(
            HypothesisEventType.TRUST_LEVEL_TRANSITION,
            relationship.user_a_id,
            relationship.user_b_id,
            payload={"previous_level": previous_level.value, "new_level": new_level.value, "reason": reason},
        )
        self._notify_transition(relationship.user_a_id, relationship.user_b_id, new_level)
        await self.session.commit()
        await self.session.refresh(relationship)
        return relationship
