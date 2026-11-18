from flask import Flask
from app.config import Config
from flask_sqlalchemy import SQLAlchemy
from flask_migrate import Migrate
from sqlalchemy import MetaData
from logging.config import dictConfig
import os
import secrets
from dotenv import load_dotenv

# logs/ is not versioned; create it so a fresh checkout (CI, new server) can start
LOG_DIR = os.path.join(os.path.dirname(os.path.abspath(__file__)), "..", "logs")
os.makedirs(LOG_DIR, exist_ok=True)

dictConfig(
    {
        "version": 1,
        "formatters": {
            "default": {
                "format": "[%(asctime)s] %(levelname)s in %(module)s: %(message)s",
            }
        },
        "handlers": {
            "console": {
                "class": "logging.StreamHandler",
                "stream": "ext://sys.stdout",
                "formatter": "default",
            },
            "fileRotate": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(LOG_DIR, "api.log"),
                "maxBytes": 1000000,
                "backupCount": 5,
                "formatter": "default",
            },
            "consoleFile": {
                "class": "logging.handlers.RotatingFileHandler",
                "filename": os.path.join(LOG_DIR, "console.log"),
                "maxBytes": 1000000,
                "backupCount": 5,
                "formatter": "default",
            },
        },
        "root": {"level": "INFO", "handlers": ["console", "fileRotate", "consoleFile"]},
        "loggers": {
            "InterviewAgent": {
                "level": "DEBUG",
                "handlers": ["console", "fileRotate", "consoleFile"],
                "propagate": False,
            }
        },
    }
)


load_dotenv()
app = Flask('InterviewAgent')
app.config.from_object(Config)
app.secret_key = os.environ.get("SECRET_KEY")
if not app.secret_key:
    # Never fall back to a known key: it would let anyone forge session cookies (e.g. admin login).
    app.secret_key = secrets.token_hex(32)
    app.logger.error(
        "SECRET_KEY is not set - using a random per-process key. Identity tokens and sessions "
        "will NOT work across gunicorn workers or restarts. Set SECRET_KEY in .env!"
    )
# Session cookie (admin login): never sent on cross-site requests (CSRF), not readable by JS.
# The LTI iframe does not rely on it; it uses the identity token (app/identity.py).
app.config.update(SESSION_COOKIE_SAMESITE="Lax", SESSION_COOKIE_HTTPONLY=True)
convention = {
    "ix": 'ix_%(column_0_label)s',
    "uq": "uq_%(table_name)s_%(column_0_name)s",
    "ck": "ck_%(table_name)s_%(constraint_name)s",
    "fk": "fk_%(table_name)s_%(column_0_name)s_%(referred_table_name)s",
    "pk": "pk_%(table_name)s"
}

app.logger.warn(Config)
metadata = MetaData(naming_convention=convention)
db = SQLAlchemy(app, metadata=metadata)
migrate = Migrate(app, db, render_as_batch=True)

from app import routes, models  # noqa: E402,F401  (registers routes/models; must follow db setup)
from app.lti import lti_bp  # noqa: E402
app.register_blueprint(lti_bp)

# Seed RAG strategy embeddings on startup (when enabled)
from app.rag import USE_RAG_STRATEGY, seed_strategy_embeddings  # noqa: E402
if USE_RAG_STRATEGY:
    with app.app_context():
        db.create_all()  # ensure strategy_embedding table exists
    import threading

    def _seed_rag() -> None:
        with app.app_context():
            seed_strategy_embeddings()

    threading.Thread(target=_seed_rag, daemon=True, name="rag-seed").start()
