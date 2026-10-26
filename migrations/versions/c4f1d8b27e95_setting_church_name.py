"""configurações: nome da igreja (calendário da Agenda)

Revision ID: c4f1d8b27e95
Revises: b8e2f4a61c03
Create Date: 2026-10-26 18:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'c4f1d8b27e95'
down_revision = 'b8e2f4a61c03'
branch_labels = None
depends_on = None


def upgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.add_column(sa.Column('church_name', sa.String(length=120), nullable=True))


def downgrade():
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.drop_column('church_name')
