"""Application factory for the Creative Approval Portal."""

from os import environ
from pathlib import Path

import click
from flask import Flask
from sqlalchemy import event, inspect

from .extensions import db


def writable_instance_path():
    """Where the database and uploads live.

    Locally this is Flask's own instance folder. A serverless host such as
    Vercel has a read-only filesystem apart from a scratch directory, so it
    sets PORTAL_DATA_DIR and everything writable goes there instead.
    """
    data_dir = environ.get("PORTAL_DATA_DIR")
    return str(Path(data_dir).resolve()) if data_dir else None


def bootstrap_demo(app):
    """Build the database and demo records on an empty scratch directory.

    Only runs when PORTAL_DEMO_SEED=1, which the demo deployment sets. A
    serverless host wipes the scratch directory on every cold start, so the
    demo restarts from the same seeded data and anything written in
    between is lost. Local runs use init-db and seed-demo instead.
    """
    if environ.get("PORTAL_DEMO_SEED") != "1":
        return
    from .commands import build_demo_data

    with app.app_context():
        if inspect(db.engine).get_table_names():
            return
        db.create_all()
        build_demo_data(environ.get("PORTAL_DEMO_PASSWORD", "demo-pass-123"))


def enable_foreign_keys(connection, _record):
    """SQLite only enforces foreign keys when each connection asks for it."""
    cursor = connection.cursor()
    cursor.execute("PRAGMA foreign_keys=ON")
    cursor.close()


def create_app(test_config=None):
    app = Flask(__name__, instance_path=writable_instance_path())
    app.config.from_mapping(
        SECRET_KEY=environ.get("PORTAL_SECRET_KEY"),
        SQLALCHEMY_DATABASE_URI="sqlite:///portal.sqlite3",
        MAX_CONTENT_LENGTH=8 * 1024 * 1024,
        SESSION_COOKIE_HTTPONLY=True,
        SESSION_COOKIE_SAMESITE="Lax",
    )
    if test_config:
        app.config.update(test_config)
    if not app.config["SECRET_KEY"]:
        raise RuntimeError("Set PORTAL_SECRET_KEY before starting the app.")

    Path(app.instance_path).mkdir(parents=True, exist_ok=True)
    db.init_app(app)
    with app.app_context():
        event.listen(db.engine, "connect", enable_foreign_keys)

    from . import models  # noqa: F401  (registers all 40 tables)
    from .commands import seed_demo, seed_starter
    from .resources import record_url
    from .security import csrf_token, current_user, protect_post
    from .ui import badge_class, initials
    from .views.auth import bp as auth_bp
    from .views.briefs import bp as briefs_bp
    from .views.campaigns import bp as campaigns_bp
    from .views.clients import bp as clients_bp
    from .views.creatives import bp as creatives_bp
    from .views.dashboard import bp as dashboard_bp
    from .views.deliveries import bp as deliveries_bp
    from .views.manage import bp as manage_bp
    from .views.manage import children
    from .views.reviews import bp as reviews_bp
    from .views.search import bp as search_bp
    from .views.settings import bp as settings_bp
    from .workflow import creative_status, version_status

    for blueprint in (
        auth_bp,
        dashboard_bp,
        settings_bp,
        clients_bp,
        campaigns_bp,
        briefs_bp,
        creatives_bp,
        reviews_bp,
        deliveries_bp,
        search_bp,
        manage_bp,
    ):
        app.register_blueprint(blueprint)

    def rows_of(records, *keys):
        """Template filter: turn dicts into table rows for a chart's data view."""
        return [[record[key] for key in keys] for record in records]

    app.jinja_env.filters["rows_of"] = rows_of
    app.before_request(protect_post)
    app.jinja_env.globals.update(
        csrf_token=csrf_token,
        children=children,
        current_user=current_user,
        record_url=record_url,
        version_status=version_status,
        creative_status=creative_status,
        badge_class=badge_class,
        initials=initials,
    )
    app.cli.add_command(seed_starter)
    app.cli.add_command(seed_demo)

    @app.cli.command("init-db")
    def init_db():
        db.create_all()
        tables = inspect(db.engine).get_table_names()
        click.echo(f"{len(tables)} tables created or already present.")

    bootstrap_demo(app)

    @app.errorhandler(403)
    def forbidden(error):
        from flask import render_template

        return render_template(
            "error.html", code=403,
            message="Your account cannot open that page.",
        ), 403

    @app.errorhandler(404)
    def not_found(error):
        from flask import render_template

        return render_template(
            "error.html", code=404,
            message="That record does not exist, or it is outside your work.",
        ), 404

    @app.errorhandler(413)
    def too_large(error):
        from flask import render_template

        return render_template(
            "error.html", code=413,
            message="That upload is larger than the 8 MB limit.",
        ), 413

    return app
