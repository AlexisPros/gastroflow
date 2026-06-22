"""add user kitchen section

Revision ID: 35e5b3a75d66
Revises: 5c8e4a1d9b22
Create Date: 2026-06-17 00:04:46.098792

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '35e5b3a75d66'
down_revision: Union[str, Sequence[str], None] = '5c8e4a1d9b22'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    op.add_column('users', sa.Column('kitchen_section_id', sa.Integer(), nullable=True))
    op.create_foreign_key(
        'fk_users_kitchen_section_id_kitchen_sections',
        'users',
        'kitchen_sections',
        ['kitchen_section_id'],
        ['id'],
    )


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_constraint('fk_users_kitchen_section_id_kitchen_sections', 'users', type_='foreignkey')
    op.drop_column('users', 'kitchen_section_id')
