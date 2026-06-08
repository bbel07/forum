from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    statements = [
        'ALTER TABLE uploads ADD COLUMN id_c INT NULL;',
        'ALTER TABLE uploads ADD CONSTRAINT fk_comentario_upload FOREIGN KEY (id_c) REFERENCES comentarios(id_c) ON DELETE CASCADE;'
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
