from __future__ import annotations

from flask import Flask, session

from database import remove_session


def create_app(
    *,
    import_name: str,
    template_folder: str,
    static_folder: str,
    static_url_path: str,
    secret_key: str,
    auth_blueprint,
    player_blueprint,
    game_blueprint,
    translate_class_name,
) -> Flask:
    app = Flask(
        import_name,
        template_folder=template_folder,
        static_folder=static_folder,
        static_url_path=static_url_path,
    )
    app.secret_key = secret_key

    @app.teardown_appcontext
    def shutdown_session(_exception=None):
        remove_session()

    @app.context_processor
    def inject_session_user():
        return {
            "current_user": session.get("username"),
            "has_character": session.get("has_character", False),
            "translate_class_name": translate_class_name,
        }

    app.register_blueprint(auth_blueprint)
    app.register_blueprint(player_blueprint)
    app.register_blueprint(game_blueprint)
    return app
