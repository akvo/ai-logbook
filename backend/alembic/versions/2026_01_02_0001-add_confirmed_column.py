"""add confirmed column

Revision ID: add_confirmed_column
Revises: f824dde24477
Create Date: 2026-01-02 00:01:00.000000

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = 'add_confirmed_column'
down_revision: Union[str, None] = 'f824dde24477'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    # Add confirmed column with default False
    op.add_column('records', sa.Column('confirmed', sa.Boolean(), nullable=False, server_default='false'))

    # Update needs_followup default to True for new records
    # Existing records with needs_followup=False should be set to True if not confirmed
    op.execute("UPDATE records SET needs_followup = true WHERE confirmed = false")


def downgrade() -> None:
    op.drop_column('records', 'confirmed')
