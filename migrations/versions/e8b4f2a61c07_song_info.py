"""músicas: ficha (copyright, CCLI, tom original, andamento, compasso)

Revision ID: e8b4f2a61c07
Revises: d7a3e9c15f40
Create Date: 2026-10-27 18:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e8b4f2a61c07'
down_revision = 'd7a3e9c15f40'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('song', schema=None) as batch_op:
        batch_op.add_column(sa.Column('info', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('song', schema=None) as batch_op:
        batch_op.drop_column('info')
