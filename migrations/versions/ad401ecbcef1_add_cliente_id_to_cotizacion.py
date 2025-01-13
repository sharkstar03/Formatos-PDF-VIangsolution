"""Add cliente_id to cotizacion

Revision ID: ad401ecbcef1
Revises: xxxx
Create Date: 2023-10-10 00:00:00.000000

"""
from alembic import op
import sqlalchemy as sa
from sqlalchemy.engine.reflection import Inspector

# Revisar y actualizar con el ID de revisión correcto
revision = 'ad401ecbcef1'
down_revision = 'xxxx'
branch_labels = None
depends_on = None

def upgrade():
    bind = op.get_bind()
    inspector = Inspector.from_engine(bind)
    columns = [col['name'] for col in inspector.get_columns('cotizacion')]

    with op.batch_alter_table('cotizacion') as batch_op:
        if 'cliente_id' not in columns:
            batch_op.add_column(sa.Column('cliente_id', sa.Integer(), nullable=True))
            batch_op.create_foreign_key('fk_cotizacion_cliente', 'cliente', ['cliente_id'], ['id'])
        if 'pdf_path' in columns:
            batch_op.drop_column('pdf_path')
        if 'fecha_aprobacion' in columns:
            batch_op.drop_column('fecha_aprobacion')

    with op.batch_alter_table('factura') as batch_op:
        batch_op.alter_column('cotizacion_id', existing_type=sa.INTEGER(), nullable=True)
        conn = op.get_bind()
        inspector = sa.inspect(conn)
        constraints = [c['name'] for c in inspector.get_foreign_keys('factura')]
        if 'constraint_name' in constraints:
            batch_op.drop_constraint('constraint_name', type_='foreignkey')  # Provide the constraint name
        if 'usuario_id' in columns:
            batch_op.drop_column('usuario_id')
        if 'pdf_path' in columns:
            batch_op.drop_column('pdf_path')
        if 'metodo_pago' in columns:
            batch_op.drop_column('metodo_pago')
        batch_op.add_column(sa.Column('cliente_id', sa.Integer(), nullable=True))
        batch_op.create_foreign_key('fk_factura_cliente', 'cliente', ['cliente_id'], ['id'])

    with op.batch_alter_table('usuario') as batch_op:
        batch_op.alter_column('password_hash', existing_type=sa.VARCHAR(length=128), nullable=False)

def downgrade():
    with op.batch_alter_table('cotizacion') as batch_op:
        batch_op.drop_constraint('fk_cotizacion_cliente', type_='foreignkey')
        batch_op.drop_column('cliente_id')
        batch_op.add_column(sa.Column('pdf_path', sa.VARCHAR(length=200), nullable=True))
        batch_op.add_column(sa.Column('fecha_aprobacion', sa.DATETIME(), nullable=True))

    with op.batch_alter_table('factura') as batch_op:
        batch_op.alter_column('cotizacion_id', existing_type=sa.INTEGER(), nullable=False)
        batch_op.add_column(sa.Column('usuario_id', sa.INTEGER(), nullable=True))
        batch_op.add_column(sa.Column('pdf_path', sa.VARCHAR(length=200), nullable=True))
        batch_op.add_column(sa.Column('metodo_pago', sa.VARCHAR(length=50), nullable=True))
        batch_op.drop_constraint('fk_factura_cliente', type_='foreignkey')
        batch_op.drop_column('cliente_id')
        batch_op.create_foreign_key('constraint_name', 'other_table', ['other_column'], ['id'])  # Provide the constraint name

    with op.batch_alter_table('usuario') as batch_op:
        batch_op.alter_column('password_hash', existing_type=sa.VARCHAR(length=128), nullable=True)
