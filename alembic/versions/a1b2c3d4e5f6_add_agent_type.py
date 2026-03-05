"""Add agent_type column

Revision ID: a1b2c3d4e5f6
Revises: 124ddb5435fd
Create Date: 2026-02-05 10:00:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'a1b2c3d4e5f6'
down_revision: Union[str, None] = '124ddb5435fd'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('agents', sa.Column('agent_type', sa.String(length=20), nullable=False, server_default='device'))


def downgrade() -> None:
    op.drop_column('agents', 'agent_type')
