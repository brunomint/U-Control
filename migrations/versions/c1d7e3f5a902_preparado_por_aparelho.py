"""Conteúdo preparado por aparelho (chave device + kind)

O preparado é passageiro: recriar a tabela só perde o que estivesse esperando
Liberar, e sem aparelho nenhum dono ele não apareceria pra ninguém.

Revision ID: c1d7e3f5a902
Revises: b9e4c2a7d815
"""
from alembic import op
import sqlalchemy as sa

revision = 'c1d7e3f5a902'
down_revision = 'b9e4c2a7d815'
branch_labels = None
depends_on = None


def _criar(com_aparelho):
    colunas = [sa.Column('device', sa.String(length=64), nullable=False)] if com_aparelho else []
    chave = ('device', 'kind') if com_aparelho else ('kind',)
    op.create_table(
        'staged_content',
        *colunas,
        sa.Column('kind', sa.String(length=20), nullable=False),
        sa.Column('payload', sa.JSON(), nullable=False),
        sa.Column('label', sa.String(length=300), nullable=True),
        sa.Column('updated_at', sa.DateTime(), nullable=True),
        sa.PrimaryKeyConstraint(*chave),
    )


def upgrade():
    op.drop_table('staged_content')
    _criar(True)


def downgrade():
    op.drop_table('staged_content')
    _criar(False)
