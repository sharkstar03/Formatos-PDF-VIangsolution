from flask_sqlalchemy import SQLAlchemy
from datetime import datetime
import json

db = SQLAlchemy()

class Cotizacion(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    numero = db.Column(db.String(10), unique=True, nullable=False)
    tipo = db.Column(db.String(20), nullable=False)  # 'empresa' o 'natural'
    nombre = db.Column(db.String(100), nullable=False)
    empresa = db.Column(db.String(100))
    ubicacion = db.Column(db.String(200))
    telefono = db.Column(db.String(20))
    subtotal = db.Column(db.Float)
    itbms = db.Column(db.Float)
    total = db.Column(db.Float)
    fecha = db.Column(db.DateTime, default=datetime.utcnow)
    items = db.Column(db.Text, default='[]')
    pdf_path = db.Column(db.String(200))

    def set_items(self, items_list):
        self.items = json.dumps(items_list)

    def get_items(self):
        return json.loads(self.items) if self.items else []

    def __repr__(self):
        return f'<Cotizacion {self.numero}>'