"""add cliente_id to cotizacion

Revision ID: xxxx
Revises: 
Create Date: 2023-10-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# Revisar y actualizar con el ID de revisión correcto
revision = 'xxxx'
down_revision = None
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns('cotizacion')]

    if 'cliente_id' not in columns:
        with op.batch_alter_table('cotizacion') as batch_op:
            batch_op.add_column(sa.Column('cliente_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_cotizacion_cliente', 'cliente', ['cliente_id'], ['id'])

def downgrade():
    with op.batch_alter_table('cotizacion') as batch_op:
        batch_op.drop_constraint('fk_cotizacion_cliente', type_='foreignkey')
        batch_op.drop_column('cliente_id')
