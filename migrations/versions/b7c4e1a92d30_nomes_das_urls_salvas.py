"""Nomes das URLs salvas (Câmera, Slides…) pro Controle

Revision ID: b7c4e1a92d30
Revises: 8713f8212445
Create Date: 2026-10-09 11:30:00.000000

"""
from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'b7c4e1a92d30'
down_revision = '8713f8212445'
branch_labels = None
depends_on = None


def upgrade():
    # Colunas opcionais: linhas existentes ficam sem nome e o Controle
    # mostra "URL 1/2/3" como antes
    with op.batch_alter_table('saved_urls', schema=None) as batch_op:
        batch_op.add_column(sa.Column('name1', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('name2', sa.String(length=80), nullable=True))
        batch_op.add_column(sa.Column('name3', sa.String(length=80), nullable=True))


def downgrade():
    with op.batch_alter_table('saved_urls', schema=None) as batch_op:
        batch_op.drop_column('name3')
        batch_op.drop_column('name2')
        batch_op.drop_column('name1')
