# Importaciones - aquí está el cambio principal
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify, flash, session, abort
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate, upgrade
from flask_login import LoginManager, UserMixin, login_user, login_required, logout_user, current_user
from weasyprint import HTML
import os
from io import BytesIO
from datetime import datetime, timedelta
import json
from sqlalchemy import extract, func
import pandas as pd
from models import db  # Primero importamos solo db
import logging
from functools import wraps

app = Flask(__name__)
app.config['SECRET_KEY'] = 'tu_clave_secreta_muy_segura'  # Cambia esto en producción
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cotizaciones.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'pdfs')
app.config['BACKUP_FOLDER'] = os.path.join(app.static_folder, 'backups')

# Configuración de logging
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('app.log'),
        logging.StreamHandler()
    ]
)

# Asegurar que existan las carpetas necesarias
for folder in [app.config['UPLOAD_FOLDER'], app.config['BACKUP_FOLDER']]:
    if not os.path.exists(folder):
        os.makedirs(folder)

# Inicializar las extensiones
db.init_app(app)

# Ahora importamos los modelos
from models import Usuario, Cotizacion, Factura, Auditoria, Backup, Notificacion

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
        logging.info("Base de datos inicializada")

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
        data = {'quote_number': 999, 'deleted_numbers': []}

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
    try:
        auditoria = Auditoria(
            usuario_id=current_user.id if current_user.is_authenticated else None,
            accion=accion,
            detalle=detalle,
            ip=request.remote_addr
        )
        db.session.add(auditoria)
        db.session.commit()
        logging.info(f"Actividad registrada: {accion} - {detalle}")
    except Exception as e:
        logging.error(f"Error al registrar actividad: {e}")
        db.session.rollback()

def crear_notificacion(usuario_id, tipo, titulo, mensaje):
    """Crea una nueva notificación"""
    try:
        notificacion = Notificacion(
            usuario_id=usuario_id,
            tipo=tipo,
            titulo=titulo,
            mensaje=mensaje
        )
        db.session.add(notificacion)
        db.session.commit()
        logging.info(f"Notificación creada para usuario {usuario_id}: {titulo}")
    except Exception as e:
        logging.error(f"Error al crear notificación: {e}")
        db.session.rollback()

# Decoradores personalizados
def admin_required(f):
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if not current_user.is_authenticated or current_user.rol != 'admin':
            flash('No tienes permisos para acceder a esta página.', 'error')
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function

# Rutas principales
@app.route('/')
@login_required
def index():
    """Página principal - Dashboard"""
    return render_template('dashboard.html')

@app.route('/api/stats')
@login_required
def get_stats():
    """Endpoint para estadísticas del dashboard con mejor manejo de errores"""
    try:
        # Optimizar consultas usando una sola transacción
        stats = db.session.query(
            func.count(Cotizacion.id).label('total_cotizaciones'),
            func.count(func.case([(Cotizacion.tipo == 'empresa', 1)])).label('cotizaciones_empresa'),
            func.count(func.case([(Cotizacion.tipo == 'natural', 1)])).label('cotizaciones_personal'),
            func.count(func.case([(Cotizacion.estado == 'facturada', 1)])).label('cotizaciones_facturadas')
        ).first()

        factura_stats = db.session.query(
            func.count(Factura.id).label('total_facturas'),
            func.sum(func.case([(Factura.estado == 'pagada', Factura.total)], else_=0)).label('total_pagado'),
            func.sum(func.case([(Factura.estado == 'pendiente', Factura.total)], else_=0)).label('total_pendiente'),
            func.count(func.distinct(Factura.cotizacion_id)).label('total_clientes'),
            func.count(func.case([(Factura.estado == 'pendiente', 1)])).label('facturas_pendientes'),
            func.count(func.case([(Factura.estado == 'pagada', 1)])).label('facturas_pagadas')
        ).first()

        return jsonify({
            'total_ventas': float(factura_stats.total_pagado or 0),
            'ventas_pendientes': float(factura_stats.total_pendiente or 0),
            'total_cotizaciones': stats.total_cotizaciones,
            'total_facturas': factura_stats.total_facturas,
            'cotizaciones_empresa': stats.cotizaciones_empresa,
            'cotizaciones_personal': stats.cotizaciones_personal,
            'cotizaciones_facturadas': stats.cotizaciones_facturadas,
            'total_clientes': factura_stats.total_clientes,
            'facturas_pendientes': factura_stats.facturas_pendientes,
            'facturas_pagadas': factura_stats.facturas_pagadas
        })
    except Exception as e:
        logging.error(f'Error fetching stats: {e}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/buscar_facturas')
@login_required
def buscar_facturas_api():
    """API mejorada para búsqueda de facturas"""
    try:
        query = request.args.get('query', '').strip()
        estado = request.args.get('estado', 'todos').lower()
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        logging.info(f'Búsqueda de facturas - Parámetros: query={query}, estado={estado}, fecha_inicio={fecha_inicio}, fecha_fin={fecha_fin}')
        
        # Consulta optimizada con joins
        base_query = Factura.query.join(
            Cotizacion,
            Factura.cotizacion_id == Cotizacion.id,
            isouter=True
        ).options(db.joinedload(Factura.cotizacion))
        
        # Filtros
        if query:
            base_query = base_query.filter(
                db.or_(
                    Factura.numero.ilike(f'%{query}%'),
                    Cotizacion.nombre.ilike(f'%{query}%')
                )
            )
        
        if estado != 'todos' and estado != 'all':
            base_query = base_query.filter(Factura.estado == estado)
        
        if fecha_inicio and fecha_fin:  # Corrected logical operator
            try:
                fecha_inicio = datetime.strptime(fecha_inicio, '%Y-%m-%d')
                fecha_fin = datetime.strptime(fecha_fin, '%Y-%m-%d')
                base_query = base_query.filter(
                    Factura.fecha.between(fecha_inicio, fecha_fin)
                )
            except ValueError as e:
                logging.error(f'Error en formato de fechas: {str(e)}')
                return jsonify({'error': 'Formato de fecha inválido'}), 400
        
        facturas = base_query.order_by(Factura.fecha.desc()).all()
        
        # Convertir a JSON con manejo de errores
        resultados = []
        for factura in facturas:
            try:
                resultados.append({
                    'numero': factura.numero,
                    'cliente_nombre': factura.cotizacion.nombre if factura.cotizacion else 'Sin cliente',
                    'fecha': factura.fecha.strftime('%d/%m/%Y'),
                    'total': float(factura.total) if factura.total is not None else 0.0,
                    'estado': factura.estado,
                    'cotizacion_numero': factura.cotizacion.numero if factura.cotizacion else None
                })
            except Exception as e:
                logging.error(f'Error procesando factura {factura.numero}: {str(e)}')
                continue
        
        return jsonify(resultados)
    except Exception as e:
        logging.error(f'Error en búsqueda de facturas: {str(e)}')
        return jsonify({'error': 'Error interno del servidor'}), 500

@app.route('/facturas')
@login_required
def facturas():
    """Vista de facturas optimizada"""
    try:
        # Usar una sola consulta para obtener estadísticas
        stats = db.session.query(
            func.sum(Factura.total).label('total_ventas'),
            func.count(func.case([(Factura.estado == 'pendiente', 1)])).label('facturas_pendientes')
        ).first()

        facturas = Factura.query.order_by(Factura.fecha.desc()).all()

        return render_template(
            'facturas.html',
            total_ventas=float(stats.total_ventas or 0),
            facturas_pendientes=stats.facturas_pendientes,
            facturas=facturas
        )
    except Exception as e:
        logging.error(f'Error al cargar facturas: {str(e)}')
        flash('Error al cargar las facturas.', 'error')
        return render_template('facturas.html', total_ventas=0, facturas_pendientes=0, facturas=[])

@app.route('/ver_factura/<numero>')
@login_required
def ver_factura(numero):
    """Ver detalles de una factura específica"""
    try:
        factura = Factura.query.filter_by(numero=numero).first_or_404()
        return render_template('ver_factura.html', factura=factura)
    except Exception as e:
        logging.error(f'Error al ver factura {numero}: {str(e)}')
        flash('Error al cargar la factura.', 'error')
        return redirect(url_for('facturas'))

@app.route('/descargar_factura/<numero>')
@login_required
def descargar_factura(numero):
    """Descargar una factura en formato PDF"""
    try:
        factura = Factura.query.filter_by(numero=numero).first_or_404()
        html = render_template('plantilla_factura_pdf.html', factura=factura)
        pdf = HTML(string=html).write_pdf()
        pdf_buffer = BytesIO(pdf)
        pdf_buffer.seek(0)
        
        return send_file(
            pdf_buffer,
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f'Factura_{factura.numero}.pdf'
        )
    except Exception as e:
        logging.error(f'Error al descargar factura {numero}: {str(e)}')
        flash('Error al generar el PDF.', 'error')
        return redirect(url_for('facturas'))

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
        logging.error(f'Error al marcar factura {numero} como pagada: {str(e)}')
        return jsonify({'error': str(e)}), 500

# Continuación del manejo de errores
@app.errorhandler(500)
def internal_server_error(e):
    logging.error(f'Error interno del servidor: {str(e)}')
    return redirect(url_for('index'))

# Rutas de autenticación
@app.route('/login', methods=['GET', 'POST'])
def login():
    if request.method == 'POST':
        try:
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
        except Exception as e:
            logging.error(f'Error en login: {str(e)}')
            flash('Error al iniciar sesión.', 'error')
    
    notificaciones = get_notificaciones().json if get_notificaciones().status_code == 200 else []
    return render_template('login.html', notificaciones=notificaciones)

@app.route('/logout')
@login_required
def logout():
    try:
        registrar_actividad('logout', f'Usuario {current_user.username} cerró sesión')
        logout_user()
        return redirect(url_for('login'))
    except Exception as e:
        logging.error(f'Error en logout: {str(e)}')
        return redirect(url_for('index'))

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
    try:
        cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
        return render_template('ver_cotizacion.html', cotizacion=cotizacion)
    except Exception as e:
        logging.error(f'Error al ver cotización {numero}: {str(e)}')
        flash('Error al cargar la cotización.', 'error')
        return redirect(url_for('buscar'))

@app.route('/aprobar_cotizacion/<numero>', methods=['POST'])
@login_required
def aprobar_cotizacion(numero):
    """Aprobar cotización y generar factura"""
    try:
        # Obtener la cotización
        cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
        
        # Verificar si ya está facturada
        if cotizacion.estado == 'facturada':
            return jsonify({
                'error': 'Esta cotización ya ha sido facturada'
            }), 400

        # Generar número de factura
        numero_factura = get_next_invoice_number()
        
        # Crear nueva factura
        nueva_factura = Factura(
            numero=numero_factura,
            cotizacion_id=cotizacion.id,
            subtotal=cotizacion.subtotal,
            itbms=cotizacion.itbms,
            total=cotizacion.total,
            estado='pendiente',
            usuario_id=current_user.id,
            creado_por=current_user.username
        )
        
        # Actualizar estado de la cotización
        cotizacion.estado = 'facturada'
        cotizacion.fecha_facturacion = datetime.utcnow()
        cotizacion.numero_factura = numero_factura
        
        # Guardar cambios
        db.session.add(nueva_factura)
        db.session.commit()
        
        # Registrar la actividad
        registrar_actividad(
            'generar_factura',
            f'Factura {numero_factura} generada de cotización {numero} por {current_user.username}'
        )
        
        return jsonify({
            'success': True,
            'message': 'Cotización aprobada y factura generada exitosamente',
            'numero_factura': numero_factura
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al aprobar cotización {numero}: {str(e)}')
        return jsonify({
            'error': f'Error al aprobar la cotización: {str(e)}'
        }), 500

@app.route('/rechazar_cotizacion/<numero>', methods=['POST'])
@login_required
def rechazar_cotizacion(numero):
    try:
        cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
        cotizacion.estado = 'rechazada'
        cotizacion.fecha_rechazo = datetime.utcnow()
        cotizacion.rechazado_por = current_user.username
        db.session.commit()
        
        registrar_actividad('rechazar_cotizacion', 
                          f'Cotización {numero} rechazada por {current_user.username}')
        
        return redirect(url_for('buscar'))
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al rechazar cotización {numero}: {str(e)}')
        flash('Error al rechazar la cotización.', 'error')
        return redirect(url_for('buscar'))

@app.route('/eliminar/<numero>', methods=['POST'])
@login_required
def eliminar_cotizacion(numero):
    try:
        cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
        
        # Guardar el número eliminado para reutilización
        try:
            with open('counter.json', 'r') as f:
                data = json.load(f)
        except FileNotFoundError:
            data = {'quote_number': 999, 'deleted_numbers': []}
        
        if 'deleted_numbers' not in data:
            data['deleted_numbers'] = []
        
        data['deleted_numbers'].append(int(cotizacion.numero))
        data['deleted_numbers'].sort()
        
        with open('counter.json', 'w') as f:
            json.dump(data, f)
        
        db.session.delete(cotizacion)
        db.session.commit()
        
        registrar_actividad('eliminar_cotizacion', 
                          f'Cotización {numero} eliminada por {current_user.username}')
        
        return redirect(url_for('buscar'))
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al eliminar cotización {numero}: {str(e)}')
        flash('Error al eliminar la cotización.', 'error')
        return redirect(url_for('buscar'))

@app.route('/reimprimir/<numero>')
@login_required
def reimprimir_cotizacion(numero):
    try:
        cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
        template = 'plantilla_pdf.html' if cotizacion.tipo == 'empresa' else 'plantilla_pdf_natural.html'
        
        html = render_template(template, 
                             nombre=cotizacion.nombre,
                             empresa=cotizacion.empresa,
                             ubicacion=cotizacion.ubicacion,
                             telefono=cotizacion.telefono,
                             items=json.loads(cotizacion.items),
                             subtotal=cotizacion.subtotal,
                             itbms=cotizacion.itbms,
                             total=cotizacion.total,
                             fecha=cotizacion.fecha.strftime('%d/%m/%Y'),
                             numero_cotizacion=cotizacion.numero)
        
        # Agregar base_url aquí también
        pdf = HTML(string=html, base_url=request.url_root).write_pdf()
        
        return send_file(
            BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"Cotizacion_{cotizacion.numero}.pdf"
        )
    except Exception as e:
        logging.error(f'Error al reimprimir cotización {numero}: {str(e)}')
        flash('Error al generar el PDF.', 'error')
        return redirect(url_for('buscar'))

@app.route('/generate-pdf-empresa', methods=['POST'])
@login_required
def generate_pdf_empresa():
    try:
        data = request.form
        items = zip(
            data.getlist('descripcion[]'),
            data.getlist('pu[]'),
            data.getlist('unidades[]'),
            data.getlist('total[]')
        )
        items = [{
            'descripcion': d,
            'precio_unitario': float(p),
            'unidades': int(u),
            'total': float(t)
        } for d, p, u, t in items]
        
        numero_cotizacion = get_next_quote_number()
        subtotal = sum(item['total'] for item in items)
        
        # Check if ITBMS is enabled
        itbms_enabled = 'toggle_itbms' in data
        itbms = subtotal * 0.07 if itbms_enabled else 0
        total = subtotal + itbms
        
        # Guardar cotización en la base de datos
        nueva_cotizacion = Cotizacion(
            numero=numero_cotizacion,
            tipo='empresa',
            nombre=data['nombre'],
            empresa=data['empresa'],
            ubicacion=data['ubicacion'],
            telefono=data['telefono'],
            ruc=data['ruc'] if 'toggle_ruc_dv' in data else None,
            dv=data['dv'] if 'toggle_ruc_dv' in data else None,
            fecha=datetime.now(),
            subtotal=subtotal,
            itbms=itbms if itbms_enabled else None,
            total=total,
            items=json.dumps(items),
            creado_por=current_user.username
        )
        
        db.session.add(nueva_cotizacion)
        db.session.commit()
        
        registrar_actividad('crear_cotizacion', 
                          f'Cotización empresa {numero_cotizacion} creada por {current_user.username}')
        
        # Obtener rutas absolutas de las imágenes
        watermark_path = os.path.join(app.static_folder, 'watermark.png')
        logo_path = os.path.join(app.static_folder, 'logo.png')
        yappy_path = os.path.join(app.static_folder, 'yappy.png')
        
        html = render_template('plantilla_pdf.html',
                             nombre=data['nombre'],
                             empresa=data['empresa'],
                             ubicacion=data['ubicacion'],
                             telefono=data['telefono'],
                             ruc=data['ruc'] if 'toggle_ruc_dv' in data else None,
                             dv=data['dv'] if 'toggle_ruc_dv' in data else None,
                             items=items,
                             subtotal=subtotal,
                             itbms=itbms if itbms_enabled else None,
                             total=total,
                             fecha=datetime.now().strftime('%d/%m/%Y'),
                             numero_cotizacion=numero_cotizacion,
                             watermark_path=watermark_path,
                             logo_path=logo_path,
                             yappy_path=yappy_path)
        
        # Usar base_url para que WeasyPrint encuentre las imágenes
        pdf = HTML(string=html, base_url=os.path.dirname(app.static_folder)).write_pdf()
        
        return send_file(
            BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{data['nombre']}_{numero_cotizacion}.pdf"
        )
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al generar PDF empresa: {str(e)}')
        return jsonify({'error': str(e)}), 500
    
@app.route('/generate-pdf-natural', methods=['POST'])
@login_required
def generate_pdf_natural():
    try:
        data = request.form
        items = zip(
            data.getlist('descripcion[]'),
            data.getlist('pu[]'),
            data.getlist('unidades[]'),
            data.getlist('total[]')
        )
        items = [{
            'descripcion': d,
            'precio_unitario': float(p),
            'unidades': int(u),
            'total': float(t)
        } for d, p, u, t in items]
        
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
            items=json.dumps(items),
            creado_por=current_user.username
        )
        
        db.session.add(nueva_cotizacion)
        db.session.commit()
        
        registrar_actividad('crear_cotizacion', 
                          f'Cotización natural {numero_cotizacion} creada por {current_user.username}')
        
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
        
        # Agregar base_url aquí también
        pdf = HTML(string=html, base_url=request.url_root).write_pdf()
        
        return send_file(
            BytesIO(pdf),
            mimetype='application/pdf',
            as_attachment=True,
            download_name=f"{data['nombre']}_{numero_cotizacion}.pdf"
        )
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al generar PDF natural: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/exportar_excel')
@login_required
def exportar_excel():
    """Exporta datos a Excel"""
    try:
        tipo = request.args.get('tipo', 'cotizaciones')
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        if tipo == 'cotizaciones':
            query = Cotizacion.query
        else:
            query = Factura.query
        
        if fecha_inicio and fecha_fin:  # Corrected logical operator
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
    except Exception as e:
        logging.error(f'Error al exportar a Excel: {str(e)}')
        flash('Error al generar el archivo Excel.', 'error')
        return redirect(url_for('index'))

@app.route('/buscar_ajax')
@login_required
def buscar_ajax():
    try:
        query = request.args.get('query', '')
        tipo = request.args.get('tipo', 'todos')
        
        base_query = Cotizacion.query.filter(
            db.or_(
                Cotizacion.nombre.ilike(f'%{query}%'),
                Cotizacion.numero.ilike(f'%{query}%')
            )
        )
        
        if tipo != 'todos':
            base_query = base_query.filter_by(tipo=tipo)
        
        cotizaciones = base_query.all()
        
        return jsonify([cotizacion.to_dict() for cotizacion in cotizaciones])
    except Exception as e:
        logging.error(f'Error en búsqueda ajax: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/generar_reporte_ventas')
@login_required
def generar_reporte_ventas():
    try:
        fecha_inicio = request.args.get('fecha_inicio')
        fecha_fin = request.args.get('fecha_fin')
        
        query = Factura.query.options(db.joinedload(Factura.cotizacion)).order_by(Factura.fecha.desc())
        
        if fecha_inicio and fecha_fin:  # Corrected logical operator
            query = query.filter(Factura.fecha.between(fecha_inicio, fecha_fin))
        
        facturas = query.all()
        
        output = BytesIO()
        with pd.ExcelWriter(output, engine='xlsxwriter') as writer:
            # Convertir a dataframe
            data = [{
                'Fecha': f.fecha,
                'Número': f.numero,
                'Cliente': f.cotizacion.nombre if f.cotizacion else 'Sin cliente',
                'Subtotal': float(f.subtotal) if f.subtotal else 0.0,
                'ITBMS': float(f.itbms) if f.itbms else 0.0,
                'Total': float(f.total) if f.total else 0.0,
                'Estado': f.estado
            } for f in facturas]
            
            df = pd.DataFrame(data)
            df.to_excel(writer, sheet_name='Ventas', index=False)
            
            # Generar hoja de resumen
            resumen = pd.DataFrame({
                'Métrica': [
                    'Total Facturas',
                    'Total Ventas',
                    'Promedio por Factura',
                    'Facturas Pendientes',
                    'Facturas Pagadas',
                    'Facturas Anuladas'
                ],
                'Valor': [
                    len(facturas),
                    df['Total'].sum(),
                    df['Total'].mean(),
                    len([f for f in facturas if f.estado == 'pendiente']),
                    len([f for f in facturas if f.estado == 'pagada']),
                    len([f for f in facturas if f.estado == 'anulada'])
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
    except Exception as e:
        logging.error(f'Error al generar reporte de ventas: {str(e)}')
        flash('Error al generar el reporte de ventas.', 'error')
        return redirect(url_for('facturas'))

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
            estado='pendiente',
            creado_por=current_user.username,
            fecha=datetime.utcnow()
        )
        
        # Actualizar estado de la cotización
        cotizacion.estado = 'facturada'
        cotizacion.fecha_facturacion = datetime.utcnow()
        cotizacion.numero_factura = numero_factura
        
        db.session.add(factura)
        db.session.commit()
        
        registrar_actividad(
            'generar_factura',
            f'Factura {numero_factura} generada de cotización {numero_cotizacion} por {current_user.username}'
        )
        
        return jsonify({
            'success': True,
            'message': 'Factura generada exitosamente',
            'numero_factura': numero_factura
        })
        
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al generar factura de cotización {numero_cotizacion}: {str(e)}')
        return jsonify({'error': str(e)}), 500

# Rutas de notificaciones
@app.route('/api/notificaciones')
@login_required
def get_notificaciones():
    """Obtiene las notificaciones del usuario actual"""
    try:
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
    except Exception as e:
        logging.error(f'Error al obtener notificaciones: {str(e)}')
        return jsonify({'error': str(e)}), 500

@app.route('/api/notificaciones/marcar_leida/<int:id>', methods=['POST'])
@login_required
def marcar_notificacion_leida(id):
    """Marca una notificación como leída"""
    try:
        notificacion = Notificacion.query.get_or_404(id)
        if notificacion.usuario_id != current_user.id:
            return jsonify({'error': 'No autorizado'}), 403
        
        notificacion.leida = True
        notificacion.fecha_lectura = datetime.utcnow()
        db.session.commit()
        
        return jsonify({'success': True})
    except Exception as e:
        db.session.rollback()
        logging.error(f'Error al marcar notificación {id} como leída: {str(e)}')
        return jsonify({'error': str(e)}), 500

# Inicialización de la aplicación
if __name__ == '__main__':
    # Configurar el logging
    logging.basicConfig(
        filename='app.log',
        level=logging.DEBUG,
        format='%(asctime)s %(levelname)s: %(message)s'
    )

    # Inicializar base de datos si es necesario
    with app.app_context():
        try:
            db.create_all()
            # Aplicar migraciones
            upgrade()
            logging.info("Base de datos inicializada correctamente")
        except Exception as e:
            logging.error(f"Error al inicializar la base de datos: {str(e)}")
    
    # Configuraciones adicionales de seguridad
    app.config['REMEMBER_COOKIE_SECURE'] = True
    app.config['REMEMBER_COOKIE_HTTPONLY'] = True
    app.config['SESSION_COOKIE_SECURE'] = True
    app.config['PERMANENT_SESSION_LIFETIME'] = timedelta(hours=24)
    
    # Ensure the cryptography library is installed
    try:
        from cryptography import x509
    except ImportError:
        logging.error("The 'cryptography' library is required for SSL. Install it using 'pip install cryptography'.")
        exit(1)

    # Iniciar el servidor
    app.run(
        host='0.0.0.0',
        port=5000,
        debug=False,  # Desactivar debug en producción
        ssl_context='adhoc'  # Activar HTTPS
    )