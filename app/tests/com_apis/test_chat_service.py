"""REQ-F-COM-01. L1 이상 관계에서만 채팅 가능, 휴대폰 번호 형식은 마스킹되고 경고 플래그가 남는다."""

from datetime import date

import pytest
from fastapi import HTTPException
from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.models.base import Base
from app.services.chat_service import NOT_MATCHED_MESSAGE, ChatService
from app.services.trust_level_service import TrustLevelService
from auth_kit.models import Gender
from auth_kit.schemas import SignUpRequest, TermAgreementItem
from auth_kit.service import AuthService
from auth_kit.terms_catalog import CATALOG_BY_TYPE, REQUIRED_TYPES


async def _session():
    engine = create_async_engine("sqlite+aiosqlite:///:memory:")
    async with engine.begin() as conn:
        await conn.run_sync(Base.metadata.create_all)
    return async_sessionmaker(engine, expire_on_commit=False)()


def _agreements() -> list[TermAgreementItem]:
    return [TermAgreementItem(terms_type=t, version=CATALOG_BY_TYPE[t].version, agreed=True) for t in REQUIRED_TYPES]


async def _signed_up_user(session, *, email: str, nickname: str, phone: str):
    result = await AuthService(session).signup(
        SignUpRequest(
            email=email,
            password="Password123!",
            name="홍길동",
            nickname=nickname,
            birth_date=date(1990, 1, 1),
            gender=Gender.MALE,
            phone_number=phone,
            agreements=_agreements(),
        )
    )
    return result.user


async def test_send_message_requires_l1_relationship():
    session = await _session()
    a = await _signed_up_user(session, email="chat_a@example.com", nickname="채팅시험A", phone="010-9501-0001")
    b = await _signed_up_user(session, email="chat_b@example.com", nickname="채팅시험B", phone="010-9501-0002")

    with pytest.raises(HTTPException) as exc_info:
        await ChatService(session).send_message(a, b.id, "안녕하세요")
    assert exc_info.value.detail == NOT_MATCHED_MESSAGE


async def test_send_and_list_messages_after_l1_and_phone_number_masked():
    session = await _session()
    a = await _signed_up_user(session, email="chat_c@example.com", nickname="채팅시험C", phone="010-9501-0003")
    b = await _signed_up_user(session, email="chat_d@example.com", nickname="채팅시험D", phone="010-9501-0004")

    await TrustLevelService(session).grant_l1(a.id, b.id)

    plain = await ChatService(session).send_message(a, b.id, "언제 만날까요?")
    assert plain.pii_masked is False
    assert plain.content == "언제 만날까요?"

    with_phone = await ChatService(session).send_message(b, a.id, "제 번호는 010-1234-5678이에요")
    assert with_phone.pii_masked is True
    assert "010-1234-5678" not in with_phone.content
    assert "***-****-****" in with_phone.content

    messages = await ChatService(session).list_messages(a, b.id)
    assert [m.content for m in messages] == [plain.content, with_phone.content]
