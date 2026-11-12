"""Delivery batches: prepare, send and acknowledge approved versions."""

from flask import Blueprint, abort, flash, redirect, render_template, request
from flask import url_for
from sqlalchemy.exc import IntegrityError

from ..access import in_client, is_client, is_manager, require_view
from ..extensions import db
from ..models import Campaign, DeliveryBatch, DeliveryReceipt, utcnow
from ..security import current_user, login_required
from ..workflow import is_approved

bp = Blueprint("deliveries", __name__)


@bp.get("/campaigns/<int:campaign_id>/deliveries")
@login_required
def index(campaign_id):
    campaign = db.get_or_404(Campaign, campaign_id)
    require_view(current_user(), campaign)
    return render_template("deliveries/list.html", campaign=campaign)


@bp.get("/deliveries/<int:batch_id>")
@login_required
def detail(batch_id):
    batch = db.get_or_404(DeliveryBatch, batch_id)
    user = current_user()
    require_view(user, batch.campaign)
    if is_client(user) and not batch.is_sent:
        abort(404)
    my_receipt = next(
        (r for r in batch.receipts if r.received_by == user.id), None
    )
    return render_template(
        "deliveries/detail.html",
        batch=batch,
        my_receipt=my_receipt,
        can_acknowledge=(
            batch.is_sent
            and my_receipt is None
            and is_client(user)
            and in_client(user, batch.campaign.brand.client_id)
        ),
    )


@bp.post("/deliveries/<int:batch_id>/send")
@login_required
def send(batch_id):
    """Confirm every item is still approved, then stamp sent_at."""
    batch = db.get_or_404(DeliveryBatch, batch_id)
    user = current_user()
    require_view(user, batch.campaign)
    if not is_manager(user):
        abort(403)

    back = url_for("deliveries.detail", batch_id=batch.id)
    if batch.is_sent:
        flash("This batch has already been sent.", "error")
        return redirect(back, code=303)
    if not batch.items:
        flash("Add at least one approved version before sending.", "error")
        return redirect(back, code=303)
    unapproved = [
        item for item in batch.items if not is_approved(item.version)
    ]
    if unapproved:
        flash(
            "Every item must be an approved version. Remove: "
            + ", ".join(item.label for item in unapproved),
            "error",
        )
        return redirect(back, code=303)

    batch.sent_at = utcnow()
    db.session.commit()
    flash("Delivery sent to the client.", "success")
    return redirect(back, code=303)


@bp.post("/deliveries/<int:batch_id>/receipt")
@login_required
def acknowledge(batch_id):
    """One receipt per batch and client account."""
    batch = db.get_or_404(DeliveryBatch, batch_id)
    user = current_user()
    require_view(user, batch.campaign)
    back = url_for("deliveries.detail", batch_id=batch.id)

    if not is_client(user) or not in_client(user, batch.campaign.brand.client_id):
        abort(403)
    if not batch.is_sent:
        flash("This batch has not been sent yet.", "error")
        return redirect(back, code=303)

    note = request.form.get("note", "").strip()
    db.session.add(
        DeliveryReceipt(
            delivery_batch_id=batch.id,
            received_by=user.id,
            note=note or None,
        )
    )
    try:
        db.session.commit()
    except IntegrityError:
        db.session.rollback()
        flash("You have already acknowledged this delivery.", "error")
        return redirect(back, code=303)

    flash("Delivery acknowledged. Thank you.", "success")
    return redirect(back, code=303)
