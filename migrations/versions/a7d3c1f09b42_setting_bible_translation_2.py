"""configurações: segunda versão da Bíblia no telão

Revision ID: a7d3c1f09b42
Revises: e41b7c2d9a10
Create Date: 2026-10-21 23:50:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a7d3c1f09b42'
down_revision = 'e41b7c2d9a10'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.add_column(sa.Column('bible_translation_2', sa.String(length=20), nullable=True))


def downgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.drop_column('bible_translation_2')
