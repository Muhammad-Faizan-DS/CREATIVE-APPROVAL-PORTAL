"""The landing page. Each role sees the work it owns."""

from datetime import date

from flask import Blueprint, render_template
from sqlalchemy.orm import selectinload

from .. import analytics
from ..access import is_client, is_designer, is_manager
from ..extensions import db
from ..models import (
    Brand,
    Brief,
    Campaign,
    Client,
    CreativeVersion,
    DeliveryBatch,
    ReviewAssignment,
    ReviewRound,
    Task,
    TaskAssignee,
)
from ..workflow import APPROVED, version_status
from ..security import current_user, login_required

bp = Blueprint("dashboard", __name__)


@bp.get("/")
@login_required
def home():
    user = current_user()
    data = {"campaigns": [], "tasks": [], "briefs": [], "reviews": [],
            "deliveries": [], "metrics": []}

    if is_manager(user):
        data["campaigns"] = db.session.scalars(
            db.select(Campaign)
            .options(selectinload(Campaign.brand), selectinload(Campaign.team))
            .order_by(Campaign.name)
        ).all()
        data["deliveries"] = db.session.scalars(
            db.select(DeliveryBatch).order_by(DeliveryBatch.id.desc()).limit(10)
        ).all()
        open_reviews = db.session.scalars(db.select(ReviewRound)).all()
        waiting = [r for r in open_reviews if r.decision is None]
        approved_versions = [
            version for version in db.session.scalars(db.select(CreativeVersion))
            if version_status(version) == APPROVED
        ]
        data["metrics"] = [
            ("Clients", db.session.scalar(
                db.select(db.func.count()).select_from(Client))),
            ("Brands", db.session.scalar(
                db.select(db.func.count()).select_from(Brand))),
            ("Campaigns", len(data["campaigns"])),
            ("Awaiting review", len(waiting)),
            ("Ready to deliver", len(approved_versions)),
        ]

    if is_designer(user):
        team_ids = [m.team_id for m in user.team_memberships]
        if team_ids:
            data["campaigns"] = db.session.scalars(
                db.select(Campaign)
                .filter(Campaign.team_id.in_(team_ids))
                .order_by(Campaign.name)
            ).all()
        data["tasks"] = db.session.scalars(
            db.select(Task)
            .join(TaskAssignee)
            .filter(TaskAssignee.user_id == user.id)
            .order_by(Task.status, Task.id)
        ).all()

    if is_client(user):
        client_ids = [m.client_id for m in user.client_memberships] or [0]
        data["briefs"] = db.session.scalars(
            db.select(Brief)
            .join(Brief.campaign)
            .join(Campaign.brand)
            .filter(Brand.client_id.in_(client_ids))
            .order_by(Brief.due_on)
        ).all()
        data["reviews"] = db.session.scalars(
            db.select(ReviewAssignment)
            .filter(ReviewAssignment.reviewer_id == user.id)
            .order_by(ReviewAssignment.id.desc())
        ).all()
        data["deliveries"] = db.session.scalars(
            db.select(DeliveryBatch)
            .join(DeliveryBatch.campaign)
            .join(Campaign.brand)
            .filter(Brand.client_id.in_(client_ids))
            .filter(DeliveryBatch.sent_at.is_not(None))
            .order_by(DeliveryBatch.sent_at.desc())
        ).all()

    campaigns_in_scope = analytics.visible_campaigns(user)
    return render_template(
        "dashboard.html",
        user=user,
        pipeline=analytics.pipeline(user, campaigns_in_scope),
        weekly=analytics.weekly_versions(user, campaigns=campaigns_in_scope),
        schedule=analytics.schedule(user, campaigns_in_scope),
        feed=analytics.activity(user, campaigns=campaigns_in_scope),
        today=date.today(),
        **data,
    )
