"""add user notification preferences

Revision ID: b2c3d4e5f6g7
Revises: a1b2c3d4e5f6
Create Date: 2026-02-05

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'b2c3d4e5f6g7'
down_revision: Union[str, None] = 'a1b2c3d4e5f6'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    op.add_column('users', sa.Column('notification_email', sa.String(length=255), nullable=True))
    op.add_column('users', sa.Column('email_enabled', sa.Boolean(), nullable=False, server_default='false'))
    op.add_column('users', sa.Column('notify_network_threats', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('notify_system_threats', sa.Boolean(), nullable=False, server_default='true'))
    op.add_column('users', sa.Column('notify_general_summary', sa.Boolean(), nullable=False, server_default='true'))


def downgrade() -> None:
    op.drop_column('users', 'notify_general_summary')
    op.drop_column('users', 'notify_system_threats')
    op.drop_column('users', 'notify_network_threats')
    op.drop_column('users', 'email_enabled')
    op.drop_column('users', 'notification_email')
