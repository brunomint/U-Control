"""slides do telão: conjuntos com nome (os Avisos em slides viram um deles)

Revision ID: a1f5c8e2d940
Revises: d4a8f1c6b372
Create Date: 2026-11-25 10:00:00

"""
import json

from alembic import op
import sqlalchemy as sa


# revision identifiers, used by Alembic.
revision = 'a1f5c8e2d940'
down_revision = 'd4a8f1c6b372'
branch_labels = None
depends_on = None


def upgrade():
    op.create_table(
        'conjunto_slides',
        sa.Column('id', sa.Integer(), nullable=False),
        sa.Column('nome', sa.String(length=80), nullable=False),
        sa.Column('tema_id', sa.Integer(), nullable=True),
        sa.Column('segundos', sa.Integer(), nullable=True),
        sa.Column('automatica', sa.Boolean(), nullable=True),
        sa.Column('embaralhar', sa.Boolean(), nullable=True),
        sa.Column('slides', sa.JSON(), nullable=True),
        sa.PrimaryKeyConstraint('id'),
    )
    # Os Avisos em slides (uma lista só) viram o conjunto "Avisos"
    con = op.get_bind()
    linha = con.execute(sa.text('SELECT itens, tema_id, segundos, embaralhar FROM avisos_config ORDER BY id LIMIT 1')).fetchone()
    itens, tema_id, segundos, embaralhar = linha if linha else (None, None, None, None)
    if isinstance(itens, str):
        try:
            itens = json.loads(itens)
        except ValueError:
            itens = []
    slides = [{'tipo': 'texto', 'texto': str(t)} for t in (itens or []) if str(t or '').strip()]
    con.execute(sa.text('INSERT INTO conjunto_slides (nome, tema_id, segundos, automatica, embaralhar, slides) '
                        'VALUES (:nome, :tema, :seg, :auto, :emb, :slides)'),
                {'nome': 'Avisos', 'tema': tema_id, 'seg': segundos or 10, 'auto': True,
                 'emb': bool(embaralhar), 'slides': json.dumps(slides, ensure_ascii=False)})


def downgrade():
    op.drop_table('conjunto_slides')
