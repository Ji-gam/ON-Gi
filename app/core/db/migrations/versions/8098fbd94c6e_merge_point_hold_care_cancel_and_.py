"""merge point_hold_care_cancel and hypothesis_event heads

Revision ID: 8098fbd94c6e
Revises: f1a2b3c4d5e6, f5a1c3e7b902
Create Date: 2026-08-17 08:01:05.305576

"""

from typing import Sequence, Union

import sqlalchemy as sa
from alembic import op


# revision identifiers, used by Alembic.
revision: str = "8098fbd94c6e"
down_revision: Union[str, Sequence[str], None] = ("f1a2b3c4d5e6", "f5a1c3e7b902")
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    pass


def downgrade() -> None:
    pass
