from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    try:
        db.session.execute(text('ALTER TABLE login_aluno ADD COLUMN foto_url VARCHAR(255) NULL;'))
        db.session.commit()
        print('OK: coluna foto_url adicionada em login_aluno')
    except Exception as e:
        print('login_aluno já possui foto_url ou falha:')
        print(e)

    try:
        db.session.execute(text('ALTER TABLE login_professor ADD COLUMN foto_url VARCHAR(255) NULL;'))
        db.session.commit()
        print('OK: coluna foto_url adicionada em login_professor')
    except Exception as e:
        print('login_professor já possui foto_url ou falha:')
        print(e)
