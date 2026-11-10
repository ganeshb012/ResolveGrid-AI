"""Make agent action foreign keys nullable

Revision ID: 3523b14b4672
Revises: c1bf462a055a
Create Date: 2026-11-01 20:40:09.480588

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '3523b14b4672'
down_revision: Union[str, Sequence[str], None] = 'c1bf462a055a'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    with op.batch_alter_table('agent_actions', schema=None) as batch_op:
        batch_op.alter_column('agent_execution_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=True)
        batch_op.alter_column('incident_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=True)


def downgrade() -> None:
    """Downgrade schema."""
    with op.batch_alter_table('agent_actions', schema=None) as batch_op:
        batch_op.alter_column('incident_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=False)
        batch_op.alter_column('agent_execution_id',
               existing_type=sa.VARCHAR(length=36),
               nullable=False)
