from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    statements = [
        'ALTER TABLE login_aluno ADD COLUMN bloqueado_ate DATETIME NULL;'
    ]

    for stmt in statements:
        try:
            db.session.execute(text(stmt))
            db.session.commit()
            print(f'OK: {stmt}')
        except Exception as e:
            db.session.rollback()
            print(f'Falha no statement: {stmt}')
            print(e)
