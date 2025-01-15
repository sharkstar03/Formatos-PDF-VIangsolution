from flask_sqlalchemy import SQLAlchemy
from flask_login import UserMixin
from datetime import datetime
from werkzeug.security import generate_password_hash, check_password_hash
import json

db = SQLAlchemy()

class Usuario(UserMixin, db.Model):
   id = db.Column(db.Integer, primary_key=True)
   username = db.Column(db.String(80), unique=True, nullable=False)
   password_hash = db.Column(db.String(120), nullable=False)
   email = db.Column(db.String(120), unique=True, nullable=False)
   nombre_completo = db.Column(db.String(120))
   rol = db.Column(db.String(20), default='usuario')
   activo = db.Column(db.Boolean, default=True)
   fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
   ultima_conexion = db.Column(db.DateTime)

   def set_password(self, password):
       self.password_hash = generate_password_hash(password)

   def check_password(self, password):
       try:
           return check_password_hash(self.password_hash, password)
       except Exception as e:
           print(f"Error checking password: {e}")
           return False

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
   empresa = db.Column(db.String(100))
   direccion = db.Column(db.String(200))
   telefono = db.Column(db.String(20))
   email = db.Column(db.String(120))
   ruc = db.Column(db.String(50))
   dv = db.Column(db.String(10))
   fecha_registro = db.Column(db.DateTime, default=datetime.utcnow)
   activo = db.Column(db.Boolean, default=True)
   
   def to_dict(self):
       return {
           'id': self.id,
           'nombre': self.nombre,
           'empresa': self.empresa,
           'direccion': self.direccion,
           'telefono': self.telefono,
           'email': self.email,
           'ruc': self.ruc,
           'dv': self.dv,
           'activo': self.activo,
           'fecha_registro': self.fecha_registro.strftime('%Y-%m-%d %H:%M:%S')
       }

class Cotizacion(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   numero = db.Column(db.String(10), unique=True, nullable=False)
   tipo = db.Column(db.String(20), nullable=False)  # natural o empresa
   nombre = db.Column(db.String(100), nullable=False)
   empresa = db.Column(db.String(100))
   ubicacion = db.Column(db.String(200))
   telefono = db.Column(db.String(20))
   ruc = db.Column(db.String(50))  
   dv = db.Column(db.String(10))  
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
   cliente_id = db.Column(db.Integer, db.ForeignKey('cliente.id'), nullable=True)
   cliente = db.relationship('Cliente', backref='cotizaciones')
   creado_por = db.Column(db.String(50))  # Add this line

   def set_items(self, items_list):
       self.items = json.dumps(items_list)

   def get_items(self):
       try:
           return json.loads(self.items) if self.items else []
       except json.JSONDecodeError:
           return []

   def to_dict(self):
       return {
           'id': self.id,
           'numero': self.numero,
           'tipo': self.tipo,
           'nombre': self.nombre,
           'empresa': self.empresa,
           'ubicacion': self.ubicacion,
           'telefono': self.telefono,
           'ruc': self.ruc,
           'dv': self.dv,
           'fecha': self.fecha.strftime('%Y-%m-%d'),
           'subtotal': f"${self.subtotal:.2f}" if self.subtotal else '$0.00',
           'itbms': f"${self.itbms:.2f}" if self.itbms else '$0.00',
           'total': f"${self.total:.2f}" if self.total else '$0.00',
           'items': self.get_items(),
           'estado': self.estado,
           'fecha_facturacion': self.fecha_facturacion.strftime('%Y-%m-%d') if self.fecha_facturacion else None,
           'numero_factura': self.numero_factura,
           'usuario_id': self.usuario_id,
           'cliente_id': self.cliente_id,
       }

class Factura(db.Model):
    __tablename__ = 'factura'
    __table_args__ = {'extend_existing': True}
    
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    cotizacion_id = db.Column(db.Integer, db.ForeignKey('cotizacion.id'))
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    subtotal = db.Column(db.Float)
    itbms = db.Column(db.Float)
    total = db.Column(db.Float)
    estado = db.Column(db.String(20), default='pendiente')
    fecha_pago = db.Column(db.DateTime)
    usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
    creado_por = db.Column(db.String(50))
    fecha_creacion = db.Column(db.DateTime, default=datetime.utcnow)
    fecha_modificacion = db.Column(db.DateTime, onupdate=datetime.utcnow)
    modificado_por = db.Column(db.String(50))

    cotizacion = db.relationship('Cotizacion', backref='facturas')
    usuario = db.relationship('Usuario', backref='facturas')

    def to_dict(self):
        return {
            'id': self.id,
            'numero': self.numero,
            'cotizacion_id': self.cotizacion_id,
            'fecha': self.fecha.strftime('%Y-%m-%d'),
            'subtotal': f"${self.subtotal:.2f}" if self.subtotal else '$0.00',
            'itbms': f"${self.itbms:.2f}" if self.itbms else '$0.00',
            'total': f"${self.total:.2f}" if self.total else '$0.00',
            'estado': self.estado,
            'fecha_pago': self.fecha_pago.strftime('%Y-%m-%d') if self.fecha_pago else None,
            'usuario_id': self.usuario_id,
            'creado_por': self.creado_por,
            'fecha_creacion': self.fecha_creacion.strftime('%Y-%m-%d %H:%M:%S'),
            'fecha_modificacion': self.fecha_modificacion.strftime('%Y-%m-%d %H:%M:%S') if self.fecha_modificacion else None,
        }
class Auditoria(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
   accion = db.Column(db.String(50))
   detalle = db.Column(db.Text)
   fecha = db.Column(db.DateTime, default=datetime.utcnow)
   ip = db.Column(db.String(20))

   usuario = db.relationship('Usuario', backref='auditorias')

   def to_dict(self):
       return {
           'id': self.id,
           'usuario_id': self.usuario_id,
           'accion': self.accion,
           'detalle': self.detalle,
           'fecha': self.fecha.strftime('%Y-%m-%d %H:%M:%S'),
           'ip': self.ip
       }

class Backup(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   fecha = db.Column(db.DateTime, default=datetime.utcnow)
   archivo = db.Column(db.String(200))
   tipo = db.Column(db.String(50))
   estado = db.Column(db.String(50))
   usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))

   usuario = db.relationship('Usuario', backref='backups')

   def to_dict(self):
       return {
           'id': self.id,
           'fecha': self.fecha.strftime('%Y-%m-%d %H:%M:%S'),
           'archivo': self.archivo,
           'tipo': self.tipo,
           'estado': self.estado,
           'usuario_id': self.usuario_id
       }

class Notificacion(db.Model):
   id = db.Column(db.Integer, primary_key=True)
   usuario_id = db.Column(db.Integer, db.ForeignKey('usuario.id'))
   tipo = db.Column(db.String(20))
   titulo = db.Column(db.String(100))
   mensaje = db.Column(db.Text)
   fecha = db.Column(db.DateTime, default=datetime.utcnow)
   leida = db.Column(db.Boolean, default=False)

   usuario = db.relationship('Usuario', backref='notificaciones')


   def to_dict(self):
       return {
           'id': self.id,
           'usuario_id': self.usuario_id,
           'tipo': self.tipo,
           'titulo': self.titulo,
           'mensaje': self.mensaje,
           'fecha': self.fecha.strftime('%Y-%m-%d %H:%M:%S'),
           'leida': self.leida
       }