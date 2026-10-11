"""ordem do culto: itens marcados como feitos

Revision ID: c3a9e5d17f42
Revises: b7c4e1a92d30
Create Date: 2026-10-11 18:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c3a9e5d17f42'
down_revision = 'b7c4e1a92d30'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('feitos', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.drop_column('feitos')
