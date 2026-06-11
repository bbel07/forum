"""
Blueprint: área do aluno
Prefixo: /aluno
"""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from models import LoginAluno, Pergunta, Resposta, Comentario, Notificacao
from services import (
    enrich_question, get_metrics, get_current_user, is_aluno, is_user_blocked, format_date,
    criar_pergunta, criar_resposta, criar_comentario,
    votar, criar_denuncia, aceitar_resposta, remover_pergunta,
    remover_resposta, remover_comentario, atualizar_perfil,
)

aluno_bp = Blueprint("aluno", __name__, url_prefix="/aluno")


# ---------------------------------------------------------------------------
# Decorator: exige login de aluno
# ---------------------------------------------------------------------------

def requer_aluno(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        user = LoginAluno.query.get(user_id) if user_id else None
        if not user:
            flash("Faça login como aluno para continuar.", "warning")
            return redirect(url_for("login"))
        if is_user_blocked(user):
            flash(f"Aluno em observação até {format_date(user.bloqueado_ate)}.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@aluno_bp.get("/feed")
@requer_aluno
def feed():
    from app import COURSE_CATALOG
    perguntas = Pergunta.query.filter_by(oculta=False)\
        .order_by(Pergunta.postado_em.desc()).all()
    perguntas = [enrich_question(p) for p in perguntas]
    return render_template(
        "feed.html",
        page_title="Feed do aluno",
        area_title="Área do aluno",
        area_subtitle="",
        questions=perguntas,
        metrics=get_metrics(),
        is_staff=False,
        base_path="aluno",
        filters=request.args,
        course_catalog=COURSE_CATALOG,
    )


@aluno_bp.get("/disciplinas/<path:disciplina>")
@requer_aluno
def disciplina_forum(disciplina):
    from app import COURSE_CATALOG

    perguntas = Pergunta.query.filter_by(oculta=False, disciplina=disciplina)
    perguntas = perguntas.order_by(Pergunta.postado_em.desc()).all()
    perguntas = [enrich_question(p) for p in perguntas]

    return render_template(
        "feed.html",
        page_title=f"Fórum - {disciplina}",
        area_title="Fórum da disciplina",
        area_subtitle=f"Perguntas sobre {disciplina}.",
        questions=perguntas,
        metrics=get_metrics(),
        is_staff=False,
        base_path="aluno",
        filters={"discipline": disciplina},
        course_catalog=COURSE_CATALOG,
        question_action_label="Perguntas e respostas",
    )


# ---------------------------------------------------------------------------
# Fórum (visualizar pergunta + respostas)
# ---------------------------------------------------------------------------

@aluno_bp.get("/forum/<int:id_pergunta>")
@requer_aluno
def forum(id_pergunta):
    pergunta = Pergunta.query.get_or_404(id_pergunta)
    user_id = session.get("user_id")
    respostas = Resposta.query.filter_by(id_pergunta=id_pergunta)\
        .order_by(Resposta.enviado_em.desc()).all()
    return render_template(
        "forum.html",
        page_title="Fórum",
        area_title="Fórum da comunidade",
        area_subtitle="Leia e participe da discussão.",
        question=enrich_question(pergunta),
        answers=respostas,
        base_path="aluno",
        is_staff=False,
        can_accept=False,
    )


# ---------------------------------------------------------------------------
# Nova pergunta
# ---------------------------------------------------------------------------

@aluno_bp.route("/pergunta/nova", methods=["GET", "POST"])
@requer_aluno
def nova_pergunta():
    from app import COURSE_CATALOG
    if request.method == "POST":
        ok, msg = criar_pergunta(request.form)
        flash(msg, "success" if ok else "warning")
        if ok:
            return redirect(url_for("aluno.feed"))
    return render_template(
        "question_form.html",
        page_title="Nova pergunta",
        area_title="Criar nova pergunta",
        area_subtitle="Formulário de publicação.",
        base_path="aluno",
        course_catalog=COURSE_CATALOG,
    )


# ---------------------------------------------------------------------------
# Ações POST do fórum
# ---------------------------------------------------------------------------

@aluno_bp.post("/forum/<int:id_pergunta>/resposta")
@requer_aluno
def post_resposta(id_pergunta):
    ok, msg = criar_resposta(id_pergunta, request.form.get("content", ""))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/comentario")
@requer_aluno
def post_comentario_pergunta(id_pergunta):
    ok, msg = criar_comentario(id_pergunta, request.form.get("content", ""))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/comentario")
@requer_aluno
def post_comentario_resposta(id_pergunta, id_r):
    ok, msg = criar_comentario(id_pergunta, request.form.get("content", ""), id_r=id_r)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/remover")
@requer_aluno
def post_remover_pergunta(id_pergunta):
    pergunta = Pergunta.query.get_or_404(id_pergunta)
    user = get_current_user()
    if not (user and is_aluno(user) and pergunta.cp == user.cp):
        flash("Você só pode excluir sua própria pergunta.", "warning")
        return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))

    ok, msg = remover_pergunta(id_pergunta)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.feed"))


@aluno_bp.post("/forum/<int:id_pergunta>/comentario/<int:id_c>/remover")
@requer_aluno
def post_remover_comentario_pergunta(id_pergunta, id_c):
    comentario = Comentario.query.get_or_404(id_c)
    user = get_current_user()
    if not (user and is_aluno(user) and comentario.cp == user.cp):
        flash("Você só pode excluir seu próprio comentário.", "warning")
        return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))

    ok, msg = remover_comentario(id_c)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.feed"))


@aluno_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/remover")
@requer_aluno
def post_remover_resposta(id_pergunta, id_r):
    resposta = Resposta.query.get_or_404(id_r)
    user = get_current_user()
    if not (user and is_aluno(user) and resposta.cp == user.cp):
        flash("Você só pode excluir sua própria resposta.", "warning")
        return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))

    ok, msg = remover_resposta(id_r)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.feed"))


@aluno_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/comentario/<int:id_c>/remover")
@requer_aluno
def post_remover_comentario_resposta(id_pergunta, id_r, id_c):
    comentario = Comentario.query.get_or_404(id_c)
    user = get_current_user()
    if not (user and is_aluno(user) and comentario.cp == user.cp):
        flash("Você só pode excluir seu próprio comentário.", "warning")
        return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))

    ok, msg = remover_comentario(id_c)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/votar")
@requer_aluno
def post_voto_pergunta(id_pergunta):
    tipo = request.form.get("tipo", "positivo")
    ok, msg = votar("pergunta", id_pergunta, tipo)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/votar")
@requer_aluno
def post_voto_resposta(id_pergunta, id_r):
    tipo = request.form.get("tipo", "positivo")
    ok, msg = votar("resposta", id_r, tipo, id_pergunta=id_pergunta)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/aceitar")
@requer_aluno
def post_aceitar_resposta(id_pergunta, id_r):
    ok, msg = aceitar_resposta(id_pergunta, id_r)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/denunciar")
@requer_aluno
def post_denuncia_pergunta(id_pergunta):
    ok, msg = criar_denuncia("pergunta", id_pergunta, request.form.get("motivo", ""))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


@aluno_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/denunciar")
@requer_aluno
def post_denuncia_resposta(id_pergunta, id_r):
    ok, msg = criar_denuncia("resposta", id_r, request.form.get("motivo", ""))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("aluno.forum", id_pergunta=id_pergunta))


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------

@aluno_bp.route("/perfil", methods=["GET", "POST"])
@requer_aluno
def perfil():
    user_id = session.get("user_id")
    user = LoginAluno.query.get(user_id)
    if request.method == "POST":
        ok, msg = atualizar_perfil(request.form)
        flash(msg, "success" if ok else "warning")
        return redirect(url_for("aluno.perfil"))

    total_perguntas = Pergunta.query.filter_by(cp=user_id).count()
    total_respostas = Resposta.query.filter_by(cp=user_id).count()
    return render_template(
        "profile.html",
        page_title="Perfil",
        area_title="Meu perfil",
        area_subtitle="Edite seus dados.",
        user=user,
        user_questions=total_perguntas,
        user_answers=total_respostas,
        base_path="aluno",
    )


# ---------------------------------------------------------------------------
# Notificações
# ---------------------------------------------------------------------------

@aluno_bp.get("/notificacoes")
@requer_aluno
def notificacoes():
    user_id = session.get("user_id")
    notifs = Notificacao.query.filter_by(cp=user_id)\
        .order_by(Notificacao.criado_em.desc()).all()
    return render_template(
        "notifications.html",
        page_title="Notificações",
        area_title="Notificações",
        area_subtitle="Acompanhe respostas, comentários e votos.",
        notifications=notifs,
        base_path="aluno",
    )


# ---------------------------------------------------------------------------
# Disciplinas
# ---------------------------------------------------------------------------

@aluno_bp.get("/disciplinas")
@requer_aluno
def disciplinas():
    from app import COURSE_CATALOG
    return render_template(
        "disciplines.html",
        page_title="Disciplinas",
        area_title="Períodos",
        area_subtitle="Matérias por semestre do Técnico em Informática.",
        base_path="aluno",
        course_catalog=COURSE_CATALOG,
    )