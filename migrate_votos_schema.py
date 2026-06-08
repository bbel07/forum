from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    statements = [
        'ALTER TABLE votos ADD COLUMN cp VARCHAR(9) NULL;',
        'ALTER TABLE votos ADD COLUMN id_pergunta INT NULL;',
        'ALTER TABLE votos ADD CONSTRAINT fk_voto_pergunta FOREIGN KEY (id_pergunta) REFERENCES perguntas(id_pergunta) ON DELETE CASCADE;',
        'ALTER TABLE votos ADD CONSTRAINT fk_voto_aluno FOREIGN KEY (cp) REFERENCES login_aluno(cp) ON DELETE CASCADE;'
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
