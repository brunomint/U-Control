"""sheet_data: rename notes to measures, add ties column

Revision ID: 5aef4d6d3bbd
Revises: 65c71cdb0ae7
Create Date: 2026-08-09 09:29:42.100757

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.dialects import sqlite

# revision identifiers, used by Alembic.
revision = '5aef4d6d3bbd'
down_revision = '65c71cdb0ae7'
branch_labels = None
depends_on = None


def upgrade():
    # Ajustado à mão — o autogenerate do Alembic vê isso como
    # add+drop (perderia os dados das 14 partituras já salvas), não
    # como um rename. Copia o conteúdo de notes -> measures antes de
    # derrubar a coluna antiga.
    with op.batch_alter_table('sheet_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('measures', sa.JSON(), nullable=True))
        batch_op.add_column(sa.Column('ties', sa.JSON(), nullable=True))

    op.execute('UPDATE sheet_data SET measures = notes')

    with op.batch_alter_table('sheet_data', schema=None) as batch_op:
        batch_op.alter_column('measures', nullable=False)
        batch_op.drop_column('notes')


def downgrade():
    with op.batch_alter_table('sheet_data', schema=None) as batch_op:
        batch_op.add_column(sa.Column('notes', sqlite.JSON(), nullable=True))

    op.execute('UPDATE sheet_data SET notes = measures')

    with op.batch_alter_table('sheet_data', schema=None) as batch_op:
        batch_op.alter_column('notes', nullable=False)
        batch_op.drop_column('ties')
        batch_op.drop_column('measures')
