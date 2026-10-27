"""músicas: ordem de apresentação das seções

Revision ID: d7a3e9c15f40
Revises: c4f1d8b27e95
Create Date: 2026-10-27 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'd7a3e9c15f40'
down_revision = 'c4f1d8b27e95'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('song', schema=None) as batch_op:
        batch_op.add_column(sa.Column('order', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('song', schema=None) as batch_op:
        batch_op.drop_column('order')
