"""Brands and campaigns.

Brand carries the full create, read, update and delete pattern written out
in long form; the other tables reuse the shared screens in views/manage.py.
"""

from flask import Blueprint, abort, flash, redirect, render_template, request
from flask import url_for
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import selectinload

from ..access import in_client, in_team, is_manager, require_view
from ..extensions import db
from ..models import Brand, Campaign, Client
from ..security import current_user, login_required, manager_only

bp = Blueprint("campaigns", __name__)


@bp.get("/brands")
@manager_only
def brand_list():
    query = db.select(Brand).options(selectinload(Brand.client))
    brands = db.session.scalars(query.order_by(Brand.name)).all()
    return render_template("brands/list.html", brands=brands)


@bp.route("/brands/new", methods=["GET", "POST"])
@manager_only
def brand_create():
    return brand_form(Brand())


@bp.route("/brands/<int:brand_id>/edit", methods=["GET", "POST"])
@manager_only
def brand_edit(brand_id):
    return brand_form(db.get_or_404(Brand, brand_id))


@bp.post("/brands/<int:brand_id>/delete")
@manager_only
def brand_delete(brand_id):
    brand = db.get_or_404(Brand, brand_id)
    db.session.delete(brand)
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("Remove the related records before deleting this brand.", "error")
        return redirect(url_for(".brand_list"), code=303)
    flash("Brand deleted.", "success")
    return redirect(url_for(".brand_list"), code=303)


def brand_form(brand):
    """Render the brand form, and on POST validate and save it."""
    clients = db.session.scalars(db.select(Client).order_by(Client.name)).all()
    name, client_id = brand.name or "", brand.client_id
    error = None
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        if brand.id is None:
            client_id = request.form.get("client_id", type=int)
        if not name or len(name) > 120:
            error = "Enter a brand name of 1 to 120 characters."
        elif client_id not in {client.id for client in clients}:
            error = "Choose an existing client."
        else:
            brand.name, brand.client_id = name, client_id
            db.session.add(brand)
            try:
                db.session.commit()
            except IntegrityError:
                db.session.rollback()
                error = "This client already has a brand with that name."
            else:
                flash("Brand saved.", "success")
                return redirect(url_for(".brand_list"), code=303)
    return render_template(
        "brands/form.html", brand=brand, clients=clients,
        name=name, client_id=client_id, error=error,
    ), 400 if error else 200


@bp.get("/brands/<int:brand_id>")
@login_required
def brand_detail(brand_id):
    """Guidelines, assets, audiences and campaigns for one brand."""
    brand = db.get_or_404(Brand, brand_id)
    user = current_user()
    allowed = (
        is_manager(user)
        or in_client(user, brand.client_id)
        or any(in_team(user, c.team_id) for c in brand.campaigns)
    )
    if not allowed:
        abort(404)
    return render_template("campaigns/brand_detail.html", brand=brand)


@bp.get("/campaigns/<int:campaign_id>")
@login_required
def campaign_detail(campaign_id):
    """Channels, audiences, briefs and delivery batches for one campaign."""
    campaign = db.get_or_404(Campaign, campaign_id)
    require_view(current_user(), campaign)
    return render_template("campaigns/detail.html", campaign=campaign)
