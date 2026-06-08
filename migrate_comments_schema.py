from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    statements = [
        'ALTER TABLE comentarios ADD COLUMN cp VARCHAR(9) NULL;',
        'ALTER TABLE comentarios MODIFY COLUMN email_p VARCHAR(150) NULL;',
        'ALTER TABLE comentarios ADD CONSTRAINT fk_comentario_aluno FOREIGN KEY (cp) REFERENCES login_aluno(cp) ON DELETE CASCADE;'
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