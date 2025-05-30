"""add_preferred_currency_to_users

Revision ID: 2cac03aded03
Revises: 2cc4da32fb1c
Create Date: 2025-05-30 15:32:00.943085

"""
from typing import Sequence, Union

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision: str = '2cac03aded03'
down_revision: Union[str, None] = '2cc4da32fb1c'
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


def upgrade() -> None:
    """Upgrade schema."""
    # Добавляем колонку как nullable с дефолтным значением
    op.add_column('users', sa.Column('preferred_currency', sa.String(length=3), nullable=True, server_default='USD'))
    
    # Обновляем все существующие записи
    op.execute("UPDATE users SET preferred_currency = 'USD' WHERE preferred_currency IS NULL")
    
    # Теперь делаем колонку NOT NULL
    op.alter_column('users', 'preferred_currency', nullable=False)


def downgrade() -> None:
    """Downgrade schema."""
    op.drop_column('users', 'preferred_currency')
