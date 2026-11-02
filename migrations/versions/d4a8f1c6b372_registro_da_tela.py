"""Registro da tela: cada troca do que o público viu (registro_tela.py)

Revision ID: d4a8f1c6b372
Revises: c1d7e3f5a902
"""
from alembic import op
import sqlalchemy as sa

revision = 'd4a8f1c6b372'
down_revision = 'c1d7e3f5a902'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'tela_evento',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('ts_ms', sa.BigInteger(), nullable=False),
        sa.Column('tipo', sa.String(length=20), nullable=False),
        sa.Column('titulo', sa.String(length=300), nullable=True),
        sa.Column('texto', sa.Text(), nullable=True),
        sa.Column('tema', sa.Text(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    op.create_index('ix_tela_evento_ts_ms', 'tela_evento', ['ts_ms'])


def downgrade():
    op.drop_index('ix_tela_evento_ts_ms', table_name='tela_evento')
    op.drop_table('tela_evento')
