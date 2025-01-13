from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json
from werkzeug.security import generate_password_hash, check_password_hash
from flask_login import UserMixin

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
    id = db.Column(db.Integer, primary_key=True)
    username = db.Column(db.String(80), unique=True, nullable=False)
    password_hash = db.Column(db.String(128))
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

class Cotizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(50), unique=True, nullable=False)
    tipo = db.Column(db.String(50), nullable=False)
    nombre = db.Column(db.String(100), nullable=False)
    empresa = db.Column(db.String(100), nullable=True)
    ubicacion = db.Column(db.String(100), nullable=False)
    telefono = db.Column(db.String(50), nullable=False)
    fecha = db.Column(db.DateTime, nullable=False, default=datetime.utcnow)
    subtotal = db.Column(db.Float, nullable=False)
    itbms = db.Column(db.Float, nullable=False)
    total = db.Column(db.Float, nullable=False)
    items = db.Column(db.Text, nullable=False)
    pdf_path = db.Column(db.String(200))
    estado = db.Column(db.String(20), default='pendiente')  # pendiente, aprobada, facturada
    fecha_aprobacion = db.Column(db.DateTime)
    fecha_facturacion = db.Column(db.DateTime)
    numero_factura = db.Column(db.String(20))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='cotizaciones')

    def set_items(self, items_list):
        self.items = json.dumps(items_list)

    def get_items(self):
        return json.loads(self.items) if self.items else []

    def to_dict(self):
        return {
            'numero': self.numero,
            'tipo': self.tipo,
            'nombre': self.nombre,
            'empresa': self.empresa,
            'ubicacion': self.ubicacion,
            'telefono': self.telefono,
            'fecha': self.fecha.strftime('%d/%m/%Y'),
            'subtotal': self.subtotal,
            'itbms': self.itbms,
            'total': self.total,
            'items': json.loads(self.items)
        }

class Factura(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(20), unique=True, nullable=False)
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'), nullable=False)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float)
    itbms = db.Column(db.Float)
    total = db.Column(db.Float)
    estado = db.Column(db.String(20), default='emitida')  # emitida, pagada, anulada
    fecha_pago = db.Column(db.DateTime)
    metodo_pago = db.Column(db.String(50))
    pdf_path = db.Column(db.String(200))
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    usuario = db.relationship('Usuario', backref='facturas')
    
    # Campos para tracking
    creado_por = db.Column(db.String(100))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    modificado_por = db.Column(db.String(100))
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow)

    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'fecha': self.fecha.strftime('%Y-%m-%d %H:%M:%S'),
            'subtotal': self.subtotal,
            'itbms': self.itbms,
            'total': self.total,
            'estado': self.estado,
            'cotizacion_numero': self.cotizacion.numero if self.cotizacion else None
        }

class Auditoria(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    accion = db.Column(db.String(50))  # login, crear_cotizacion, crear_factura, etc.
    detalle = db.Column(db.Text)
    ip = db.Column(db.String(50))
    
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
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    tipo = db.Column(db.String(50))  # sistema, factura, cotizacion
    titulo = db.Column(db.String(200))
    mensaje = db.Column(db.Text)
    leida = db.Column(db.Boolean, default=False)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    
    usuario = db.relationship('Usuario', backref='notificaciones')