"""
Funções de negócio — sem rotas, sem render_template.
Importadas pelos blueprints e pelo app.py.
"""
from datetime import datetime, timedelta
import os
import re
import uuid
from pathlib import Path
from flask import session, current_app
from werkzeug.utils import secure_filename
from extensions import db
from models import (
    LoginAluno, LoginProfessor, Pergunta, Resposta,
    Comentario, Voto, Denuncia, Notificacao, ReputacaoHistorico, Upload,
)


# ---------------------------------------------------------------------------
# Helpers gerais
# ---------------------------------------------------------------------------

def now_iso():
    return datetime.now().isoformat(timespec="seconds")


def format_date(value):
    if isinstance(value, datetime):
        return value.strftime("%d/%m/%Y %H:%M")
    try:
        return datetime.fromisoformat(value).strftime("%d/%m/%Y %H:%M")
    except (ValueError, TypeError):
        return value


def hash_password(password: str) -> str:
    """Hash simples para demonstração — substitua por bcrypt em produção."""
    return password[::-1]

ALLOWED_IMAGE_EXTENSIONS = {'png', 'jpg', 'jpeg', 'gif', 'webp'}
BAD_WORDS = {
    'burro', 'idiota', 'otario', 'otário', 'fdp', 'porra', 'pqp',
    'caralho', 'merda', 'puta', 'buceta', 'cu', 'foda', 'filhodaputa',
    'filho da puta', 'vaca', 'otária', 'viado', 'viado', 'bicha', 'buceta',
}


def is_allowed_image(filename: str) -> bool:
    return '.' in filename and filename.rsplit('.', 1)[1].lower() in ALLOWED_IMAGE_EXTENSIONS


def normalize_text(value: str) -> str:
    return re.sub(r'[^a-z0-9]', '', value.lower())


def contains_profanity(text: str) -> bool:
    if not text:
        return False
    normalized = normalize_text(text)
    plain = re.sub(r'[^a-z0-9 ]', '', text.lower())
    for bad in BAD_WORDS:
        key = normalize_text(bad)
        if key and (key in normalized or key in plain.replace(' ', '')):
            return True
    return False


def save_upload(file, cp=None, email_p=None, id_pergunta=None, id_r=None, id_c=None, tipo='attachment'):
    if not file or not hasattr(file, 'filename') or not file.filename:
        return None
    filename = secure_filename(file.filename)
    if not is_allowed_image(filename):
        return None

    uploads_dir = Path(current_app.root_path) / 'static' / 'uploads'
    uploads_dir.mkdir(parents=True, exist_ok=True)
    unique_name = f"{datetime.utcnow().strftime('%Y%m%d%H%M%S')}_{uuid.uuid4().hex}_{filename}"
    path = uploads_dir / unique_name
    file.save(path)
    relative_path = f"uploads/{unique_name}"
    upload = Upload(
        cp=cp,
        email_p=email_p,
        id_pergunta=id_pergunta,
        id_r=id_r,
        id_c=id_c,
        url_arquivo=relative_path,
        tipo=tipo,
    )
    db.session.add(upload)
    return upload


def validate_text_field(label: str, text: str):
    if not text or not text.strip():
        return False, f"{label} não pode ficar vazio."
    if contains_profanity(text):
        return False, f"{label} contém linguagem imprópria. Por favor, reformule sem xingamentos."
    return True, ""


def is_strong_password(password: str) -> bool:
    return (
        len(password) >= 8
        and any(c.isalpha() for c in password)
        and any(c.isdigit() for c in password)
    )


# ---------------------------------------------------------------------------
# Usuário logado
# ---------------------------------------------------------------------------

def get_current_user():
    """Retorna LoginAluno ou LoginProfessor, ou None."""
    user_id = session.get("user_id")
    if not user_id:
        return None
    return LoginAluno.query.get(user_id) or LoginProfessor.query.get(user_id)


def is_aluno(user) -> bool:
    return isinstance(user, LoginAluno)


# ---------------------------------------------------------------------------
# Enriquecimento de perguntas para os templates
# ---------------------------------------------------------------------------

def enrich_question(pergunta: Pergunta) -> Pergunta:
    """Adiciona atributos auxiliares que os templates precisam."""
    autor = LoginAluno.query.get(pergunta.cp)
    pergunta.author_name = autor.nome if autor else "Usuário desconhecido"
    pergunta.answer_count = Resposta.query.filter_by(id_pergunta=pergunta.id_pergunta).count()
    # Aliases para compatibilidade com o template
    pergunta.id = pergunta.id_pergunta
    pergunta.title = pergunta.titulo
    pergunta.description = pergunta.descricao
    pergunta.course = pergunta.curso
    pergunta.votes = Voto.query.filter_by(id_pergunta=pergunta.id_pergunta).count()
    pergunta.created_at = pergunta.postado_em
    pergunta.comments = Comentario.query.filter_by(id_pergunta=pergunta.id_pergunta, id_r=None).all()
    pergunta.answers = Resposta.query.filter_by(id_pergunta=pergunta.id_pergunta).all()
    for c in pergunta.comments:
        c.created_at = c.criado_em
        c.content = c.conteudo
        autor_c = LoginAluno.query.get(c.cp) if c.cp else None
        c.author_name = autor_c.nome if autor_c else "Usuário desconhecido"
    for r in pergunta.answers:
        r.id = r.id_r
        r.content = r.conteudo
        r.created_at = r.enviado_em
        r.votes = Voto.query.filter_by(id_r=r.id_r).count()
        r.is_accepted = (pergunta.aceita_id == r.id_r)
        autor_r = LoginAluno.query.get(r.cp) if r.cp else None
        r.author_name = autor_r.nome if autor_r else "Usuário desconhecido"
        r.comments = Comentario.query.filter_by(id_r=r.id_r).all()
        for c in r.comments:
            c.created_at = c.criado_em
            c.content = c.conteudo
            autor_c = LoginAluno.query.get(c.cp) if c.cp else None
            c.author_name = autor_c.nome if autor_c else "Usuário desconhecido"
    return pergunta


def get_metrics() -> dict:
    """Métricas reais do banco para o cabeçalho do feed."""
    return {
        "users": LoginAluno.query.count() + LoginProfessor.query.count(),
        "questions": Pergunta.query.count(),
        "answers": Resposta.query.count(),
        "reports": Denuncia.query.filter_by(status="aberta").count(),
    }


def is_user_blocked(user) -> bool:
    return bool(getattr(user, "bloqueado_ate", None) and user.bloqueado_ate > datetime.utcnow())


def get_observed_students():
    agora = datetime.utcnow()
    return LoginAluno.query.filter(LoginAluno.bloqueado_ate != None, LoginAluno.bloqueado_ate > agora).all()


def observar_aluno(cp: str, minutos: int = 30):
    aluno = LoginAluno.query.get(cp)
    if not aluno:
        return False, "Aluno não encontrado."

    agora = datetime.utcnow()
    if aluno.bloqueado_ate and aluno.bloqueado_ate > agora:
        aluno.bloqueado_ate += timedelta(minutes=minutos)
    else:
        aluno.bloqueado_ate = agora + timedelta(minutes=minutos)

    try:
        db.session.commit()
        return True, f"Aluno em observação até {format_date(aluno.bloqueado_ate)}."
    except Exception:
        db.session.rollback()
        return False, "Erro ao colocar aluno em observação."


# ---------------------------------------------------------------------------
# Autenticação
# ---------------------------------------------------------------------------

def fazer_login(email: str, senha: str, role: str):
    """
    Tenta autenticar e salva user_id na session.
    Retorna (True, mensagem) ou (False, mensagem).
    """
    if role == "student":
        user = LoginAluno.query.filter_by(email=email).first()
        hash_db = getattr(user, "senha_hash", None)
        user_id = getattr(user, "cp", None)
    else:
        user = LoginProfessor.query.filter_by(email_p=email).first()
        hash_db = getattr(user, "senha_hash_p", None)
        user_id = getattr(user, "email_p", None)

    if not user:
        return False, "Usuário não encontrado."
    if hash_db != hash_password(senha):
        return False, "E-mail ou senha incorretos."
    if role == "student" and is_user_blocked(user):
        return False, f"Aluno em observação até {format_date(user.bloqueado_ate)}."

    session["user_id"] = user_id
    return True, "Bem-vindo!"


def cadastrar_aluno(form: dict):
    email = form.get("email", "").strip()
    cp = form.get("cp", "").strip()
    senha = form.get("password", "")

    if not email.endswith("@aluno.ifsp.edu.br"):
        return False, "O cadastro de aluno exige e-mail @aluno.ifsp.edu.br."
    if not is_strong_password(senha):
        return False, "A senha precisa ter ao menos 8 caracteres, letra e número."

    novo = LoginAluno(
        cp=cp,
        nome=form.get("name", "").strip(),
        email=email,
        senha_hash=hash_password(senha),
    )
    try:
        db.session.add(novo)
        db.session.commit()
        return True, "Aluno cadastrado com sucesso!"
    except Exception:
        db.session.rollback()
        return False, "Erro: CP ou e-mail já cadastrado."


def cadastrar_professor(form: dict):
    email = form.get("email", "").strip()
    senha = form.get("password", "")

    if not email.endswith("@ifsp.edu.br"):
        return False, "O cadastro de professor exige e-mail @ifsp.edu.br."
    if not is_strong_password(senha):
        return False, "A senha precisa ter ao menos 8 caracteres, letra e número."

    novo = LoginProfessor(
        email_p=email,
        nome_p=form.get("name", "").strip(),
        senha_hash_p=hash_password(senha),
    )
    try:
        db.session.add(novo)
        db.session.commit()
        return True, "Professor cadastrado com sucesso!"
    except Exception:
        db.session.rollback()
        return False, "Erro ao cadastrar professor. E-mail já em uso."


# ---------------------------------------------------------------------------
# Perguntas
# ---------------------------------------------------------------------------

def criar_pergunta(form: dict):
    user_id = session.get("user_id")
    if not user_id:
        return False, "Entre na plataforma antes de publicar."

    if not LoginAluno.query.get(user_id):
        return False, "Apenas alunos podem publicar perguntas."

    titulo = form.get("title", "").strip()
    descricao = form.get("description", "").strip()
    valid, message = validate_text_field("Título", titulo)
    if not valid:
        return False, message
    valid, message = validate_text_field("Descrição", descricao)
    if not valid:
        return False, message

    nova = Pergunta(
        titulo=titulo,
        descricao=descricao,
        cp=user_id,
        curso=form.get("course", ""),
        semestre=form.get("semester", ""),
        disciplina=form.get("discipline", ""),
    )
    try:
        db.session.add(nova)
        db.session.commit()
        award_points(user_id, 12, "pergunta_criada")
        return True, "Pergunta publicada com sucesso!"
    except Exception:
        db.session.rollback()
        return False, "Erro ao salvar a pergunta. Tente novamente."


# ---------------------------------------------------------------------------
# Respostas
# ---------------------------------------------------------------------------

def criar_resposta(id_pergunta: int, conteudo: str):
    user_id = session.get("user_id")
    if not user_id:
        return False, "Faça login para responder."

    pergunta = Pergunta.query.get(id_pergunta)
    if not pergunta:
        return False, "Pergunta não encontrada."
    valid, message = validate_text_field("Resposta", conteudo)
    if not valid:
        return False, message

    nova = Resposta(conteudo=conteudo.strip(), cp=user_id, id_pergunta=id_pergunta)
    try:
        db.session.add(nova)
        db.session.commit()
        award_points(user_id, 10, "resposta_criada")
        notificar(pergunta.cp, f"Sua pergunta '{pergunta.titulo}' recebeu uma nova resposta.")
        return True, "Resposta publicada com sucesso!"
    except Exception:
        db.session.rollback()
        return False, "Erro ao salvar a resposta."


def aceitar_resposta(id_pergunta: int, id_r: int):
    user_id = session.get("user_id")
    pergunta = Pergunta.query.get(id_pergunta)
    if not pergunta:
        return False, "Pergunta não encontrada."
    if pergunta.cp != user_id:
        return False, "Somente o autor pode aceitar uma resposta."

    # Toggle: desmarcar se já estava aceita
    if pergunta.aceita_id == id_r:
        pergunta.aceita_id = None
    else:
        pergunta.aceita_id = id_r
        resposta = Resposta.query.get(id_r)
        if resposta:
            award_points(resposta.cp, 15, "resposta_aceita")
            notificar(resposta.cp, f"Sua resposta foi aceita em '{pergunta.titulo}'.")

    db.session.commit()
    return True, "Status da resposta atualizado."


# ---------------------------------------------------------------------------
# Comentários
# ---------------------------------------------------------------------------

def criar_comentario(id_pergunta: int, conteudo: str, id_r: int = None):
    user_id = session.get("user_id")
    user = get_current_user()
    if not user or not user_id:
        return False, "Faça login para comentar."
    valid, message = validate_text_field("Comentário", conteudo)
    if not valid:
        return False, message

    cp = user_id if is_aluno(user) else None
    email_p = user_id if not is_aluno(user) else None

    novo = Comentario(
        conteudo=conteudo.strip(),
        cp=cp,
        email_p=email_p,
        id_pergunta=id_pergunta,
        id_r=id_r,
    )
    try:
        db.session.add(novo)
        db.session.commit()
        return True, "Comentário adicionado."
    except Exception:
        db.session.rollback()
        return False, "Erro ao salvar o comentário."


# ---------------------------------------------------------------------------
# Votos
# ---------------------------------------------------------------------------

def votar(tipo_alvo: str, id_alvo: int, tipo_voto: str, id_pergunta: int = None):
    """tipo_alvo: 'pergunta' ou 'resposta'. tipo_voto: 'positivo' ou 'negativo'."""
    user_id = session.get("user_id")
    user = get_current_user()
    if not user:
        return False, "Faça login para votar."

    cp = user_id if is_aluno(user) else None
    email_p = user_id if not is_aluno(user) else None

    novo_voto = Voto(
        cp=cp,
        email_p=email_p,
        id_r=id_alvo if tipo_alvo == "resposta" else None,
        id_pergunta=id_alvo if tipo_alvo == "pergunta" else None,
        tipo=tipo_voto,
    )
    try:
        db.session.add(novo_voto)
        db.session.commit()
        return True, "Voto registrado."
    except Exception:
        db.session.rollback()
        return False, "Erro ao registrar voto."


# ---------------------------------------------------------------------------
# Denúncias
# ---------------------------------------------------------------------------

def criar_denuncia(tipo_alvo: str, id_alvo: int, motivo: str = ""):
    user_id = session.get("user_id")
    if not user_id:
        return False, "Faça login para denunciar."

    if tipo_alvo == "pergunta":
        pergunta = Pergunta.query.get(id_alvo)
        if pergunta and pergunta.cp:
            aluno = LoginAluno.query.get(pergunta.cp)
            if aluno and is_user_blocked(aluno):
                aluno.bloqueado_ate += timedelta(minutes=30)

    nova = Denuncia(
        tipo_alvo=tipo_alvo,
        id_pergunta=id_alvo if tipo_alvo == "pergunta" else None,
        id_r=id_alvo if tipo_alvo == "resposta" else None,
        cp_autor=user_id if isinstance(get_current_user(), LoginAluno) else None,
        motivo=motivo,
    )
    try:
        db.session.add(nova)
        db.session.commit()
        return True, "Denúncia registrada para revisão."
    except Exception:
        db.session.rollback()
        return False, "Erro ao registrar denúncia."


def resolver_denuncia(id_d: int):
    d = Denuncia.query.get(id_d)
    if not d:
        return False, "Denúncia não encontrada."
    d.status = "resolvida"
    db.session.commit()
    return True, "Denúncia resolvida."


# ---------------------------------------------------------------------------
# Moderação
# ---------------------------------------------------------------------------

def ocultar_pergunta(id_pergunta: int):
    pergunta = Pergunta.query.get(id_pergunta)
    if not pergunta:
        return False, "Pergunta não encontrada."
    pergunta.oculta = True
    db.session.commit()
    return True, "Pergunta ocultada."


def remover_resposta(id_r: int):
    resposta = Resposta.query.get(id_r)
    if not resposta:
        return False, "Resposta não encontrada."

    if resposta.pergunta and resposta.pergunta.aceita_id == id_r:
        resposta.pergunta.aceita_id = None

    Comentario.query.filter_by(id_r=id_r).delete(synchronize_session=False)
    Upload.query.filter_by(id_r=id_r).delete(synchronize_session=False)
    Voto.query.filter_by(id_r=id_r).delete(synchronize_session=False)
    db.session.delete(resposta)
    db.session.commit()
    return True, "Resposta removida."


def remover_comentario(id_c: int):
    comentario = Comentario.query.get(id_c)
    if not comentario:
        return False, "Comentário não encontrado."
    Upload.query.filter_by(id_c=id_c).delete(synchronize_session=False)
    db.session.delete(comentario)
    db.session.commit()
    return True, "Comentário removido."


def remover_pergunta(id_pergunta: int):
    pergunta = Pergunta.query.get(id_pergunta)
    if not pergunta:
        return False, "Pergunta não encontrada."

    answer_ids = [r.id_r for r in pergunta.respostas]
    comment_ids = [c.id_c for c in pergunta.comentarios]

    Voto.query.filter_by(id_pergunta=id_pergunta).delete(synchronize_session=False)
    Upload.query.filter_by(id_pergunta=id_pergunta).delete(synchronize_session=False)
    Comentario.query.filter_by(id_pergunta=id_pergunta).delete(synchronize_session=False)

    if answer_ids:
        Comentario.query.filter(Comentario.id_r.in_(answer_ids)).delete(synchronize_session=False)
        Upload.query.filter(Upload.id_r.in_(answer_ids)).delete(synchronize_session=False)
        Voto.query.filter(Voto.id_r.in_(answer_ids)).delete(synchronize_session=False)
        Resposta.query.filter(Resposta.id_r.in_(answer_ids)).delete(synchronize_session=False)

    if comment_ids:
        Upload.query.filter(Upload.id_c.in_(comment_ids)).delete(synchronize_session=False)

    db.session.delete(pergunta)
    db.session.commit()
    return True, "Pergunta removida."


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------

def atualizar_perfil(form: dict):
    user = get_current_user()
    if not user:
        return False, "Faça login para editar o perfil."

    if is_aluno(user):
        user.nome = form.get("name", "").strip()
        user.email = form.get("email", "").strip()
    else:
        user.nome_p = form.get("name", "").strip()

    try:
        db.session.commit()
        return True, "Perfil atualizado."
    except Exception:
        db.session.rollback()
        return False, "Erro ao atualizar. E-mail pode já estar em uso."


# ---------------------------------------------------------------------------
# Notificações e pontuação
# ---------------------------------------------------------------------------

def notificar(cp: str, mensagem: str):
    if not cp:
        return
    nova = Notificacao(cp=cp, mensagem=mensagem)
    db.session.add(nova)
    # não faz commit aqui — quem chamar notificar() deve commitar depois


def award_points(cp: str, pontos: int, motivo: str = ""):
    if not cp:
        return
    registro = ReputacaoHistorico(cp=cp, pontos=pontos, motivo=motivo)
    db.session.add(registro)
    # não faz commit aqui — quem chamar deve commitar depois