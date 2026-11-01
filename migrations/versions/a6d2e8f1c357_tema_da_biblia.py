"""temas do telão: tema da Bíblia

Revision ID: a6d2e8f1c357
Revises: f3c7a1d9e204
Create Date: 2026-11-01 16:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a6d2e8f1c357'
down_revision = 'f3c7a1d9e204'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tema_biblia_id', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.drop_column('tema_biblia_id')
