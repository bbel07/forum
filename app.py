import os
import secrets
import smtplib
from datetime import datetime, timedelta
from email.message import EmailMessage
from flask import Flask, flash, redirect, render_template, request, session, url_for
from extensions import db
from dotenv import load_dotenv
import click

app = Flask(__name__)

# ---------------------------------------------------------------------------
# Configuração
# ---------------------------------------------------------------------------
app.secret_key = os.environ.get("SECRET_KEY", "ifsp-forum-demo-secret")
app.config["SQLALCHEMY_DATABASE_URI"] = os.environ.get(
    "DATABASE_URL",
    "mysql+mysqlconnector://root:10112007@localhost/forum",
)
app.config["SQLALCHEMY_TRACK_MODIFICATIONS"] = False

load_dotenv()

db.init_app(app)

app.config["MAIL_SERVER"] = os.environ.get("MAIL_SERVER", "")
app.config["MAIL_PORT"] = int(os.environ.get("MAIL_PORT", 587))
app.config["MAIL_USE_TLS"] = os.environ.get("MAIL_USE_TLS", "true").lower() in ("1", "true", "yes")
app.config["MAIL_USE_SSL"] = os.environ.get("MAIL_USE_SSL", "false").lower() in ("1", "true", "yes")
app.config["MAIL_USERNAME"] = os.environ.get("MAIL_USERNAME", "")
app.config["MAIL_PASSWORD"] = os.environ.get("MAIL_PASSWORD", "")
app.config["MAIL_DEFAULT_SENDER"] = os.environ.get("MAIL_DEFAULT_SENDER", "no-reply@ifspforum.local")


def send_email(subject: str, body: str, recipient: str) -> bool:
    msg = EmailMessage()
    msg["Subject"] = subject
    msg["From"] = app.config["MAIL_DEFAULT_SENDER"]
    msg["To"] = recipient
    msg.set_content(body)

    server_name = app.config["MAIL_SERVER"]
    if not server_name:
        print(f"[EMAIL FALLBACK] {subject} -> {recipient}\n{body}")
        return False

    try:
        if app.config["MAIL_USE_SSL"]:
            server = smtplib.SMTP_SSL(server_name, app.config["MAIL_PORT"])
            server.ehlo()
        else:
            server = smtplib.SMTP(server_name, app.config["MAIL_PORT"])
            server.ehlo()
            if app.config["MAIL_USE_TLS"]:
                server.starttls()
                server.ehlo()

        if app.config["MAIL_USERNAME"]:
            server.login(app.config["MAIL_USERNAME"], app.config["MAIL_PASSWORD"])

        server.send_message(msg)
        server.quit()
        return True
    except Exception as exc:
        print(f"[EMAIL ERROR] Falha ao enviar e-mail para {recipient}: {exc}")
        return False


def send_password_reset_code(email: str, code: str):
    print(f"[RECUPERAR SENHA] Código de verificação para {email}: {code}")
    return False


# ---------------------------------------------------------------------------
# Catálogo de cursos
# ---------------------------------------------------------------------------
COURSE_CATALOG = {
    "1º Semestre": [
        "Algoritmo e lógica de programação",
        "Inglês",
        "Introdução aos sistemas operacionais",
        "Fundamentos de informática",
        "Fundamentos de Análises de sistemas",
        "Fundamentos de programação",
        "Matemática",
    ],
    "2º Semestre": [
        "Banco de dados",
        "Empreendedorismo e técnicas de gestão",
        "Engenharia de Software",
        "Introdução à web",
        "Programação Orientada à objeto",
        "Redes de computadores",
        "Sociedade e meio ambiente",
    ],
    "3º Semestre": [
        "Administração de banco de dados",
        "Introdução à administração",
        "Programação para dispositivos móveis",
        "Programação para web",
        "Projeto integrador",
        "Segurança da informação",
    ],
}
# ---------------------------------------------------------------------------
# Imports pós-db
# ---------------------------------------------------------------------------
from models import LoginAluno, LoginProfessor, Pergunta  # noqa: E402
from services import (  # noqa: E402
    format_date, hash_password, fazer_login,
    cadastrar_aluno, cadastrar_professor, enrich_question, get_metrics,
)
from blueprints.aluno import aluno_bp   # noqa: E402
from blueprints.equipe import equipe_bp  # noqa: E402

app.register_blueprint(aluno_bp)
app.register_blueprint(equipe_bp)


# ---------------------------------------------------------------------------
# Context processor
# ---------------------------------------------------------------------------
# Adicione esta função antes ou dentro do context processor
def role_label(role):
    labels = {
        'aluno': 'Aluno',
        'professor': 'Professor',
        'admin': 'Administrador',
    }
    return labels.get(role, role or 'Desconhecido')

@app.context_processor
def inject_globals():
    user_id = session.get("user_id")
    user = None
    if user_id:
        user = LoginAluno.query.get(user_id) or LoginProfessor.query.get(user_id)
    return {
        "current_user": user,
        "format_date": format_date,
        "course_catalog": COURSE_CATALOG,
        "role_label": role_label,   # <-- adicione esta linha
    }


# ---------------------------------------------------------------------------
# Página inicial pública — exibe perguntas sem exigir login
# ---------------------------------------------------------------------------
@app.get("/")
def home():
    # Se já logado, vai direto ao feed
    user_id = session.get("user_id")
    if user_id:
        if LoginAluno.query.get(user_id):
            return redirect(url_for("aluno.feed"))
        return redirect(url_for("equipe.feed"))

    # Visitante vê o feed público com chamadas para login/cadastro.
    search = request.args.get("search", "").strip()
    course = request.args.get("course", "").strip()

    query = Pergunta.query.filter_by(oculta=False)
    if search:
        like = f"%{search}%"
        query = query.filter(
            db.or_(Pergunta.titulo.ilike(like), Pergunta.disciplina.ilike(like))
        )
    if course:
        query = query.filter_by(curso=course)

    perguntas = query.order_by(Pergunta.postado_em.desc()).all()
    for p in perguntas:
        enrich_question(p)

    return render_template(
        "intro.html",
        page_title="Código do Sucesso",
        questions=perguntas,
        metrics=get_metrics(),
        filters={"search": search, "course": course},
    )


@app.get("/politica-privacidade")
def privacy():
    return render_template("privacy.html", page_title="Política e Privacidade")


# ---------------------------------------------------------------------------
# Login
# ---------------------------------------------------------------------------
@app.route("/login", methods=["GET", "POST"])
def login():
    if session.get("user_id"):
        return redirect(url_for("home"))

    next_url = request.args.get("next") or request.form.get("next") or ""

    if request.method == "POST":
        identifier = request.form.get("identifier", "").strip()
        senha = request.form.get("password", "")

        # Detecta automaticamente o papel pelo e-mail
        if "@aluno.ifsp" in identifier:
            role = "student"
        else:
            role = "teacher"

        ok, msg = fazer_login(email=identifier, senha=senha, role=role)
        flash(msg, "success" if ok else "warning")

        if ok:
            user_id = session.get("user_id")
            if next_url:
                return redirect(next_url)
            destino = "aluno.feed" if LoginAluno.query.get(user_id) else "equipe.feed"
            return redirect(url_for(destino))

    return render_template("login.html", page_title="Entrar", next_url=next_url)


# ---------------------------------------------------------------------------
# Cadastro
# ---------------------------------------------------------------------------
@app.route("/cadastro", methods=["GET", "POST"])
def cadastro():
    if session.get("user_id"):
        return redirect(url_for("home"))

    if request.method == "POST":
        action = request.form.get("action", "")

        if action == "register_student":
            email = request.form.get("email", "").strip()
            email_confirm = request.form.get("email_confirm", "").strip()
            accepted = request.form.get("accept_policy")
            if email != email_confirm:
                flash("Os e-mails não coincidem.", "warning")
            elif not accepted:
                flash("Você deve concordar com a Política e Privacidade para se cadastrar.", "warning")
            elif not email.endswith("@aluno.ifsp.edu.br"):
                flash("E-mail de aluno deve terminar com @aluno.ifsp.edu.br.", "warning")
            else:
                ok, msg = cadastrar_aluno(request.form)
                flash(msg, "success" if ok else "warning")
                if ok:
                    return redirect(url_for("login"))

        elif action == "register_staff":
            email = request.form.get("email", "").strip()
            email_confirm = request.form.get("email_confirm", "").strip()
            accepted = request.form.get("accept_policy")
            if email != email_confirm:
                flash("Os e-mails não coincidem.", "warning")
            elif not accepted:
                flash("Você deve concordar com a Política e Privacidade para se cadastrar.", "warning")
            elif not email.endswith("@ifsp.edu.br"):
                flash("E-mail da equipe deve terminar com @ifsp.edu.br.", "warning")
            else:
                ok, msg = cadastrar_professor(request.form)
                flash(msg, "success" if ok else "warning")
                if ok:
                    return redirect(url_for("login"))

    return render_template("cadastro.html", page_title="Cadastro")


# ---------------------------------------------------------------------------
# Recuperar senha
# ---------------------------------------------------------------------------
@app.route("/recuperar-senha", methods=["GET", "POST"])
def recuperar_senha():
    reset_email = session.get("reset_email")
    reset_code = session.get("reset_code")
    reset_expires = session.get("reset_expires")
    display_code = None

    if request.method == "POST":
        action = request.form.get("action")
        email = request.form.get("email", "").strip()

        if action == "send_code":
            if not email:
                flash("Informe um e-mail cadastrado para receber o código.", "warning")
            else:
                user = (
                    LoginAluno.query.filter_by(email=email).first()
                    or LoginProfessor.query.filter_by(email_p=email).first()
                )
                if not user:
                    flash("E-mail não encontrado.", "warning")
                else:
                    code = f"{secrets.randbelow(10**6):06d}"
                    session["reset_email"] = email
                    session["reset_code"] = code
                    session["reset_expires"] = (datetime.utcnow() + timedelta(minutes=5)).isoformat()
                    reset_email = email
                    display_code = code
                    flash(
                        "Código gerado. Copie-o e cole na próxima etapa para redefinir sua senha.",
                        "success",
                    )
                    return render_template(
                        "recuperar_senha.html",
                        page_title="Recuperar senha",
                        reset_email=reset_email,
                        reset_code=display_code,
                    )

        elif action == "reset_password":
            code = request.form.get("code", "").strip()
            password = request.form.get("password", "")
            password_confirm = request.form.get("password_confirm", "")

            if not email:
                flash("Informe o e-mail utilizado para solicitar o código.", "warning")
            elif not code:
                flash("Informe o código de verificação enviado por e-mail.", "warning")
            elif not reset_email or email != reset_email:
                flash("O e-mail informado não corresponde ao pedido de recuperação.", "warning")
            elif not reset_code or not reset_expires:
                flash("Solicite um código antes de tentar redefinir a senha.", "warning")
            elif datetime.utcnow() > datetime.fromisoformat(reset_expires):
                flash("O código expirou. Solicite um novo código.", "warning")
                session.pop("reset_code", None)
                session.pop("reset_expires", None)
            elif code != reset_code:
                flash("Código de verificação inválido.", "warning")
            elif password != password_confirm:
                flash("As senhas não coincidem.", "warning")
            else:
                user = (
                    LoginAluno.query.filter_by(email=email).first()
                    or LoginProfessor.query.filter_by(email_p=email).first()
                )
                if not user:
                    flash("E-mail não encontrado.", "warning")
                else:
                    if isinstance(user, LoginAluno):
                        user.senha_hash = hash_password(password)
                    else:
                        user.senha_hash_p = hash_password(password)
                    db.session.commit()
                    session.pop("reset_email", None)
                    session.pop("reset_code", None)
                    session.pop("reset_expires", None)
                    flash("Senha atualizada! Faça login.", "success")
                    return redirect(url_for("login"))

    return render_template(
        "recuperar_senha.html",
        page_title="Recuperar senha",
        reset_email=reset_email,
        reset_code=display_code,
    )


# ---------------------------------------------------------------------------
# Logout
# ---------------------------------------------------------------------------
@app.get("/sair")
@app.post("/sair")
def logout():
    session.clear()
    flash("Sessão encerrada.", "success")
    return redirect(url_for("home"))


# ---------------------------------------------------------------------------
# Rota legada /acesso → redireciona para /login
# ---------------------------------------------------------------------------
@app.route("/acesso")
def access():
    return redirect(url_for("login"))


# ---------------------------------------------------------------------------
# Inicialização
# ---------------------------------------------------------------------------
if __name__ == "__main__":
    # Inicialização segura para desenvolvimento local: apenas cria tabelas se necessário.
    with app.app_context():
        try:
            db.create_all()
            print("✔ Tabelas criadas (se não existiam).")
        except Exception as e:
            print(f"✘ Erro ao criar tabelas: {e}")
            print("  Verifique se o banco de dados está acessível e a URL em app.config['SQLALCHEMY_DATABASE_URI'] é válida.")
    app.run(debug=True)


# Comando CLI para criar as tabelas sem apagar dados
@app.cli.command("init-db")
def init_db_command():
    """Cria as tabelas do banco (não apaga dados existentes)."""
    try:
        db.create_all()
        click.echo("✔ Tabelas criadas (se não existiam).")
    except Exception as e:
        click.echo(f"✘ Erro ao criar tabelas: {e}")
