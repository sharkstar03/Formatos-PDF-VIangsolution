# app.py
from flask import Flask, render_template, request, send_file, redirect, url_for, jsonify
from weasyprint import HTML
import os
from io import BytesIO
from datetime import datetime
import json
from flask_sqlalchemy import SQLAlchemy
from sqlalchemy import extract
from werkzeug.utils import secure_filename
from models import db, Cotizacion

app = Flask(__name__)
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///cotizaciones.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join(app.static_folder, 'pdfs')

# Crear carpeta para PDFs si no existe
if not os.path.exists(app.config['UPLOAD_FOLDER']):
    os.makedirs(app.config['UPLOAD_FOLDER'])
    print(f"Carpeta de PDFs creada en: {app.config['UPLOAD_FOLDER']}")

db.init_app(app)

def init_db():
    """Inicializa la base de datos"""
    with app.app_context():
        db.drop_all()
        db.create_all()
        print("Base de datos inicializada")

# Inicializar la base de datos
init_db()

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
        print("Archivo counter.json no encontrado, iniciando desde 999")
    
    if deleted_numbers:
        new_number = deleted_numbers.pop(0)
    else:
        new_number = current_number + 1
    
    with open('counter.json', 'w') as f:
        json.dump({'quote_number': new_number, 'deleted_numbers': deleted_numbers}, f)
    
    print(f"Generando número de cotización: {new_number:04d}")
    return f"{new_number:04d}"

def limpiar_nombre_archivo(nombre):
    """Limpia el nombre para que sea válido como nombre de archivo"""
    nombre_limpio = nombre.replace(' ', '_')
    nombre_limpio = ''.join(c for c in nombre_limpio if c.isalnum() or c in '_-')
    return nombre_limpio.lower()[:50]

def save_pdf(pdf_file, nombre, numero):
    """Guarda el PDF en el sistema de archivos"""
    filename = secure_filename(f'{nombre}_{numero}.pdf')
    filepath = os.path.join(app.config['UPLOAD_FOLDER'], filename)
    print(f"Guardando PDF en: {filepath}")
    try:
        with open(filepath, 'wb') as f:
            f.write(pdf_file.getvalue())
        print(f"PDF guardado exitosamente en {filepath}")
        return filepath
    except Exception as e:
        print(f"Error guardando PDF: {str(e)}")
        raise

@app.route('/')
def index():
    """Página principal con estadísticas"""
    total_cotizaciones = Cotizacion.query.count()
    cotizaciones_empresa = Cotizacion.query.filter_by(tipo='empresa').count()
    cotizaciones_personal = Cotizacion.query.filter_by(tipo='natural').count()
    
    mes_actual = datetime.now().month
    año_actual = datetime.now().year
    cotizaciones_mes = Cotizacion.query.filter(
        extract('month', Cotizacion.fecha) == mes_actual,
        extract('year', Cotizacion.fecha) == año_actual
    ).count()
    
    print(f"Estadísticas - Total: {total_cotizaciones}, Empresas: {cotizaciones_empresa}, Personal: {cotizaciones_personal}, Mes actual: {cotizaciones_mes}")
    
    return render_template('select_type.html',
                         total_cotizaciones=total_cotizaciones,
                         cotizaciones_empresa=cotizaciones_empresa,
                         cotizaciones_personal=cotizaciones_personal,
                         cotizaciones_mes=cotizaciones_mes)

@app.route('/formulario_empresa')
def formulario_empresa():
    """Formulario para cotizaciones empresariales"""
    return render_template('formulario_empresa.html')

@app.route('/formulario_natural')
def formulario_natural():
    """Formulario para cotizaciones personales"""
    return render_template('formulario_natural.html')

@app.route('/buscar')
def buscar():
    """Página de búsqueda de cotizaciones"""
    cotizaciones = Cotizacion.query.all()
    print(f"Total de cotizaciones en la base de datos: {len(cotizaciones)}")
    for c in cotizaciones:
        print(f"Cotización #{c.numero} - {c.nombre} - PDF: {c.pdf_path}")
    return render_template('buscar.html')

@app.route('/buscar_ajax')
def buscar_ajax():
    """Búsqueda en tiempo real de cotizaciones"""
    query = request.args.get('query', '')
    tipo = request.args.get('tipo', 'todos')
    page = request.args.get('page', 1, type=int)
    per_page = 10
    
    base_query = Cotizacion.query
    
    if tipo != 'todos':
        base_query = base_query.filter_by(tipo=tipo)
    
    cotizaciones = base_query.filter(
        db.or_(
            Cotizacion.nombre.ilike(f'%{query}%'),
            Cotizacion.numero.ilike(f'%{query}%')
        )
    ).order_by(Cotizacion.fecha.desc()).paginate(
        page=page, per_page=per_page, error_out=False)
    
    resultados = [{
        'numero': c.numero,
        'nombre': c.nombre,
        'tipo': c.tipo,
        'fecha': c.fecha.strftime('%d/%m/%Y'),
        'total': f"${c.total:.2f}"
    } for c in cotizaciones.items]
    
    return jsonify(resultados)

@app.route('/ver/<numero>')
def ver_cotizacion(numero):
    cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
    return render_template('ver_cotizacion.html', cotizacion=cotizacion)

@app.route('/reimprimir/<numero>')
def reimprimir_cotizacion(numero):
    cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
    if cotizacion.pdf_path and os.path.exists(cotizacion.pdf_path):
        return send_file(cotizacion.pdf_path, mimetype='application/pdf')
    return "PDF no encontrado", 404

@app.route('/eliminar/<numero>')
def eliminar_cotizacion(numero):
    cotizacion = Cotizacion.query.filter_by(numero=numero).first_or_404()
    
    if cotizacion.pdf_path and os.path.exists(cotizacion.pdf_path):
        os.remove(cotizacion.pdf_path)
    
    db.session.delete(cotizacion)
    db.session.commit()
    
    try:
        with open('counter.json', 'r') as f:
            data = json.load(f)
            deleted_numbers = data.get('deleted_numbers', [])
    except FileNotFoundError:
        deleted_numbers = []
    
    deleted_numbers.append(int(numero))
    
    with open('counter.json', 'w') as f:
        json.dump({'quote_number': data.get('quote_number', 999), 'deleted_numbers': deleted_numbers}, f)
    
    return redirect(url_for('buscar'))

@app.route('/generate-pdf-empresa', methods=['POST'])
def generate_pdf_empresa():
    """Genera PDF para cotizaciones empresariales"""
    try:
        print("Iniciando generación de PDF empresarial")
        nombre = request.form['nombre']
        empresa = request.form['empresa']
        ubicacion = request.form['ubicacion']
        telefono = request.form['telefono']
        
        descripciones = request.form.getlist('descripcion[]')
        precios_unitarios = request.form.getlist('pu[]')
        unidades = request.form.getlist('unidades[]')
        totales = request.form.getlist('total[]')
        
        print(f"Items recibidos: {len(descripciones)}")
        
        items = []
        for i in range(len(descripciones)):
            items.append({
                'descripcion': descripciones[i],
                'precio_unitario': float(precios_unitarios[i]),
                'unidades': int(unidades[i]),
                'total': float(totales[i])
            })
        
        subtotal = sum(float(total) for total in totales)
        itbms = subtotal * 0.07
        total = subtotal + itbms
        
        numero_cotizacion = get_next_quote_number()
        print(f"Nuevo número de cotización: {numero_cotizacion}")
        
        cotizacion = Cotizacion(
            numero=numero_cotizacion,
            tipo='empresa',
            nombre=nombre,
            empresa=empresa,
            ubicacion=ubicacion,
            telefono=telefono,
            subtotal=subtotal,
            itbms=itbms,
            total=total
        )
        cotizacion.set_items(items)
        
        print("Generando HTML del PDF")
        rendered_html = render_template('plantilla_pdf.html',
                                      nombre=nombre,
                                      empresa=empresa,
                                      ubicacion=ubicacion,
                                      telefono=telefono,
                                      items=items,
                                      subtotal=subtotal,
                                      itbms=itbms,
                                      total=total,
                                      fecha=datetime.now().strftime("%d de %B de %Y"),
                                      numero_cotizacion=numero_cotizacion)
        
        print("Generando PDF")
        pdf_file = BytesIO()
        HTML(string=rendered_html, base_url=request.url_root).write_pdf(pdf_file)
        pdf_file.seek(0)
        
        # Guardar el PDF
        pdf_path = save_pdf(pdf_file, nombre, numero_cotizacion)
        cotizacion.pdf_path = pdf_path
        
        print("Guardando en base de datos")
        db.session.add(cotizacion)
        db.session.commit()
        
        print(f"PDF generado y guardado exitosamente: {pdf_path}")
        
        # Crear una nueva copia del BytesIO para enviar
        pdf_file.seek(0)
        return send_file(pdf_file,
                        as_attachment=True,
                        download_name=f'{nombre}_{numero_cotizacion}.pdf',
                        mimetype='application/pdf')
                        
    except Exception as e:
        print(f"Error en generate_pdf_empresa: {str(e)}")
        import traceback
        traceback.print_exc()
        return jsonify({'error': str(e)}), 500

@app.route('/generate-pdf-natural', methods=['POST'])
def generate_pdf_natural():
    """Genera PDF para cotizaciones personales"""
    try:
        print("Iniciando generación de PDF personal")
        nombre = request.form['nombre']
        ubicacion = request.form['ubicacion']
        telefono = request.form['telefono']
        
        descripciones = request.form.getlist('descripcion[]')
        precios_unitarios = request.form.getlist('pu[]')
        unidades = request.form.getlist('unidades[]')
        totales = request.form.getlist('total[]')
        
        print(f"Items recibidos: {len(descripciones)}")
        
        items = []
        for i in range(len(descripciones)):
            items.append({
                'descripcion': descripciones[i],
                'precio_unitario': float(precios_unitarios[i]),
                'unidades': int(unidades[i]),
                'total': float(totales[i])
            })
        
        subtotal = sum(float(total) for total in totales)
        itbms = subtotal * 0.07
        total = subtotal + itbms
        
        numero_cotizacion = get_next_quote_number()
        print(f"Nuevo número de cotización: {numero_cotizacion}")
        
        cotizacion = Cotizacion(
            numero=numero_cotizacion,
            tipo='natural',
            nombre=nombre,
            ubicacion=ubicacion,
            telefono=telefono,
            subtotal=subtotal,
            itbms=itbms,
            total=total
        )
        cotizacion.set_items(items)
        
        print("Generando HTML del PDF")
        rendered_html = render_template('plantilla_pdf_natural.html',
                                      nombre=nombre,
                                      ubicacion=ubicacion,
                                      telefono=telefono,
                                      items=items,
                                      subtotal=subtotal,
                                      itbms=itbms,
                                      total=total,
                                      fecha=datetime.now().strftime("%d de %B de %Y"),
                                      numero_cotizacion=numero_cotizacion)
        
        pdf_file = BytesIO()
        HTML(string=rendered_html, base_url=request.url_root).write_pdf(pdf_file)
        pdf_file.seek(0)
        
        # Guardar el PDF
        pdf_path = save_pdf(pdf_file, nombre, numero_cotizacion)
        cotizacion.pdf_path = pdf_path
        
        db.session.add(cotizacion)
        db.session.commit()
        
        # Crear una nueva copia del BytesIO para enviar
        pdf_file.seek(0)
        return send_file(pdf_file,
                        as_attachment=True,
                        download_name=f'{nombre}_{numero_cotizacion}.pdf',
                        mimetype='application/pdf')
    except Exception as e:
        return jsonify({'error': str(e)}), 500

if __name__ == '__main__':
    app.run(debug=True)