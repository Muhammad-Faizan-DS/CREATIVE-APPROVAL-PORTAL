"""Search across the records the signed-in account may open."""

from flask import Blueprint, render_template, request

from ..analytics import search as search_records
from ..security import current_user, login_required

bp = Blueprint("search", __name__)


@bp.get("/search")
@login_required
def results():
    term = request.args.get("q", "").strip()
    groups = search_records(current_user(), term)
    total = sum(len(rows) for _, rows in groups)
    return render_template(
        "search.html", term=term, groups=groups, total=total,
    )
