"""
Blueprint: área da equipe (professores e mediadores)
Prefixo: /equipe
"""
from flask import Blueprint, flash, redirect, render_template, request, session, url_for
from models import LoginAluno, LoginProfessor, Pergunta, Resposta, Comentario, Denuncia, Notificacao
from services import (
    enrich_question, get_metrics, get_current_user, is_aluno,
    criar_comentario,
    votar, resolver_denuncia,
    ocultar_pergunta, remover_pergunta, remover_resposta, remover_comentario,
    get_observed_students, observar_aluno,
    atualizar_perfil,
)

equipe_bp = Blueprint("equipe", __name__, url_prefix="/equipe")

ROLES_EQUIPE = {"professor", "mediador"}


# ---------------------------------------------------------------------------
# Decorator: exige login de professor ou mediador
# ---------------------------------------------------------------------------

def requer_equipe(f):
    from functools import wraps
    @wraps(f)
    def wrapped(*args, **kwargs):
        user_id = session.get("user_id")
        user = LoginProfessor.query.get(user_id) if user_id else None
        if not user:
            flash("Acesso restrito à equipe acadêmica.", "warning")
            return redirect(url_for("login"))
        return f(*args, **kwargs)
    return wrapped


# ---------------------------------------------------------------------------
# Feed
# ---------------------------------------------------------------------------

@equipe_bp.get("/feed")
@requer_equipe
def feed():
    perguntas = Pergunta.query.order_by(Pergunta.postado_em.desc()).all()
    perguntas = [enrich_question(p) for p in perguntas]
    return render_template(
        "feed.html",
        page_title="Feed da equipe",
        area_title="Área de professores e mediadores",
        area_subtitle="Visualização ampliada com ferramentas de moderação.",
        questions=perguntas,
        metrics=get_metrics(),
        is_staff=True,
        base_path="equipe",
        filters=request.args,
    )


# ---------------------------------------------------------------------------
# Fórum
# ---------------------------------------------------------------------------

@equipe_bp.get("/forum/<int:id_pergunta>")
@requer_equipe
def forum(id_pergunta):
    pergunta = Pergunta.query.get_or_404(id_pergunta)
    respostas = Resposta.query.filter_by(id_pergunta=id_pergunta)\
        .order_by(Resposta.enviado_em.desc()).all()
    return render_template(
        "forum.html",
        page_title="Fórum",
        area_title="Fórum da comunidade",
        area_subtitle="Leia e modere a discussão.",
        question=enrich_question(pergunta),
        answers=respostas,
        base_path="equipe",
        is_staff=True,
        can_accept=True,
    )



# ---------------------------------------------------------------------------
# Ações POST do fórum
# ---------------------------------------------------------------------------


@equipe_bp.post("/forum/<int:id_pergunta>/comentario")
@requer_equipe
def post_comentario_pergunta(id_pergunta):
    ok, msg = criar_comentario(id_pergunta, request.form.get("content", ""))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


@equipe_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/comentario")
@requer_equipe
def post_comentario_resposta(id_pergunta, id_r):
    ok, msg = criar_comentario(id_pergunta, request.form.get("content", ""), id_r=id_r)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


@equipe_bp.post("/forum/<int:id_pergunta>/remover")
@requer_equipe
def post_remover_pergunta(id_pergunta):
    ok, msg = remover_pergunta(id_pergunta)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.feed"))


@equipe_bp.post("/forum/<int:id_pergunta>/comentario/<int:id_c>/remover")
@requer_equipe
def post_remover_comentario_pergunta(id_pergunta, id_c):
    ok, msg = remover_comentario(id_c)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


@equipe_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/remover")
@requer_equipe
def post_remover_resposta(id_pergunta, id_r):
    ok, msg = remover_resposta(id_r)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


@equipe_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/comentario/<int:id_c>/remover")
@requer_equipe
def post_remover_comentario_resposta(id_pergunta, id_r, id_c):
    ok, msg = remover_comentario(id_c)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


@equipe_bp.post("/forum/<int:id_pergunta>/votar")
@requer_equipe
def post_voto_pergunta(id_pergunta):
    ok, msg = votar("pergunta", id_pergunta, request.form.get("tipo", "positivo"))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


@equipe_bp.post("/forum/<int:id_pergunta>/resposta/<int:id_r>/votar")
@requer_equipe
def post_voto_resposta(id_pergunta, id_r):
    ok, msg = votar("resposta", id_r, request.form.get("tipo", "positivo"))
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))



# ---------------------------------------------------------------------------
# Ações exclusivas da moderação
# ---------------------------------------------------------------------------

@equipe_bp.post("/forum/<int:id_pergunta>/ocultar")
@requer_equipe
def post_ocultar_pergunta(id_pergunta):
    ok, msg = ocultar_pergunta(id_pergunta)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.forum", id_pergunta=id_pergunta))


# ---------------------------------------------------------------------------
# Moderação
# ---------------------------------------------------------------------------

def _annotate_denuncia(report):
    report.target_type = report.tipo_alvo
    report.created_at = report.criado_em
    report.reason = report.motivo
    report.reporter_name = None
    report.target_name = "Usuário desconhecido"
    report.target_title = ""
    report.target_content = ""

    if report.cp_autor:
        autor = LoginAluno.query.get(report.cp_autor)
        report.reporter_name = autor.nome if autor else "Usuário desconhecido"
    else:
        report.reporter_name = "Usuário desconhecido"

    if report.tipo_alvo == "pergunta" and report.id_pergunta:
        pergunta = Pergunta.query.get(report.id_pergunta)
        if pergunta:
            autor_alvo = LoginAluno.query.get(pergunta.cp)
            report.target_name = autor_alvo.nome if autor_alvo else "Usuário desconhecido"
            report.target_title = pergunta.titulo
            report.target_content = pergunta.descricao
            report.reported_cp = pergunta.cp
            report.question_id = pergunta.id_pergunta
    elif report.tipo_alvo == "resposta" and report.id_r:
        resposta = Resposta.query.get(report.id_r)
        if resposta:
            autor_alvo = LoginAluno.query.get(resposta.cp)
            report.target_name = autor_alvo.nome if autor_alvo else "Usuário desconhecido"
            report.target_content = resposta.conteudo
            report.target_title = "Resposta"
            report.reported_cp = resposta.cp
            report.question_id = resposta.id_pergunta
    return report


@equipe_bp.get("/moderacao")
@requer_equipe
def moderacao():
    denuncias = Denuncia.query.filter_by(status="aberta")\
        .order_by(Denuncia.criado_em.desc()).all()
    for denuncia in denuncias:
        _annotate_denuncia(denuncia)
    return render_template(
        "moderation.html",
        page_title="Moderação",
        area_title="Painel de moderação",
        area_subtitle="Tela exclusiva para professores e mediadores.",
        reports=denuncias,
        flagged_users=get_observed_students(),
        base_path="equipe",
    )


@equipe_bp.post("/moderacao/aluno/<string:cp>/observar")
@requer_equipe
def post_observar_aluno(cp):
    ok, msg = observar_aluno(cp)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.moderacao"))


@equipe_bp.post("/moderacao/denuncia/<int:id_d>/resolver")
@requer_equipe
def post_resolver_denuncia(id_d):
    ok, msg = resolver_denuncia(id_d)
    flash(msg, "success" if ok else "warning")
    return redirect(url_for("equipe.moderacao"))


# ---------------------------------------------------------------------------
# Perfil
# ---------------------------------------------------------------------------

@equipe_bp.route("/perfil", methods=["GET", "POST"])
@requer_equipe
def perfil():
    user_id = session.get("user_id")
    user = LoginProfessor.query.get(user_id)
    if request.method == "POST":
        ok, msg = atualizar_perfil(request.form)
        flash(msg, "success" if ok else "warning")
        return redirect(url_for("equipe.perfil"))

    total_respostas = Resposta.query.count()
    return render_template(
        "profile.html",
        page_title="Perfil",
        area_title="Meu perfil",
        area_subtitle="Edite seus dados.",
        user=user,
        user_questions=0,
        user_answers=total_respostas,
        base_path="equipe",
    )


# ---------------------------------------------------------------------------
# Notificações
# ---------------------------------------------------------------------------

@equipe_bp.get("/notificacoes")
@requer_equipe
def notificacoes():
    user_id = session.get("user_id")
    notifs = Notificacao.query.filter_by(email_p=user_id)\
        .order_by(Notificacao.criado_em.desc()).all()
    return render_template(
        "notifications.html",
        page_title="Notificações",
        area_title="Notificações",
        area_subtitle="Alertas de moderação e interações.",
        notifications=notifs,
        base_path="equipe",
    )


# ---------------------------------------------------------------------------
# Disciplinas
# ---------------------------------------------------------------------------

@equipe_bp.get("/disciplinas")
@requer_equipe
def disciplinas():
    return render_template(
        "disciplines.html",
        page_title="Disciplinas",
        area_title="Disciplinas por curso e semestre",
        area_subtitle="Grade acadêmica completa.",
        base_path="equipe",
    )


@equipe_bp.get("/disciplinas/<path:disciplina>")
@requer_equipe
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
        is_staff=True,
        base_path="equipe",
        filters={"discipline": disciplina},
        course_catalog=COURSE_CATALOG,
        question_action_label="Perguntas e respostas",
    )