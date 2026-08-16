"""point_hold_care_cancel

Revision ID: f1a2b3c4d5e6
Revises: e4a7b1d0c9f2
Create Date: 2026-08-16 00:00:00.000000

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op

# revision identifiers, used by Alembic.
revision: str = "f1a2b3c4d5e6"
down_revision: Union[str, None] = "e4a7b1d0c9f2"
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column("point_accounts", sa.Column("held_balance", sa.Integer(), nullable=False, server_default="0"))
    op.alter_column("point_accounts", "held_balance", server_default=None)

    op.add_column("care_sessions", sa.Column("cancelled_at", sa.DateTime(timezone=True), nullable=True))
    op.add_column("care_sessions", sa.Column("cancel_reason", sa.String(length=500), nullable=True))
    op.add_column(
        "care_sessions",
        sa.Column("at_fault_user_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=True),
    )
    op.create_foreign_key(
        "fk_care_sessions_at_fault_user_id_users",
        "care_sessions",
        "users",
        ["at_fault_user_id"],
        ["id"],
        ondelete="SET NULL",
    )

    bind = op.get_bind()
    if bind.dialect.name == "postgresql":
        op.execute("ALTER TYPE care_session_status_enum ADD VALUE IF NOT EXISTS 'CANCELLED'")
        op.execute("ALTER TYPE care_session_status_enum ADD VALUE IF NOT EXISTS 'NO_SHOW'")

    op.create_table(
        "point_holds",
        sa.Column("id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), autoincrement=True, nullable=False),
        sa.Column("care_session_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("payer_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("payee_id", sa.BigInteger().with_variant(sa.Integer(), "sqlite"), nullable=False),
        sa.Column("amount", sa.Integer(), nullable=False),
        sa.Column(
            "status",
            sa.Enum("HELD", "SETTLED", "RELEASED", "FORFEITED", name="point_hold_status_enum"),
            nullable=False,
        ),
        sa.Column("created_at", sa.DateTime(timezone=True), server_default=sa.text("now()"), nullable=False),
        sa.Column("resolved_at", sa.DateTime(timezone=True), nullable=True),
        sa.ForeignKeyConstraint(["care_session_id"], ["care_sessions.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payer_id"], ["users.id"], ondelete="CASCADE"),
        sa.ForeignKeyConstraint(["payee_id"], ["users.id"], ondelete="CASCADE"),
        sa.PrimaryKeyConstraint("id"),
        sa.UniqueConstraint("care_session_id"),
    )
    op.create_index(op.f("ix_point_holds_payer_id"), "point_holds", ["payer_id"], unique=False)


def downgrade() -> None:
    op.drop_index(op.f("ix_point_holds_payer_id"), table_name="point_holds")
    op.drop_table("point_holds")

    op.drop_constraint("fk_care_sessions_at_fault_user_id_users", "care_sessions", type_="foreignkey")
    op.drop_column("care_sessions", "at_fault_user_id")
    op.drop_column("care_sessions", "cancel_reason")
    op.drop_column("care_sessions", "cancelled_at")

    op.drop_column("point_accounts", "held_balance")
