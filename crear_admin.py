from app import app, db
from models import Usuario

def crear_admin():
    with app.app_context():
        # Verificar si ya existe un admin
        admin_existente = Usuario.query.filter_by(username='admin').first()
        
        if not admin_existente:
            admin = Usuario(
                username='admin',
                email='admin@example.com',
                nombre_completo='Administrador',
                rol='admin',
                activo=True
            )
            admin.set_password('admin123')  # ¡Cambia esta contraseña!
            
            db.session.add(admin)
            db.session.commit()
            print("Usuario administrador creado exitosamente")
        else:
            print("El usuario administrador ya existe")

if __name__ == '__main__':
    crear_admin()