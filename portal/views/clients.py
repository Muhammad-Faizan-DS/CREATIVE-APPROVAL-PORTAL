"""Client organisations, their reviewers and their contacts."""

from flask import Blueprint, abort, render_template
from sqlalchemy.orm import selectinload

from ..access import in_client, is_manager
from ..extensions import db
from ..models import Client
from ..security import current_user, login_required, manager_only

bp = Blueprint("clients", __name__, url_prefix="/clients")


@bp.get("/")
@manager_only
def index():
    clients = db.session.scalars(
        db.select(Client)
        .options(selectinload(Client.brands))
        .order_by(Client.name)
    ).all()
    return render_template("clients/list.html", clients=clients)


@bp.get("/<int:client_id>")
@login_required
def detail(client_id):
    client = db.get_or_404(Client, client_id)
    user = current_user()
    if not is_manager(user) and not in_client(user, client.id):
        abort(404)
    return render_template("clients/detail.html", client=client)
