"""configurações: idioma da interface

Revision ID: b8e2f4a61c03
Revises: a7d3c1f09b42
Create Date: 2026-10-26 13:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b8e2f4a61c03'
down_revision = 'a7d3c1f09b42'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.add_column(sa.Column('language', sa.String(length=5), nullable=True))


def downgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.drop_column('language')
