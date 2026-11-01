"""avisos em slides no telão do público

Revision ID: b9e4c2a7d815
Revises: a6d2e8f1c357
Create Date: 2026-11-01 19:00:00

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b9e4c2a7d815'
down_revision = 'a6d2e8f1c357'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'avisos_config',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('itens', sa.JSON(), nullable=True),
        sa.Column('tema_id', sa.Integer(), nullable=True),
        sa.Column('segundos', sa.Integer(), nullable=True),
        sa.Column('embaralhar', sa.Boolean(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )


def downgrade():
    op.drop_table('avisos_config')
