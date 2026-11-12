"""Manager settings: the lookup tables and team membership."""

from flask import Blueprint, render_template

from ..extensions import db
from ..models import Team
from ..resources import settings_groups
from ..security import manager_only

bp = Blueprint("settings", __name__, url_prefix="/settings")


@bp.get("/")
@manager_only
def index():
    return render_template("settings/index.html", groups=settings_groups())


@bp.get("/teams/<int:team_id>")
@manager_only
def team_detail(team_id):
    team = db.get_or_404(Team, team_id)
    return render_template("settings/team_detail.html", team=team)
