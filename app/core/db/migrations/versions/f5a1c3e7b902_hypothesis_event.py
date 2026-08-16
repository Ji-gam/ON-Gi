"""hypothesis_event

Revision ID: f5a1c3e7b902
Revises: e4a7b1d0c9f2
Create Date: 2026-08-16 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f5a1c3e7b902"
down_revision: Union[str, None] = "e4a7b1d0c9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "hypothesis_events",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("event_type", sa.String(length=30), nullable=False),
        sa.Column("actor_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("target_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_user_id"], ["users.id"], ondelete="SET NULL"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_hypothesis_events_event_type"), "hypothesis_events", ["event_type"], unique=False)
    op.create_index(op.f("ix_hypothesis_events_actor_user_id"), "hypothesis_events", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_hypothesis_events_target_user_id"), "hypothesis_events", ["target_user_id"], unique=False)
    op.create_index(op.f("ix_hypothesis_events_created_at"), "hypothesis_events", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_hypothesis_events_created_at"), table_name="hypothesis_events")
    op.drop_index(op.f("ix_hypothesis_events_target_user_id"), table_name="hypothesis_events")
    op.drop_index(op.f("ix_hypothesis_events_actor_user_id"), table_name="hypothesis_events")
    op.drop_index(op.f("ix_hypothesis_events_event_type"), table_name="hypothesis_events")
    op.drop_table("hypothesis_events")
