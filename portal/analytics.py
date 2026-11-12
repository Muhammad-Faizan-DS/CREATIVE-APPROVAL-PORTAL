"""Figures behind the dashboard charts, the activity feed and search.

Everything here is derived from the same tables the rest of the portal
uses, and every query is scoped to what the signed-in account may see.
"""

from datetime import date, timedelta

from .access import in_client, in_team, is_client, is_designer, is_manager
from .extensions import db
from .models import (
    Brand,
    Brief,
    Campaign,
    Client,
    Creative,
    DeliveryBatch,
    TaskComment,
)
from .workflow import (
    APPROVED,
    CHANGES_REQUESTED,
    DELIVERED,
    DRAFT,
    IN_REVIEW,
    version_status,
)

PIPELINE_ORDER = (DRAFT, IN_REVIEW, CHANGES_REQUESTED, APPROVED, DELIVERED)


def visible_campaigns(user):
    """The campaigns an account may read, newest first."""
    query = db.select(Campaign).join(Campaign.brand).order_by(Campaign.starts_on)
    campaigns = db.session.scalars(query).all()
    if is_manager(user):
        return campaigns
    if is_designer(user):
        return [c for c in campaigns if in_team(user, c.team_id)]
    if is_client(user):
        return [c for c in campaigns if in_client(user, c.brand.client_id)]
    return []


def visible_versions(user, campaigns=None):
    """Every creative version inside the account's campaigns."""
    campaigns = visible_campaigns(user) if campaigns is None else campaigns
    versions = []
    for campaign in campaigns:
        for brief in campaign.briefs:
            for deliverable in brief.deliverables:
                for creative in deliverable.creatives:
                    versions.extend(creative.versions)
    return versions


def pipeline(user, campaigns=None):
    """How many versions sit in each workflow state."""
    counts = {label: 0 for label in PIPELINE_ORDER}
    for version in visible_versions(user, campaigns):
        counts[version_status(version)] += 1
    return [{"label": label, "value": counts[label]} for label in PIPELINE_ORDER]


def weekly_versions(user, weeks=8, campaigns=None):
    """New versions per week, oldest first, for the activity line."""
    today = date.today()
    start = today - timedelta(days=today.weekday() + 7 * (weeks - 1))
    buckets = [
        {"start": start + timedelta(days=7 * index), "value": 0}
        for index in range(weeks)
    ]
    for version in visible_versions(user, campaigns):
        made = version.created_at.date()
        index = (made - start).days // 7
        if 0 <= index < weeks:
            buckets[index]["value"] += 1
    for bucket in buckets:
        bucket["label"] = bucket["start"].strftime("%d %b")
    return buckets


def schedule(user, campaigns=None):
    """Campaign start and end dates for the timeline."""
    campaigns = visible_campaigns(user) if campaigns is None else campaigns
    rows = []
    for campaign in campaigns:
        ends_on = campaign.ends_on or campaign.starts_on + timedelta(days=14)
        rows.append({
            "name": campaign.name,
            "status": campaign.status,
            "starts_on": campaign.starts_on,
            "ends_on": max(ends_on, campaign.starts_on),
            "campaign": campaign,
        })
    return rows


def deliverable_progress(campaign):
    """How many creatives exist against each deliverable's quantity."""
    rows = []
    for brief in campaign.briefs:
        for deliverable in brief.deliverables:
            rows.append({
                "label": deliverable.label,
                "made": len(deliverable.creatives),
                "wanted": deliverable.quantity,
                "deliverable": deliverable,
            })
    return rows


def activity(user, limit=8, campaigns=None):
    """A merged, newest-first feed of what happened in those campaigns."""
    campaigns = visible_campaigns(user) if campaigns is None else campaigns
    allowed = {campaign.id for campaign in campaigns}
    events = []

    for version in visible_versions(user, campaigns):
        events.append({
            "at": version.created_at,
            "kind": "version",
            "who": version.author.name,
            "what": f"uploaded {version.creative.name} version "
                    f"{version.version_number}",
            "endpoint": ("creatives.version_detail", {"version_id": version.id}),
        })
        review_round = version.review_round
        if review_round is None:
            continue
        for comment in review_round.comments:
            events.append({
                "at": comment.created_at,
                "kind": "comment",
                "who": comment.author.name,
                "what": f"commented on {version.creative.name} v"
                        f"{version.version_number}",
                "endpoint": ("reviews.detail", {"round_id": review_round.id}),
            })
        decision = review_round.decision
        if decision is not None:
            events.append({
                "at": decision.created_at,
                "kind": decision.outcome,
                "who": decision.decider.name,
                "what": f"{decision.outcome.replace('_', ' ')} "
                        f"{version.creative.name} v{version.version_number}",
                "endpoint": ("reviews.detail", {"round_id": review_round.id}),
            })

    for batch in db.session.scalars(db.select(DeliveryBatch)).all():
        if batch.campaign_id not in allowed:
            continue
        if batch.sent_at:
            events.append({
                "at": batch.sent_at,
                "kind": "delivery",
                "who": batch.preparer.name,
                "what": f"sent {batch.title}",
                "endpoint": ("deliveries.detail", {"batch_id": batch.id}),
            })
        for receipt in batch.receipts:
            events.append({
                "at": receipt.received_at,
                "kind": "receipt",
                "who": receipt.recipient.name,
                "what": f"acknowledged {batch.title}",
                "endpoint": ("deliveries.detail", {"batch_id": batch.id}),
            })

    for comment in db.session.scalars(db.select(TaskComment)).all():
        if comment.task.brief.campaign_id not in allowed:
            continue
        events.append({
            "at": comment.created_at,
            "kind": "task",
            "who": comment.author.name,
            "what": f"commented on {comment.task.title}",
            "endpoint": ("briefs.task_detail", {"task_id": comment.task_id}),
        })

    events.sort(key=lambda event: event["at"], reverse=True)
    return events[:limit]


def search(user, term, per_kind=5):
    """Search the records an account may open. Returns grouped results."""
    term = (term or "").strip()
    if len(term) < 2:
        return []

    pattern = f"%{term}%"
    campaigns = visible_campaigns(user)
    allowed_campaigns = {campaign.id for campaign in campaigns}
    allowed_clients = {campaign.brand.client_id for campaign in campaigns}
    if is_manager(user):
        allowed_clients |= {
            row.id for row in db.session.scalars(db.select(Client)).all()
        }

    groups = []

    if is_manager(user):
        clients = db.session.scalars(
            db.select(Client).filter(Client.name.ilike(pattern))
            .order_by(Client.name).limit(per_kind)
        ).all()
        groups.append(("Clients", [
            {"title": row.name, "meta": f"{len(row.brands)} brands",
             "endpoint": ("clients.detail", {"client_id": row.id})}
            for row in clients
        ]))

    brands = [
        row for row in db.session.scalars(
            db.select(Brand).filter(Brand.name.ilike(pattern))
            .order_by(Brand.name)
        ).all()
        if row.client_id in allowed_clients
    ][:per_kind]
    groups.append(("Brands", [
        {"title": row.name, "meta": row.client.name,
         "endpoint": ("campaigns.brand_detail", {"brand_id": row.id})}
        for row in brands
    ]))

    groups.append(("Campaigns", [
        {"title": row.name, "meta": f"{row.brand.name} · {row.status}",
         "endpoint": ("campaigns.campaign_detail", {"campaign_id": row.id})}
        for row in campaigns if term.casefold() in row.name.casefold()
    ][:per_kind]))

    briefs = [
        row for row in db.session.scalars(
            db.select(Brief).filter(Brief.title.ilike(pattern))
            .order_by(Brief.title)
        ).all()
        if row.campaign_id in allowed_campaigns
    ][:per_kind]
    groups.append(("Briefs", [
        {"title": row.title, "meta": f"{row.campaign.name} · {row.status}",
         "endpoint": ("briefs.detail", {"brief_id": row.id})}
        for row in briefs
    ]))

    creatives = [
        row for row in db.session.scalars(
            db.select(Creative).filter(Creative.name.ilike(pattern))
            .order_by(Creative.name)
        ).all()
        if row.deliverable.brief.campaign_id in allowed_campaigns
    ][:per_kind]
    groups.append(("Creatives", [
        {"title": row.name,
         "meta": f"{row.deliverable.label} · "
                 f"{version_status(row.latest_version) if row.latest_version else 'no version'}",
         "endpoint": ("creatives.detail", {"creative_id": row.id})}
        for row in creatives
    ]))

    return [(name, rows) for name, rows in groups if rows]


def count_versions(user):
    return len(visible_versions(user))


__all__ = [
    "activity", "count_versions", "deliverable_progress", "pipeline",
    "schedule", "search", "visible_campaigns", "visible_versions",
    "weekly_versions",
]
