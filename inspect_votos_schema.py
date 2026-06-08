from app import app
from extensions import db
from sqlalchemy import text

with app.app_context():
    conn = db.engine.connect()
    rs = conn.execute(text('SHOW COLUMNS FROM votos;'))
    print('COLUMNS in votos:')
    for row in rs:
        print(row)
    conn.close()
