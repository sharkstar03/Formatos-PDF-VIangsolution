from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(120), nullable=False)
    email = db.Column(db.String(120), unique=True, nullable=False)
    nombre_completo = db.Column(db.String(120))
    rol = db.Column(db.String(20), default='usuario')  # admin, usuario
    activo = db.Column(db.Boolean, default=True)
    fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
    ultima_conexion = db.Column(db.DateTime)

    def set_password(self, password):
        self.password_hash = generate_password_hash(password)

    def check_password(self, password):
        return check_password_hash(self.password_hash, password)

    def to_dict(self):
        return {
            'id': self.id,
            'username': self.username,
            'email': self.email,
            'nombre_completo': self.nombre_completo,
            'rol': self.rol,
            'activo': self.activo,
            'fecha_registro': self.fecha_registro.strftime('%Y-%m-%d %H:%M:%S')
        }

class Cliente(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nombre = db.Column(db.String(100), nullable=False)
    # ...otros campos...

class Cotizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    empresa = db.Column(db.String(100))
    ubicacion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float)
    itbms = db.Column(db.Float)
    total = db.Column(db.Float)
    items = db.Column(db.Text)
    estado = db.Column(db.String(20), default='pendiente')
    fecha_facturacion = db.Column(db.DateTime)
    numero_factura = db.Column(db.String(10))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='cotizaciones')
    cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)  # Add this line
    cliente = db.relationship('Cliente', backref='cotizaciones')

    def set_items(self, items_list):
        self.items = json.dumps(items_list)

    def get_items(self):
        return json.loads(self.items) if self.items else []

    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'nombre': self.nombre,
            'tipo': self.tipo,
            'fecha': self.fecha.strftime('%Y-%m-%d'),
            'total': self.total,
            'estado': self.estado
        }

class Factura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float)
    itbms = db.Column(db.Float)
    total = db.Column(db.Float)
    estado = db.Column(db.String(20), default='emitida')
    fecha_pago = db.Column(db.DateTime)
    creado_por = db.Column(db.String(80))
    modificado_por = db.Column(db.String(80))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow)

    cotizacion = db.relationship('Cotizacion', backref='facturas')

    def to_dict(self):
        return {
            'numero': self.numero,
            'fecha': self.fecha.strftime('%Y-%m-%d'),
            'total': self.total,
            'estado': self.estado,
            'cliente': self.cotizacion.nombre if self.cotizacion else None
        }

class Auditoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    accion = db.Column(db.String(50))
    detalle = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    ip = db.Column(db.String(20))

    usuario = db.relationship('Usuario', backref='auditorias')

class Backup(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    archivo = db.Column(db.String(200))
    tipo = db.Column(db.String(50))  # completo, parcial
    estado = db.Column(db.String(50))  # exitoso, fallido
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    
    usuario = db.relationship('Usuario', backref='backups')

class Notificacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    tipo = db.Column(db.String(20))
    titulo = db.Column(db.String(100))
    mensaje = db.Column(db.Text)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    leida = db.Column(db.Boolean, default=False)

    usuario = db.relationship('Usuario', backref='notificaciones')