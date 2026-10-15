"""partitura: sinais de repetição por compasso (ritornelo, casas, D.C., D.S...)

Revision ID: e41b7c2d9a10
Revises: c3a9e5d17f42
Create Date: 2026-10-15 09:30:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'e41b7c2d9a10'
down_revision = 'c3a9e5d17f42'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('sheet_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('marks', sa.JSON(), nullable=True))


def downgrade():
    with op.batch_alter_table('sheet_data', schema=None) as batch_op:
        batch_op.drop_column('marks')
