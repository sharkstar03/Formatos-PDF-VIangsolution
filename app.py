from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade  # Import upgrade function
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from weasyprint import HTML
import os
from io import BytesIO
from datetime import datetime, timedelta
import json
from sqlalchemy import extract, func
import pandas as pd
from models import db, Usuario, Cotizacion, Factura, Auditoria, Backup, Notificacion
import shutil
from functools import wraps
import random
import string

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_muy_segura'  # Cambia esto en producción
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cotizaciones.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'pdfs')
app.config['BACKUP_FOLDER'] = os.path.join(app.static_folder, 'backups')

# Asegurar que existan las carpetas necesarias
for folder in [app.config['UPLOAD_FOLDER'], app.config['BACKUP_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

db.init_app(app)
migrate = Migrate(app, db)
login_manager = LoginManager()
login_manager.init_app(app)
login_manager.login_view = 'login'

@login_manager.user_loader
def load_user(user_id):
    return Usuario.query.get(int(user_id))

# Funciones de utilidad
def init_db():
    """Inicializa la base de datos"""
    with app.app_context():
        db.create_all()
        print("Base de datos inicializada")

def get_next_quote_number():
    """Genera y gestiona la numeración automática de cotizaciones"""
    try:
        with open('counter.json', 'r') as f:
            data = json.load(f)
            current_number = data.get('quote_number', 999)
            deleted_numbers = data.get('deleted_numbers', [])
    except FileNotFoundError:
        current_number = 999
        deleted_numbers = []
    
    if deleted_numbers:
        new_number = deleted_numbers.pop(0)
    else:
        new_number = current_number + 1
    
    with open('counter.json', 'w') as f:
        json.dump({'quote_number': new_number, 'deleted_numbers': deleted_numbers}, f)
    
    return f"{new_number:04d}"

def get_next_invoice_number():
    """Genera y gestiona la numeración automática de facturas"""
    try:
        with open('counter.json', 'r') as f:
            data = json.load(f)
            current_invoice = data.get('invoice_number', 999)
    except FileNotFoundError:
        current_invoice = 999

    new_number = current_invoice + 1
    
    with open('counter.json', 'w') as f:
        json.dump({
            'quote_number': data.get('quote_number', 999), 
            'invoice_number': new_number,
            'deleted_numbers': data.get('deleted_numbers', [])
        }, f)
    
    return f"F{new_number:04d}"

def registrar_actividad(accion, detalle):
    """Registra una actividad en el log de auditoría"""
    auditoria = Auditoria(
        usuario_id=current_user.id if current_user.is_authenticated else None,
        accion=accion,
        detalle=detalle,
        ip=request.remote_addr
    )
    db.session.add(auditoria)
    db.session.commit()

def crear_notificacion(usuario_id, tipo, titulo, mensaje):
    """Crea una nueva notificación"""
    notificacion = Notificacion(
        usuario_id=usuario_id,
        tipo=tipo,
        titulo=titulo,
        mensaje=mensaje
    )
    db.session.add(notificacion)
    db.session.commit()

# Decoradores personalizados
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'admin':
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Rutas de autenticación
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        username = request.form.get('username')
        password = request.form.get('password')
        remember = 'remember_me' in request.form
        
        user = Usuario.query.filter_by(username=username).first()
        if user and user.check_password(password):
            if not user.activo:
                flash('Tu cuenta está desactivada. Contacta al administrador.', 'error')
                return redirect(url_for('login'))
            
            login_user(user, remember=remember)
            user.ultima_conexion = datetime.utcnow()
            db.session.commit()
            
            registrar_actividad('login', f'Usuario {username} inició sesión')
            next_page = request.args.get('next')
            return redirect(next_page or url_for('index'))
        else:
            flash('Usuario o contraseña incorrectos.', 'error')
    
    return render_template('login.html')

@app.route('/logout')
@login_required
def logout():
    registrar_actividad('logout', f'Usuario {current_user.username} cerró sesión')
    logout_user()
    return redirect(url_for('login'))

# Rutas del Dashboard
@app.route('/')
@login_required
def index():
    """Página principal - Dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats')
@login_required
def get_stats():
    """Endpoint para estadísticas del dashboard"""
    try:
        total_cotizaciones = Cotizacion.query.count()
        cotizaciones_empresa = Cotizacion.query.filter_by(tipo='empresa').count()
        cotizaciones_personal = Cotizacion.query.filter_by(tipo='natural').count()
        cotizaciones_aprobadas = Cotizacion.query.filter_by(estado='aprobada').count()
        cotizaciones_rechazadas = Cotizacion.query.filter_by(estado='rechazada').count()
        total_facturas = Factura.query.count()
        total_ventas = db.session.query(func.sum(Factura.total)).scalar() or 0
        total_clientes = db.session.query(func.count(Factura.cotizacion_id.distinct())).scalar()
        facturas_pendientes = Factura.query.filter_by(estado='pendiente').count()
        
        return jsonify({
            'total_ventas': float(total_ventas),
            'total_cotizaciones': total_cotizaciones,
            'total_facturas': total_facturas,
            'cotizaciones_empresa': cotizaciones_empresa,
            'cotizaciones_personal': cotizaciones_personal,
            'cotizaciones_aprobadas': cotizaciones_aprobadas,
            'cotizaciones_rechazadas': cotizaciones_rechazadas,
            'total_clientes': total_clientes,
            'facturas_pendientes': facturas_pendientes
        })
    except Exception as e:
        return jsonify({'error': str(e)}), 500

# Rutas de facturas
@app.route('/api/buscar_facturas')
@login_required
def buscar_facturas_api():
    query = request.args.get('query', '').strip()
    estado = request.args.get('estado', 'todos')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    # Iniciar la consulta base
    base_query = Factura.query.join(Cotizacion)
    
    # Aplicar filtros
    if query:
        base_query = base_query.filter(
            db.or_(
                Factura.numero.ilike(f'%{query}%'),
                Cotizacion.nombre.ilike(f'%{query}%')
            )
        )
    
    if estado != 'todos':
        base_query = base_query.filter(Factura.estado == estado)
    
    if fecha_inicio and fecha_fin:
        base_query = base_query.filter(
            Factura.fecha.between(fecha_inicio, fecha_fin)
        )
    
    # Obtener resultados
    facturas = base_query.order_by(Factura.fecha.desc()).all()
    
    # Convertir a formato JSON
    return jsonify([{
        'numero': f.numero,
        'cliente_nombre': f.cotizacion.nombre if f.cotizacion else 'N/A',
        'fecha': f.fecha.strftime('%d/%m/%Y'),
        'total': float(f.total),
        'estado': f.estado,
        'cotizacion_numero': f.cotizacion.numero if f.cotizacion else None
    } for f in facturas])

@app.route('/facturas')
@login_required
def facturas():
    """Lista todas las facturas"""
    facturas = Factura.query.order_by(Factura.fecha.desc()).all()
    return render_template('facturas.html', facturas=facturas)

@app.route('/ver_factura/<numero>')
@login_required
def ver_factura(numero):
    """Ver detalles de una factura específica"""
    factura = Factura.query.filter_by(numero=numero).first_or_404()
    return render_template('ver_factura.html', factura=factura)

@app.route('/descargar_factura/<numero>')
@login_required
def descargar_factura(numero):
    """Descargar una factura en formato PDF"""
    factura = Factura.query.filter_by(numero=numero).first_or_404()
    
    # Renderizar el template HTML
    html = render_template('plantilla_factura_pdf.html', factura=factura)
    
    # Convertir HTML a PDF
    pdf = HTML(string=html).write_pdf()
    
    # Preparar el archivo para descarga
    pdf_buffer = BytesIO(pdf)
    pdf_buffer.seek(0)
    
    return send_file(
        pdf_buffer,
        mimetype='application/pdf',
        as_attachment=True,
        download_name=f'Factura_{factura.numero}.pdf'
    )

@app.route('/marcar_pagada/<numero>', methods=['POST'])
@login_required
def marcar_factura_pagada(numero):
    """Marcar una factura como pagada"""
    try:
        factura = Factura.query.filter_by(numero=numero).first_or_404()
        
        if factura.estado == 'anulada':
            return jsonify({'error': 'No se puede marcar como pagada una factura anulada'}), 400
            
        if factura.estado == 'pagada':
            return jsonify({'error': 'La factura ya está marcada como pagada'}), 400
        
        factura.estado = 'pagada'
        factura.fecha_pago = datetime.utcnow()
        factura.modificado_por = current_user.username
        
        db.session.commit()
        
        registrar_actividad(
            'marcar_pagada',
            f'Factura {numero} marcada como pagada por {current_user.username}'
        )
        
        return jsonify({
            'success': True,
            'message': 'Factura marcada como pagada exitosamente'
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Rutas de notificaciones
@app.route('/api/notificaciones')
@login_required
def get_notificaciones():
    """Obtiene las notificaciones del usuario actual"""
    notificaciones = Notificacion.query.filter_by(
        usuario_id=current_user.id,
        leida=False
    ).order_by(Notificacion.fecha.desc()).all()
    
    return jsonify([{
        'id': n.id,
        'tipo': n.tipo,
        'titulo': n.titulo,
        'mensaje': n.mensaje,
        'fecha': n.fecha.strftime('%Y-%m-%d %H:%M:%S')
    } for n in notificaciones])

@app.route('/api/notificaciones/marcar_leida/<int:id>', methods=['POST'])
@login_required
def marcar_notificacion_leida(id):
    """Marca una notificación como leída"""
    notificacion = Notificacion.query.get_or_404(id)
    if notificacion.usuario_id != current_user.id:
        return jsonify({'error': 'No autorizado'}), 403
    
    notificacion.leida = True
    db.session.commit()
    return jsonify({'success': True})

# Rutas de cotizaciones
@app.route('/select')
@login_required
def cotizaciones():
    return render_template('select_type.html')

@app.route('/nueva_cotizacion')
@login_required
def nueva_cotizacion():
    return render_template('nueva_cotizacion.html')

@app.route('/select_type')
@login_required
def select_type():
    return render_template('select_type.html')

@app.route('/formulario_empresa')
@login_required
def formulario_empresa():
    return render_template('formulario_empresa.html')

@app.route('/formulario_natural')
@login_required
def formulario_natural():
    return render_template('formulario_natural.html')

@app.route('/buscar')
@login_required
def buscar():
    return render_template('buscar.html')

@app.route('/ver/<numero>')
@login_required
def ver_cotizacion(numero):
    cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
    return render_template('ver_cotizacion.html', cotizacion=cotizacion)

@app.route('/generate-pdf-empresa', methods=['POST'])
@login_required
def generate_pdf_empresa():
    data = request.form
    items = zip(data.getlist('descripcion[]'), data.getlist('pu[]'), data.getlist('unidades[]'), data.getlist('total[]'))
    items = [{'descripcion': d, 'precio_unitario': float(p), 'unidades': int(u), 'total': float(t)} for d, p, u, t in items]
    
    numero_cotizacion = get_next_quote_number()
    subtotal = sum(item['total'] for item in items)
    itbms = subtotal * 0.07
    total = subtotal * 1.07
    
    # Guardar cotización en la base de datos
    nueva_cotizacion = Cotizacion(
        numero=numero_cotizacion,
        tipo='empresa',
        nombre=data['nombre'],
        empresa=data['empresa'],
        ubicacion=data['ubicacion'],
        telefono=data['telefono'],
        fecha=datetime.now(),
        subtotal=subtotal,
        itbms=itbms,
        total=total,
        items=json.dumps(items)
    )
    db.session.add(nueva_cotizacion)
    db.session.commit()
    
    html = render_template('plantilla_pdf.html', 
                           nombre=data['nombre'], 
                           empresa=data['empresa'], 
                           ubicacion=data['ubicacion'], 
                           telefono=data['telefono'], 
                           items=items,
                           subtotal=subtotal,
                           itbms=itbms,
                           total=total,
                           fecha=datetime.now().strftime('%d/%m/%Y'),
                           numero_cotizacion=numero_cotizacion)
    
    pdf = HTML(string=html).write_pdf()
    return send_file(BytesIO(pdf), 
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"{data['nombre']}_{numero_cotizacion}.pdf")

@app.route('/generate-pdf-natural', methods=['POST'])
@login_required
def generate_pdf_natural():
    data = request.form
    items = zip(data.getlist('descripcion[]'), data.getlist('pu[]'), data.getlist('unidades[]'), data.getlist('total[]'))
    items = [{'descripcion': d, 'precio_unitario': float(p), 'unidades': int(u), 'total': float(t)} for d, p, u, t in items]
    
    numero_cotizacion = get_next_quote_number()
    subtotal = sum(item['total'] for item in items)
    itbms = subtotal * 0.07
    total = subtotal * 1.07
    
    # Guardar cotización en la base de datos
    nueva_cotizacion = Cotizacion(
        numero=numero_cotizacion,
        tipo='natural',
        nombre=data['nombre'],
        ubicacion=data['ubicacion'],
        telefono=data['telefono'],
        fecha=datetime.now(),
        subtotal=subtotal,
        itbms=itbms,
        total=total,
        items=json.dumps(items)
    )
    db.session.add(nueva_cotizacion)
    db.session.commit()
    
    html = render_template('plantilla_pdf_natural.html', 
                           nombre=data['nombre'], 
                           ubicacion=data['ubicacion'], 
                           telefono=data['telefono'], 
                           items=items,
                           subtotal=subtotal,
                           itbms=itbms,
                           total=total,
                           fecha=datetime.now().strftime('%d/%m/%Y'),
                           numero_cotizacion=numero_cotizacion)
    
    pdf = HTML(string=html).write_pdf()
    return send_file(BytesIO(pdf), 
                    mimetype='application/pdf',
                    as_attachment=True,
                    download_name=f"{data['nombre']}_{numero_cotizacion}.pdf")

@app.route('/exportar_excel')
@login_required
def exportar_excel():
    """Exporta datos a Excel"""
    tipo = request.args.get('tipo', 'cotizaciones')
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    if tipo == 'cotizaciones':
        query = Cotizacion.query
    else:
        query = Factura.query
    
    if fecha_inicio and fecha_fin:
        query = query.filter(
            Cotizacion.fecha.between(fecha_inicio, fecha_fin)
        )
    
    data = [item.to_dict() for item in query.all()]
    df = pd.DataFrame(data)
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        df.to_excel(writer, index=False)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'reporte_{tipo}_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/buscar_ajax')
@login_required
def buscar_ajax():
    query = request.args.get('query', '')
    tipo = request.args.get('tipo', 'todos')
    
    cotizaciones = Cotizacion.query.filter(
        (Cotizacion.nombre.ilike(f'%{query}%')) | 
        (Cotizacion.numero.ilike(f'%{query}%'))
    )
    
    if tipo != 'todos':
        cotizaciones = cotizaciones.filter_by(tipo=tipo)
    
    cotizaciones = cotizaciones.all()
    
    return jsonify([cotizacion.to_dict() for cotizacion in cotizaciones])

@app.route('/generar_reporte_ventas')
@login_required
def generar_reporte_ventas():
    fecha_inicio = request.args.get('fecha_inicio')
    fecha_fin = request.args.get('fecha_fin')
    
    query = Factura.query.order_by(Factura.fecha.desc())
    
    if fecha_inicio and fecha_fin:
        query = query.filter(Factura.fecha.between(fecha_inicio, fecha_fin))
    
    facturas = query.all()
    
    output = BytesIO()
    with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
        # Convertir a dataframe
        data = [{
            'Fecha': f.fecha,
            'Número': f.numero,
            'Cliente': f.cotizacion.nombre,
            'Subtotal': f.subtotal,
            'ITBMS': f.itbms,
            'Total': f.total,
            'Estado': f.estado
        } for f in facturas]
        
        df = pd.DataFrame(data)
        df.to_excel(writer, sheet_name='Ventas', index=False)
        
        # Generar hoja de resumen
        resumen = pd.DataFrame({
            'Métrica': ['Total Facturas', 'Total Ventas', 'Promedio por Factura'],
            'Valor': [
                len(facturas), 
                df['Total'].sum(), 
                df['Total'].mean()
            ]
        })
        resumen.to_excel(writer, sheet_name='Resumen', index=False)
    
    output.seek(0)
    
    return send_file(
        output,
        mimetype='application/vnd.openxmlformats-officedocument.spreadsheetml.sheet',
        as_attachment=True,
        download_name=f'reporte_ventas_{datetime.now().strftime("%Y%m%d")}.xlsx'
    )

@app.route('/generar_factura/<numero_cotizacion>', methods=['POST'])
@login_required
def generar_factura(numero_cotizacion):
    """Genera una nueva factura a partir de una cotización"""
    try:
        cotizacion = Cotizacion.query.filter_by(numero=numero_cotizacion).first_or_404()
        
        if cotizacion.estado == 'facturada':
            return jsonify({'error': 'Esta cotización ya ha sido facturada'}), 400

        # Generar nueva factura
        numero_factura = get_next_invoice_number()
        factura = Factura(
            numero=numero_factura,
            cotizacion_id=cotizacion.id,
            subtotal=cotizacion.subtotal,
            itbms=cotizacion.itbms,
            total=cotizacion.total,
            estado='emitida',
            creado_por='sistema'
        )
        
        # Actualizar estado de la cotización
        cotizacion.estado = 'facturada'
        cotizacion.fecha_facturacion = datetime.utcnow()
        cotizacion.numero_factura = numero_factura
        
        db.session.add(factura)
        db.session.commit()
        
        return jsonify({
            'success': True,
            'message': 'Factura generada exitosamente',
            'numero_factura': numero_factura
        })
        
    except Exception as e:
        db.session.rollback()
        return jsonify({'error': str(e)}), 500

# Manejo de Errores
@app.errorhandler(404)
def page_not_found(e):
    return render_template('errores/404.html'), 404

@app.errorhandler(500)
def internal_server_error(e):
    return render_template('errores/500.html'), 500

# Ruta de cierre
def shutdown_server():
    func = request.environ.get('werkzeug.server.shutdown')
    if func is None:
        raise RuntimeError('Not running with the Werkzeug Server')
    func()

@app.route('/shutdown', methods=['POST'])
@login_required
@admin_required
def shutdown():
    shutdown_server()
    return 'Servidor detenido...'

# Inicialización de la aplicación
if __name__ == '__main__':
    # Inicializar base de datos si es necesario
    with app.app_context():
        db.create_all()
        # Apply migrations
        upgrade()  # Use the upgrade function

    # Configurar modo de depuración
    app.run(debug=True, port=5000)