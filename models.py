from datetime import datetime
from extensions import db


class LoginAluno(db.Model):
    __tablename__ = 'login_aluno'
    cp = db.Column(db.String(9), primary_key=True)
    nome = db.Column(db.String(100), nullable=False)
    email = db.Column(db.String(150), unique=True, nullable=False)
    senha_hash = db.Column(db.String(255), nullable=False)
    foto_url = db.Column(db.String(255), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relacionamentos
    perguntas = db.relationship('Pergunta', backref='aluno', lazy=True)
    respostas = db.relationship('Resposta', backref='aluno', lazy=True)
    uploads = db.relationship('Upload', foreign_keys='Upload.cp', backref='aluno', lazy=True)

    @property
    def role(self):
        return 'aluno'

    @property
    def name(self):
        return self.nome

class LoginProfessor(db.Model):
    __tablename__ = 'login_professor'
    email_p = db.Column(db.String(150), primary_key=True)
    nome_p = db.Column(db.String(100), nullable=False)
    senha_hash_p = db.Column(db.String(255), nullable=False)
    foto_url = db.Column(db.String(255), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    atualizado_em = db.Column(db.DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    uploads = db.relationship('Upload', foreign_keys='Upload.email_p', backref='professor', lazy=True)

    @property
    def role(self):
        return 'professor'

    @property
    def name(self):
        return self.nome_p

    @property
    def email(self):
        return self.email_p


class Pergunta(db.Model):
    __tablename__ = 'perguntas'
    id_pergunta = db.Column(db.Integer, primary_key=True, autoincrement=True)  # FIX: db.Int → db.Integer
    titulo = db.Column(db.String(60), nullable=False)
    descricao = db.Column(db.String(500), nullable=False)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=False)
    curso = db.Column(db.String(100))
    semestre = db.Column(db.String(5))
    disciplina = db.Column(db.String(100))
    aceita_id = db.Column(db.Integer, db.ForeignKey('respostas.id_r'), nullable=True)
    oculta = db.Column(db.Boolean, default=False)
    postado_em = db.Column(db.DateTime, default=datetime.utcnow)

    respostas = db.relationship(
        'Resposta',
        foreign_keys='Resposta.id_pergunta',
        backref='pergunta',
        lazy=True,
    )
    comentarios = db.relationship('Comentario', backref='pergunta', lazy=True)
    tags = db.relationship('Tag', secondary='pergunta_tags', backref='perguntas', lazy=True)
    uploads = db.relationship('Upload', foreign_keys='Upload.id_pergunta', backref='pergunta', lazy=True)


class Resposta(db.Model):
    __tablename__ = 'respostas'
    id_r = db.Column(db.Integer, primary_key=True, autoincrement=True)  # FIX: db.Int → db.Integer
    conteudo = db.Column(db.String(500), nullable=False)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=False)
    id_pergunta = db.Column(db.Integer, db.ForeignKey('perguntas.id_pergunta'))
    enviado_em = db.Column(db.DateTime, default=datetime.utcnow)

    comentarios = db.relationship('Comentario', backref='resposta', lazy=True)
    uploads = db.relationship('Upload', foreign_keys='Upload.id_r', backref='resposta', lazy=True)


class Comentario(db.Model):
    __tablename__ = 'comentarios'
    id_c = db.Column(db.Integer, primary_key=True, autoincrement=True)
    conteudo = db.Column(db.String(500), nullable=False)
    email_p = db.Column(db.String(150), db.ForeignKey('login_professor.email_p'), nullable=True)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=True)
    id_pergunta = db.Column(db.Integer, db.ForeignKey('perguntas.id_pergunta'), nullable=True)
    id_r = db.Column(db.Integer, db.ForeignKey('respostas.id_r'), nullable=True)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
    uploads = db.relationship('Upload', foreign_keys='Upload.id_c', backref='comentario', lazy=True)


class Voto(db.Model):
    __tablename__ = 'votos'
    id_v = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=True)
    email_p = db.Column(db.String(150), db.ForeignKey('login_professor.email_p'), nullable=True)
    id_r = db.Column(db.Integer, db.ForeignKey('respostas.id_r'), nullable=True)
    id_pergunta = db.Column(db.Integer, db.ForeignKey('perguntas.id_pergunta'), nullable=True)
    tipo = db.Column(db.Enum('positivo', 'negativo'), nullable=False)


class Tag(db.Model):
    __tablename__ = 'tags'
    id_t = db.Column(db.Integer, primary_key=True, autoincrement=True)
    nome_tag = db.Column(db.String(50), unique=True, nullable=False)  # FIX: db.Sring → db.String


class PerguntaTag(db.Model):
    __tablename__ = 'pergunta_tags'
    id_pergunta = db.Column(db.Integer, db.ForeignKey('perguntas.id_pergunta'), primary_key=True)
    id_t = db.Column(db.Integer, db.ForeignKey('tags.id_t'), primary_key=True)


class ReputacaoHistorico(db.Model):
    __tablename__ = 'reputacao_historico'
    id_rh = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=False)
    pontos = db.Column(db.Integer, nullable=False)  # FIX: db.Int → db.Integer
    motivo = db.Column(db.String(50))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Notificacao(db.Model):
    __tablename__ = 'notificacoes'
    id_n = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=True)
    email_p = db.Column(db.String(150), db.ForeignKey('login_professor.email_p'), nullable=True)
    mensagem = db.Column(db.String(300), nullable=False)
    lida = db.Column(db.Boolean, default=False)
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Denuncia(db.Model):
    __tablename__ = 'denuncias'
    id_d = db.Column(db.Integer, primary_key=True, autoincrement=True)
    tipo_alvo = db.Column(db.String(20), nullable=False)  # 'pergunta' ou 'resposta'
    id_pergunta = db.Column(db.Integer, db.ForeignKey('perguntas.id_pergunta'), nullable=True)
    id_r = db.Column(db.Integer, db.ForeignKey('respostas.id_r'), nullable=True)
    cp_autor = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=True)
    motivo = db.Column(db.String(200))
    status = db.Column(db.Enum('aberta', 'resolvida'), default='aberta')
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)


class Upload(db.Model):
    __tablename__ = 'uploads'
    id_up = db.Column(db.Integer, primary_key=True, autoincrement=True)
    cp = db.Column(db.String(9), db.ForeignKey('login_aluno.cp'), nullable=True)
    email_p = db.Column(db.String(150), db.ForeignKey('login_professor.email_p'), nullable=True)
    id_pergunta = db.Column(db.Integer, db.ForeignKey('perguntas.id_pergunta'), nullable=True)
    id_r = db.Column(db.Integer, db.ForeignKey('respostas.id_r'), nullable=True)
    id_c = db.Column(db.Integer, db.ForeignKey('comentarios.id_c'), nullable=True)
    url_arquivo = db.Column(db.String(255), nullable=False)
    tipo = db.Column(db.String(100))
    criado_em = db.Column(db.DateTime, default=datetime.utcnow)
