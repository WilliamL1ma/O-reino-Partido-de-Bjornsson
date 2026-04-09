from __future__ import annotations

from collections.abc import Callable

from flask import Blueprint, flash, redirect, render_template, request, session, url_for


def create_auth_blueprint(
    *,
    normalize_email: Callable[[str], str],
    validate_birth_date: Callable[[str], object | None],
    password_is_strong: Callable[[str], bool],
    hash_password: Callable[[str], str],
    verify_password: Callable[[str, str], bool],
    get_user_by_email: Callable[[str], object | None],
    get_character_by_user_id: Callable[[int], object | None],
    login_user: Callable[[object], None],
    logout_user: Callable[[], None],
    post_login_redirect: Callable[[], str],
    session_scope,
    user_model,
    integrity_error,
) -> Blueprint:
    blueprint = Blueprint("auth_routes", __name__)

    @blueprint.get("/", endpoint="index")
    def index():
        return render_template("index.html")

    @blueprint.route("/login", methods=["GET", "POST"], endpoint="login")
    def login():
        if request.method == "POST":
            email = normalize_email(request.form.get("email", ""))
            password = request.form.get("password", "")

            if not email or not password:
                flash("Preencha e-mail e senha para entrar.", "error")
                return redirect(url_for(".login"))

            user = get_user_by_email(email)
            if not user or not verify_password(password, user.password_hash):
                flash("E-mail ou senha invalidos.", "error")
                return redirect(url_for(".login"))

            login_user(user)
            character = get_character_by_user_id(user.id)
            session["has_character"] = character is not None
            flash(f"Bem-vindo de volta, {user.username}.", "success")
            return redirect(post_login_redirect())

        return render_template("login.html")

    @blueprint.route("/registro", methods=["GET", "POST"], endpoint="register")
    def register():
        if request.method == "POST":
            username = request.form.get("username", "").strip()
            email = normalize_email(request.form.get("email", ""))
            birth_date_raw = request.form.get("birth_date", "").strip()
            password = request.form.get("password", "")
            confirm_password = request.form.get("confirm_password", "")

            if not all([username, email, birth_date_raw, password, confirm_password]):
                flash("Preencha todos os campos para criar sua conta.", "error")
                return redirect(url_for(".register"))

            if password != confirm_password:
                flash("A confirmação de senha não confere.", "error")
                return redirect(url_for(".register"))

            if not password_is_strong(password):
                flash("A senha deve ter pelo menos 8 caracteres.", "error")
                return redirect(url_for(".register"))

            birth_daté = validate_birth_date(birth_date_raw)
            if birth_daté is None:
                flash("Informe uma data de nascimento valida.", "error")
                return redirect(url_for(".register"))

            with session_scope() as db_session:
                existing_user = db_session.query(user_model).filter_by(email=email).first()
                if existing_user:
                    flash("Ja existe uma conta cadastrada com esse e-mail.", "error")
                    return redirect(url_for(".register"))

                user = user_model(
                    username=username,
                    email=email,
                    birth_date=birth_date,
                    password_hash=hash_password(password),
                )
                db_session.add(user)
                try:
                    db_session.flush()
                except integrity_error:
                    flash("Ja existe uma conta cadastrada com esse e-mail.", "error")
                    return redirect(url_for(".register"))

            flash("Conta criada com sucesso. Faca login para continuar.", "success")
            return redirect(url_for(".login"))

        return render_template("register.html")

    @blueprint.post("/logout", endpoint="logout")
    def logout():
        logout_user()
        flash("Sessao encerrada.", "success")
        return redirect(url_for(".index"))

    return blueprint
