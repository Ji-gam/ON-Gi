"""access_log

Revision ID: a7c3e9f1b204
Revises: a3b8e1f4c7d2
Create Date: 2026-08-21 09:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "a7c3e9f1b204"
down_revision: Union[str, None] = "a3b8e1f4c7d2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.create_table(
        "access_logs",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("actor_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("target_child_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("action", sa.String(length=10), nullable=False),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.ForeignKeyConstraint(["actor_user_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["target_child_id"], ["children.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
    )
    op.create_index(op.f("ix_access_logs_actor_user_id"), "access_logs", ["actor_user_id"], unique=False)
    op.create_index(op.f("ix_access_logs_target_child_id"), "access_logs", ["target_child_id"], unique=False)
    op.create_index(op.f("ix_access_logs_created_at"), "access_logs", ["created_at"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_access_logs_created_at"), table_name="access_logs")
    op.drop_index(op.f("ix_access_logs_target_child_id"), table_name="access_logs")
    op.drop_index(op.f("ix_access_logs_actor_user_id"), table_name="access_logs")
    op.drop_table("access_logs")
