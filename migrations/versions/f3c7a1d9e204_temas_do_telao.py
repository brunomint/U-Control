"""temas do telão: biblioteca de temas, tema padrão e tema por culto

Revision ID: f3c7a1d9e204
Revises: e8b4f2a61c07
Create Date: 2026-11-01 10:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'f3c7a1d9e204'
down_revision = 'e8b4f2a61c07'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tema',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=80), nullable=False),
        sa.Column('dados', sa.JSON(), nullable=False),
        sa.PrimaryKeyConstraint('id'),
    )
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tema_padrao_id', sa.Integer(), nullable=True))
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.add_column(sa.Column('tema_telao', sa.Integer(), nullable=True))


def downgrade():
    with op.batch_alter_table('order', schema=None) as batch_op:
        batch_op.drop_column('tema_telao')
    with op.batch_alter_table('setting', schema=None) as batch_op:
        batch_op.drop_column('tema_padrao_id')
    op.drop_table('tema')
