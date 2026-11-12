"""Command line helpers that create starter and demo data."""

from datetime import date, timedelta

import click
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import (
    Audience,
    Brand,
    Brief,
    BriefDeliverable,
    BriefReference,
    BriefRequirement,
    BrandAsset,
    BrandGuideline,
    Campaign,
    CampaignAudience,
    CampaignChannel,
    Channel,
    Client,
    ClientContact,
    ClientMembership,
    CreativeFormat,
    Role,
    Tag,
    Task,
    TaskAssignee,
    TaskChecklistItem,
    Team,
    TeamMembership,
    User,
)

ROLE_LABELS = {
    "manager": "Manager",
    "designer": "Designer",
    "client": "Client reviewer",
}


def get_or_create(model, defaults=None, **filters):
    """Return the matching row, inserting it the first time."""
    row = db.session.scalar(db.select(model).filter_by(**filters))
    if row is None:
        row = model(**filters, **(defaults or {}))
        db.session.add(row)
        db.session.flush()
    return row


def ensure_role(code):
    return get_or_create(Role, defaults={"label": ROLE_LABELS[code]}, code=code)


def ensure_user(name, email, role_code, password):
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user is None:
        user = User(
            name=name,
            email=email,
            role=ensure_role(role_code),
            password_hash=generate_password_hash(password),
        )
        db.session.add(user)
        db.session.flush()
    return user


@click.command("seed-starter")
@click.password_option()
@with_appcontext
def seed_starter(password):
    """Create the first manager account and one client to test with."""
    role = db.session.scalar(db.select(Role).filter_by(code="manager"))
    if role is None:
        role = Role(code="manager", label="Manager")
        db.session.add(role)
    email = "manager@example.test"
    if db.session.scalar(db.select(User).filter_by(email=email)) is None:
        db.session.add(User(
            name="Demo Manager", email=email, role=role,
            password_hash=generate_password_hash(password),
        ))
    if db.session.scalar(db.select(Client).filter_by(name="Demo Client")) is None:
        db.session.add(Client(name="Demo Client"))
    db.session.commit()
    click.echo("Starter manager and client are ready.")


@click.command("seed-demo")
@click.password_option()
@with_appcontext
def seed_demo(password):
    """Create the full demo: three roles, two client organisations, a brief."""
    build_demo_data(password)
    click.echo(
        "Demo data ready. Sign in as manager@example.test, "
        "designer@example.test or client@example.test."
    )


def build_demo_data(password):
    """The demo records, shared by the CLI command and the demo deployment."""
    ensure_user("Dana Price", "manager@example.test", "manager", password)
    designer = ensure_user("Sam Ortiz", "designer@example.test", "designer",
                           password)
    reviewer = ensure_user("Riya Khan", "client@example.test", "client",
                           password)
    other_reviewer = ensure_user("Tom Lund", "client2@example.test", "client",
                                 password)

    northwind = get_or_create(
        Client, defaults={"website_url": "https://northwind.example"},
        name="Northwind Coffee",
    )
    lumen = get_or_create(
        Client, defaults={"website_url": "https://lumen.example"},
        name="Lumen Fitness",
    )
    get_or_create(ClientMembership, defaults={"can_approve": True},
                  client_id=northwind.id, user_id=reviewer.id)
    get_or_create(ClientMembership, defaults={"can_approve": True},
                  client_id=lumen.id, user_id=other_reviewer.id)
    get_or_create(ClientContact,
                  defaults={"name": "Riya Khan", "job_title": "Brand lead"},
                  client_id=northwind.id, email="riya@northwind.example")

    team = get_or_create(Team, defaults={"description": "Static ad studio"},
                         name="Studio One")
    get_or_create(TeamMembership, defaults={"joined_on": date.today()},
                  team_id=team.id, user_id=designer.id)

    brand = get_or_create(Brand, client_id=northwind.id, name="Northwind Roast")
    get_or_create(
        BrandGuideline,
        defaults={"rule_text": "Use the cream logo on dark backgrounds only."},
        brand_id=brand.id, title="Logo contrast",
    )
    get_or_create(
        BrandAsset,
        defaults={"asset_type": "logo", "url": "https://northwind.example/logo.png"},
        brand_id=brand.id, label="Primary logo",
    )
    audience = get_or_create(
        Audience,
        defaults={"description": "City commuters aged 25 to 40."},
        brand_id=brand.id, label="Commuters",
    )

    channel = get_or_create(Channel, name="Instagram feed")
    fmt = get_or_create(CreativeFormat,
                        defaults={"width_px": 1080, "height_px": 1080},
                        name="Square 1080")
    get_or_create(CreativeFormat,
                  defaults={"width_px": 1080, "height_px": 1920},
                  name="Story 1080 x 1920")
    for tag_name in ("seasonal", "promo"):
        get_or_create(Tag, name=tag_name)

    campaign = get_or_create(
        Campaign,
        defaults={
            "team_id": team.id,
            "starts_on": date.today(),
            "ends_on": date.today() + timedelta(days=30),
            "status": "active",
        },
        brand_id=brand.id, name="Autumn Roast Launch",
    )
    link = get_or_create(CampaignChannel,
                         defaults={"note": "Square posts in the main feed."},
                         campaign_id=campaign.id, channel_id=channel.id)
    get_or_create(CampaignAudience, defaults={"priority": 1},
                  campaign_id=campaign.id, audience_id=audience.id)

    brief = get_or_create(
        Brief,
        defaults={
            "created_by": reviewer.id,
            "goal": "Introduce the autumn roast to city commuters.",
            "due_on": date.today() + timedelta(days=14),
            "status": "submitted",
        },
        campaign_id=campaign.id, title="Autumn roast launch posts",
    )
    get_or_create(
        BriefRequirement,
        defaults={"details": "Show the cup and the roast name in the first second."},
        brief_id=brief.id, label="Product visible",
    )
    get_or_create(
        BriefReference,
        defaults={"url": "https://northwind.example/autumn-moodboard"},
        brief_id=brief.id, label="Moodboard",
    )
    get_or_create(
        BriefDeliverable,
        defaults={
            "campaign_channel_id": link.id,
            "creative_format_id": fmt.id,
            "quantity": 2,
        },
        brief_id=brief.id, label="Square feed posts",
    )

    task = get_or_create(
        Task,
        defaults={"due_on": date.today() + timedelta(days=7), "status": "doing"},
        brief_id=brief.id, title="Design the square feed posts",
    )
    get_or_create(TaskAssignee, defaults={"note": "Lead designer"},
                  task_id=task.id, user_id=designer.id)
    get_or_create(TaskChecklistItem, defaults={"is_done": False},
                  task_id=task.id, label="Export the square preview")

    db.session.commit()
