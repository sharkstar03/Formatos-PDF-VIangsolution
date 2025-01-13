from app import app, db

def reset_db():
    with app.app_context():
        # Drop all tables
        db.drop_all()
        # Create all tables
        db.create_all()
        print("Base de datos reiniciada exitosamente")

if __name__ == '__main__':
    reset_db()