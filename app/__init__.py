import os
from flask import Flask, session
from authlib.integrations.flask_client import OAuth

from .db import close_db, init_app as init_db_app


def create_app(test_config=None):
    app = Flask(
        __name__,
        instance_relative_config=True,
        template_folder="../templates",
        static_folder="../static",
    )
    app.config.from_mapping(
        SECRET_KEY=os.getenv("SECRET_KEY", "dev-change-this"),
        DATABASE=os.path.join(app.instance_path, "life_path.sqlite"),
        STRIPE_SECRET_KEY=os.getenv("STRIPE_SECRET_KEY", ""),
        STRIPE_PUBLISHABLE_KEY=os.getenv("STRIPE_PUBLISHABLE_KEY", ""),
        STRIPE_PRICE_BASIC=os.getenv("STRIPE_PRICE_BASIC", "price_basic"),
        STRIPE_PRICE_PRO=os.getenv("STRIPE_PRICE_PRO", "price_pro"),
        STRIPE_PRICE_ELITE=os.getenv("STRIPE_PRICE_ELITE", "price_elite"),
        COMPANY_EMAIL=os.getenv("COMPANY_EMAIL", "pending@lifepath.example"),
        SMTP_HOST=os.getenv("SMTP_HOST", ""),
        SMTP_PORT=int(os.getenv("SMTP_PORT", "587")),
        SMTP_USER=os.getenv("SMTP_USER", ""),
        SMTP_PASS=os.getenv("SMTP_PASS", ""),
        OAUTH_CLIENT_ID=os.getenv("OAUTH_CLIENT_ID", ""),
        OAUTH_CLIENT_SECRET=os.getenv("OAUTH_CLIENT_SECRET", ""),
    )

    if test_config is not None:
        app.config.update(test_config)

    os.makedirs(app.instance_path, exist_ok=True)

    init_db_app(app)
    app.teardown_appcontext(close_db)

    oauth = OAuth(app)
    if app.config["OAUTH_CLIENT_ID"] and app.config["OAUTH_CLIENT_SECRET"]:
        oauth.register(
            name="google",
            client_id=app.config["OAUTH_CLIENT_ID"],
            client_secret=app.config["OAUTH_CLIENT_SECRET"],
            server_metadata_url=(
                "https://accounts.google.com/"
                ".well-known/openid-configuration"
            ),
            client_kwargs={"scope": "openid email profile"},
        )

    from .routes import bp

    app.register_blueprint(bp)

    @app.context_processor
    def csrf_context():
        token = session.get("csrf_token")
        if not token:
            token = os.urandom(24).hex()
            session["csrf_token"] = token
        return {"csrf_token": token}

    return app
