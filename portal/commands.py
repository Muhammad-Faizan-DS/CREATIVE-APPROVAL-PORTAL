"""Command line helpers that create starter and demo data."""

import zlib
from datetime import date, datetime, timedelta, timezone
from pathlib import Path
from struct import pack

import click
from flask import current_app
from flask.cli import with_appcontext
from werkzeug.security import generate_password_hash

from .extensions import db
from .models import (
    Audience,
    Brand,
    BrandAsset,
    BrandGuideline,
    Brief,
    BriefDeliverable,
    BriefReference,
    BriefRequirement,
    Campaign,
    CampaignAudience,
    CampaignChannel,
    ChangeRequest,
    Channel,
    Client,
    ClientContact,
    ClientMembership,
    CopyVariant,
    Creative,
    CreativeFormat,
    CreativeTag,
    CreativeVersion,
    DeliveryBatch,
    DeliveryItem,
    DeliveryReceipt,
    ReviewAssignment,
    ReviewAttachment,
    ReviewComment,
    ReviewDecision,
    ReviewRound,
    Role,
    Tag,
    Task,
    TaskAssignee,
    TaskChecklistItem,
    TaskComment,
    Team,
    TeamMembership,
    User,
    VersionCopyVariant,
    VersionFile,
)

ROLE_LABELS = {
    "manager": "Manager",
    "designer": "Designer",
    "client": "Client reviewer",
}

TODAY = date.today()


def days(offset):
    return TODAY + timedelta(days=offset)


def moment(offset_days, hour=10):
    stamp = datetime.now(timezone.utc) + timedelta(days=offset_days)
    return stamp.replace(hour=hour, minute=0, second=0, microsecond=0)


# --- small helpers --------------------------------------------------------

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


def ensure_user(name, email, role_code, password_hash):
    """One password hash is computed once and shared by the demo accounts."""
    user = db.session.scalar(db.select(User).filter_by(email=email))
    if user is None:
        user = User(
            name=name, email=email, role=ensure_role(role_code),
            password_hash=password_hash,
        )
        db.session.add(user)
        db.session.flush()
    return user


def make_png(width, height, front, back, blocks=4):
    """A small two-tone PNG, so demo versions have a real preview image."""
    rows = bytearray()
    for y in range(height):
        rows.append(0)
        band = (y * blocks) // height
        for x in range(width):
            colour = front if ((x * blocks) // width + band) % 2 else back
            rows.extend(colour)

    def chunk(kind, payload):
        body = kind + payload
        return pack(">I", len(payload)) + body + pack(">I", zlib.crc32(body))

    header = pack(">IIBBBBB", width, height, 8, 2, 0, 0, 0)
    return (
        b"\x89PNG\r\n\x1a\n"
        + chunk(b"IHDR", header)
        + chunk(b"IDAT", zlib.compress(bytes(rows), 6))
        + chunk(b"IEND", b"")
    )


def attach_preview(version, label, colour, kind="preview"):
    """Write a preview image for a version and record it in version_files."""
    stored_name = f"demo-{version.creative_id}-v{version.version_number}-{kind}.png"
    existing = db.session.scalar(
        db.select(VersionFile).filter_by(stored_name=stored_name)
    )
    folder = Path(current_app.config.get("UPLOAD_FOLDER")
                  or Path(current_app.instance_path) / "uploads")
    folder.mkdir(parents=True, exist_ok=True)
    target = folder / stored_name
    if not target.exists():
        target.write_bytes(make_png(360, 360, colour, (246, 247, 249)))
    if existing:
        return existing
    record = VersionFile(
        creative_version_id=version.id, kind=kind, display_name=label,
        stored_name=stored_name, mime_type="image/png",
        size_bytes=target.stat().st_size,
    )
    db.session.add(record)
    db.session.flush()
    return record


# --- the starter command from the build guide -----------------------------

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
    """Fill every screen: three client organisations and a full history."""
    counts = build_demo_data(password)
    click.echo(
        "Demo data ready: "
        + ", ".join(f"{value} {name}" for name, value in counts.items())
    )
    click.echo(
        "Sign in as manager@example.test, designer@example.test or "
        "client@example.test."
    )


# --- the demo data --------------------------------------------------------

def build_demo_data(password):
    """Create the demo records. Safe to run again: every row is matched first."""
    password_hash = generate_password_hash(password)

    # People ---------------------------------------------------------------
    manager = ensure_user("Dana Price", "manager@example.test", "manager",
                          password_hash)
    producer = ensure_user("Noor Hassan", "producer@example.test", "manager",
                           password_hash)
    designers = {
        "sam": ensure_user("Sam Ortiz", "designer@example.test", "designer",
                           password_hash),
        "mia": ensure_user("Mia Chen", "designer2@example.test", "designer",
                           password_hash),
        "leo": ensure_user("Leo Vance", "designer3@example.test", "designer",
                           password_hash),
    }
    reviewers = {
        "riya": ensure_user("Riya Khan", "client@example.test", "client",
                            password_hash),
        "tom": ensure_user("Tom Lund", "client2@example.test", "client",
                           password_hash),
        "aisha": ensure_user("Aisha Rahman", "client3@example.test", "client",
                             password_hash),
        "omar": ensure_user("Omar Daniels", "client4@example.test", "client",
                            password_hash),
    }

    # Client organisations, members and contacts ---------------------------
    orgs = {}
    for key, name, site in (
        ("northwind", "Northwind Coffee", "https://northwind.example"),
        ("lumen", "Lumen Fitness", "https://lumen.example"),
        ("verity", "Verity Bank", "https://verity.example"),
    ):
        orgs[key] = get_or_create(Client, defaults={"website_url": site}, name=name)

    memberships = (
        ("northwind", "riya", True), ("northwind", "omar", False),
        ("lumen", "tom", True), ("lumen", "aisha", False),
        ("verity", "aisha", True),
    )
    for org_key, person_key, can_approve in memberships:
        get_or_create(
            ClientMembership, defaults={"can_approve": can_approve},
            client_id=orgs[org_key].id, user_id=reviewers[person_key].id,
        )

    contacts = (
        ("northwind", "Riya Khan", "riya@northwind.example", "Brand lead"),
        ("northwind", "Jonah Pike", "jonah@northwind.example", "Head of retail"),
        ("lumen", "Tom Lund", "tom@lumen.example", "Marketing manager"),
        ("lumen", "Elsa Moreau", "elsa@lumen.example", "Social lead"),
        ("verity", "Aisha Rahman", "aisha@verity.example", "Campaign owner"),
    )
    for org_key, name, email, title in contacts:
        get_or_create(ClientContact, defaults={"name": name, "job_title": title},
                      client_id=orgs[org_key].id, email=email)

    # Teams ----------------------------------------------------------------
    teams = {
        "one": get_or_create(Team, defaults={
            "description": "Static ads for food and drink accounts."},
            name="Studio One"),
        "two": get_or_create(Team, defaults={
            "description": "Performance creative for fitness and finance."},
            name="Studio Two"),
    }
    team_members = (
        ("one", "sam", -120), ("one", "mia", -60),
        ("two", "leo", -200), ("two", "mia", -30),
    )
    for team_key, person_key, offset in team_members:
        get_or_create(TeamMembership, defaults={"joined_on": days(offset)},
                      team_id=teams[team_key].id,
                      user_id=designers[person_key].id)

    # Lookup tables --------------------------------------------------------
    channels = {
        name: get_or_create(Channel, name=name)
        for name in ("Instagram feed", "Instagram story", "Display network",
                     "Email", "YouTube pre-roll")
    }
    formats = {
        name: get_or_create(CreativeFormat,
                            defaults={"width_px": w, "height_px": h}, name=name)
        for name, w, h in (
            ("Square 1080", 1080, 1080),
            ("Story 1080 x 1920", 1080, 1920),
            ("Landscape 1200 x 628", 1200, 628),
            ("Leaderboard 728 x 90", 728, 90),
            ("Email banner 600 x 200", 600, 200),
        )
    }
    tags = {
        name: get_or_create(Tag, name=name)
        for name in ("seasonal", "promo", "evergreen", "launch", "retargeting")
    }

    # Brands, guidelines, assets and audiences -----------------------------
    brands = {}
    for key, org_key, name in (
        ("roast", "northwind", "Northwind Roast"),
        ("cold", "northwind", "Northwind Cold Brew"),
        ("studio", "lumen", "Lumen Studio"),
        ("everyday", "verity", "Verity Everyday"),
    ):
        brands[key] = get_or_create(Brand, client_id=orgs[org_key].id, name=name)

    guidelines = (
        ("roast", "Logo contrast", "Use the cream logo on dark backgrounds only."),
        ("roast", "Tone of voice", "Warm and plain. No exclamation marks."),
        ("cold", "Colour", "Cold Brew blue is the only accent on packaging shots."),
        ("studio", "People first", "Show real members, never stock gym photos."),
        ("studio", "Claims", "No before and after body comparisons."),
        ("everyday", "Compliance", "Every rate claim carries the APR footnote."),
    )
    for brand_key, title, rule in guidelines:
        get_or_create(BrandGuideline, defaults={"rule_text": rule},
                      brand_id=brands[brand_key].id, title=title)

    assets = (
        ("roast", "Primary logo", "logo", "https://northwind.example/logo.svg"),
        ("roast", "Pack shots", "photography", "https://northwind.example/packs"),
        ("cold", "Bottle renders", "photography", "https://northwind.example/bottles"),
        ("studio", "Brand font", "font", "https://lumen.example/font"),
        ("studio", "Member photos", "photography", "https://lumen.example/members"),
        ("everyday", "Logo kit", "logo", "https://verity.example/logo"),
    )
    for brand_key, label, kind, url in assets:
        get_or_create(BrandAsset, defaults={"asset_type": kind, "url": url},
                      brand_id=brands[brand_key].id, label=label)

    audiences = {}
    for key, brand_key, label, description in (
        ("commuters", "roast", "Commuters", "City commuters aged 25 to 40."),
        ("home", "roast", "Home brewers", "People who grind beans at home."),
        ("students", "cold", "Students", "Campus buyers who drink cold brew."),
        ("members", "studio", "Lapsed members", "Members who stopped visiting."),
        ("beginners", "studio", "Beginners", "First time gym joiners."),
        ("savers", "everyday", "Savers", "Customers with a savings balance."),
    ):
        audiences[key] = get_or_create(
            Audience, defaults={"description": description},
            brand_id=brands[brand_key].id, label=label,
        )

    # Campaigns, their channels and audiences ------------------------------
    campaigns = {}
    for key, brand_key, team_key, name, start, end, status in (
        ("autumn", "roast", "one", "Autumn Roast Launch", -10, 25, "active"),
        ("holiday", "roast", "one", "Holiday Gifting", 14, 60, "planned"),
        ("coldsummer", "cold", "one", "Cold Brew Summer", -90, -20, "closed"),
        ("comeback", "studio", "two", "January Comeback", -5, 40, "active"),
        ("saver", "everyday", "two", "Everyday Saver", -30, 30, "active"),
    ):
        campaigns[key] = get_or_create(
            Campaign,
            defaults={"team_id": teams[team_key].id, "starts_on": days(start),
                      "ends_on": days(end), "status": status},
            brand_id=brands[brand_key].id, name=name,
        )

    links = {}
    for campaign_key, channel_name, note in (
        ("autumn", "Instagram feed", "Square posts in the main feed."),
        ("autumn", "Instagram story", "Vertical cutdowns for stories."),
        ("autumn", "Email", "Header banner for the weekly email."),
        ("holiday", "Instagram feed", "Gift sets, warm styling."),
        ("coldsummer", "Display network", "Standard display sizes."),
        ("comeback", "Instagram feed", "Member stories."),
        ("comeback", "YouTube pre-roll", "Six second bumper stills."),
        ("saver", "Display network", "Rate led banners."),
        ("saver", "Email", "Monthly statement insert."),
    ):
        links[(campaign_key, channel_name)] = get_or_create(
            CampaignChannel, defaults={"note": note},
            campaign_id=campaigns[campaign_key].id,
            channel_id=channels[channel_name].id,
        )

    for campaign_key, audience_key, priority in (
        ("autumn", "commuters", 1), ("autumn", "home", 2),
        ("holiday", "home", 1), ("coldsummer", "students", 1),
        ("comeback", "members", 1), ("comeback", "beginners", 2),
        ("saver", "savers", 1),
    ):
        get_or_create(CampaignAudience, defaults={"priority": priority},
                      campaign_id=campaigns[campaign_key].id,
                      audience_id=audiences[audience_key].id)

    return _build_work(manager, producer, designers, reviewers, campaigns,
                       links, formats, tags)


def _build_work(manager, producer, designers, reviewers, campaigns, links,
                formats, tags):
    """Briefs, tasks, creatives, reviews and deliveries."""

    # Briefs with their requirements, references and deliverables ----------
    briefs = {}
    for key, campaign_key, author, title, goal, due, status in (
        ("autumn", "autumn", reviewers["riya"], "Autumn roast launch posts",
         "Introduce the autumn roast to city commuters and home brewers.",
         14, "submitted"),
        ("autumn_email", "autumn", reviewers["riya"], "Autumn email banner",
         "Give the weekly email a seasonal header that matches the feed posts.",
         9, "submitted"),
        ("holiday", "holiday", reviewers["omar"], "Holiday gift set teasers",
         "Tease the gift sets before the November sale opens.", 30, "draft"),
        ("comeback", "comeback", reviewers["tom"], "January comeback offer",
         "Bring lapsed members back with a no joining fee offer.", 12,
         "submitted"),
        ("saver", "saver", reviewers["aisha"], "Everyday saver rate banners",
         "Explain the new saver rate in one line, with the APR footnote.",
         20, "submitted"),
    ):
        briefs[key] = get_or_create(
            Brief,
            defaults={"created_by": author.id, "goal": goal,
                      "due_on": days(due), "status": status},
            campaign_id=campaigns[campaign_key].id, title=title,
        )

    requirements = (
        ("autumn", "Product visible", "Show the cup and the roast name in the first glance."),
        ("autumn", "Price point", "Include the 650 rupee bag price."),
        ("autumn", "Legal", "Carry the roastery address in the footer."),
        ("autumn_email", "Width", "Keep the safe area inside 560 pixels."),
        ("holiday", "Gift framing", "Each set must look wrapped and giftable."),
        ("comeback", "Offer", "State no joining fee in January."),
        ("comeback", "Member proof", "Use a real member quote."),
        ("saver", "Rate", "Lead with the rate, follow with the APR footnote."),
        ("saver", "Accessibility", "Body text at 16 pixels or larger."),
    )
    for brief_key, label, details in requirements:
        get_or_create(BriefRequirement, defaults={"details": details},
                      brief_id=briefs[brief_key].id, label=label)

    references = (
        ("autumn", "Moodboard", "https://northwind.example/autumn-moodboard"),
        ("autumn", "Last year's posts", "https://northwind.example/2025-autumn"),
        ("autumn_email", "Email template", "https://northwind.example/email"),
        ("holiday", "Gift set photos", "https://northwind.example/gifts"),
        ("comeback", "Member quotes", "https://lumen.example/quotes"),
        ("saver", "Rate sheet", "https://verity.example/rates"),
    )
    for brief_key, label, url in references:
        get_or_create(BriefReference, defaults={"url": url},
                      brief_id=briefs[brief_key].id, label=label)

    deliverables = {}
    for key, brief_key, link_key, format_name, label, quantity in (
        ("autumn_feed", "autumn", ("autumn", "Instagram feed"), "Square 1080",
         "Square feed posts", 3),
        ("autumn_story", "autumn", ("autumn", "Instagram story"),
         "Story 1080 x 1920", "Story cutdowns", 2),
        ("autumn_mail", "autumn_email", ("autumn", "Email"),
         "Email banner 600 x 200", "Email header", 1),
        ("holiday_feed", "holiday", ("holiday", "Instagram feed"),
         "Square 1080", "Gift set posts", 4),
        ("comeback_feed", "comeback", ("comeback", "Instagram feed"),
         "Square 1080", "Member story posts", 2),
        ("comeback_bumper", "comeback", ("comeback", "YouTube pre-roll"),
         "Landscape 1200 x 628", "Bumper stills", 2),
        ("saver_display", "saver", ("saver", "Display network"),
         "Leaderboard 728 x 90", "Rate leaderboards", 3),
    ):
        deliverables[key] = get_or_create(
            BriefDeliverable,
            defaults={"campaign_channel_id": links[link_key].id,
                      "creative_format_id": formats[format_name].id,
                      "quantity": quantity},
            brief_id=briefs[brief_key].id, label=label,
        )

    # Tasks ----------------------------------------------------------------
    tasks = {}
    for key, brief_key, title, due, status in (
        ("design_feed", "autumn", "Design the square feed posts", 3, "doing"),
        ("retouch", "autumn", "Retouch the pack shots", 5, "todo"),
        ("email", "autumn_email", "Lay out the email header", 2, "done"),
        ("comeback_design", "comeback", "Design the member story posts", 6, "doing"),
        ("saver_display", "saver", "Build the rate leaderboards", 8, "todo"),
    ):
        tasks[key] = get_or_create(
            Task, defaults={"due_on": days(due), "status": status},
            brief_id=briefs[brief_key].id, title=title,
        )

    for task_key, person, note in (
        ("design_feed", designers["sam"], "Lead designer"),
        ("design_feed", designers["mia"], "Second pair of eyes"),
        ("retouch", designers["mia"], None),
        ("email", designers["sam"], None),
        ("comeback_design", designers["leo"], "Lead designer"),
        ("saver_display", designers["leo"], None),
    ):
        get_or_create(TaskAssignee, defaults={"note": note},
                      task_id=tasks[task_key].id, user_id=person.id)

    checklist = (
        ("design_feed", "Export the square preview", True),
        ("design_feed", "Check the logo contrast rule", True),
        ("design_feed", "Add the price point", False),
        ("retouch", "Clean the bag seam", False),
        ("email", "Test in dark mode", True),
        ("comeback_design", "Collect member quotes", True),
        ("comeback_design", "Draft two headline options", False),
        ("saver_display", "Confirm the APR footnote", False),
    )
    for task_key, label, done in checklist:
        get_or_create(TaskChecklistItem, defaults={"is_done": done},
                      task_id=tasks[task_key].id, label=label)

    comments = (
        ("design_feed", designers["sam"],
         "First pass is up. I kept the cup large and the logo on the dark band.", -3),
        ("design_feed", manager,
         "Looks close. Make sure the price sits inside the safe area.", -2),
        ("email", designers["sam"], "Header exported at 600 by 200 and tested.", -6),
        ("comeback_design", designers["leo"],
         "Using the quote from Priya, she agreed to the photo.", -1),
    )
    for task_key, author, body, offset in comments:
        get_or_create(TaskComment, defaults={"created_at": moment(offset)},
                      task_id=tasks[task_key].id, author_id=author.id, body=body)

    return _build_creatives(manager, producer, designers, reviewers, campaigns,
                            deliverables, tags)


def _version(creative, author, number, notes, offset):
    return get_or_create(
        CreativeVersion,
        defaults={"created_by": author.id, "notes": notes,
                  "created_at": moment(offset)},
        creative_id=creative.id, version_number=number,
    )


def _round(version, opener, offset, due=None):
    return get_or_create(
        ReviewRound,
        defaults={"opened_by": opener.id, "opened_at": moment(offset),
                  "due_on": due},
        creative_version_id=version.id,
    )


def _build_creatives(manager, producer, designers, reviewers, campaigns,
                     deliverables, tags):
    """Creatives in every workflow state, plus deliveries."""

    creatives = {}
    for key, deliverable_key, author, name in (
        ("morning", "autumn_feed", designers["sam"], "Morning cup hero"),
        ("beans", "autumn_feed", designers["mia"], "Bean close up"),
        ("grind", "autumn_feed", designers["sam"], "Grind at home"),
        ("story", "autumn_story", designers["mia"], "Autumn story cutdown"),
        ("header", "autumn_mail", designers["sam"], "Autumn email header"),
        ("gift", "holiday_feed", designers["mia"], "Gift set teaser"),
        ("member", "comeback_feed", designers["leo"], "Priya member story"),
        ("bumper", "comeback_bumper", designers["leo"], "Comeback bumper still"),
        ("rate", "saver_display", designers["leo"], "Rate leaderboard"),
    ):
        creatives[key] = get_or_create(
            Creative, defaults={"created_by": author.id},
            brief_deliverable_id=deliverables[deliverable_key].id, name=name,
        )

    for creative_key, tag_name, note in (
        ("morning", "seasonal", "Autumn window"),
        ("morning", "launch", None),
        ("beans", "seasonal", None),
        ("story", "promo", "Story only"),
        ("gift", "seasonal", "Holiday window"),
        ("member", "promo", "January offer"),
        ("member", "retargeting", None),
        ("rate", "evergreen", "Runs all year"),
    ):
        get_or_create(CreativeTag, defaults={"note": note},
                      creative_id=creatives[creative_key].id,
                      tag_id=tags[tag_name].id)

    copy = {}
    for key, creative_key, label, headline, body in (
        ("morning_a", "morning", "Option A", "Your morning, roasted right",
         "The autumn roast lands this week. Warm, nutty, ready at 7am."),
        ("morning_b", "morning", "Option B", "Autumn in a cup",
         "A darker roast for shorter days. 650 rupees a bag."),
        ("beans_a", "beans", "Option A", "Picked this season",
         "Single origin beans, roasted in small batches."),
        ("member_a", "member", "Priya quote", "I came back in January",
         "No joining fee this month. Priya trains three mornings a week."),
        ("rate_a", "rate", "Rate led", "3.8 percent on everyday savings",
         "Representative APR applies. Your rate may vary."),
    ):
        copy[key] = get_or_create(
            CopyVariant, defaults={"headline": headline, "primary_text": body},
            creative_id=creatives[creative_key].id, label=label,
        )

    # 1. Delivered: version 1 sent back, version 2 approved and shipped -----
    morning_v1 = _version(creatives["morning"], designers["sam"], 1,
                          "First pass with the large cup.", -9)
    attach_preview(morning_v1, "morning-cup-v1.png", (143, 94, 62))
    morning_round1 = _round(morning_v1, designers["sam"], -8)
    get_or_create(ReviewAssignment, defaults={"can_decide": True},
                  review_round_id=morning_round1.id,
                  reviewer_id=reviewers["riya"].id)
    get_or_create(ReviewAssignment, defaults={"can_decide": False},
                  review_round_id=morning_round1.id,
                  reviewer_id=reviewers["omar"].id)
    comment = get_or_create(
        ReviewComment, defaults={"created_at": moment(-8, 14)},
        review_round_id=morning_round1.id, author_id=reviewers["riya"].id,
        body="The cup works, but the logo disappears on the light band.",
    )
    get_or_create(ReviewAttachment,
                  defaults={"url": "https://northwind.example/logo-rules"},
                  review_comment_id=comment.id, label="Logo contrast rule")
    get_or_create(
        ReviewDecision,
        defaults={"decided_by": reviewers["riya"].id, "outcome": "changes_requested",
                  "note": "Move the logo onto the dark band and enlarge it.",
                  "created_at": moment(-8, 15)},
        review_round_id=morning_round1.id,
    )
    morning_v2 = _version(creatives["morning"], designers["sam"], 2,
                          "Logo moved to the dark band and enlarged.", -6)
    attach_preview(morning_v2, "morning-cup-v2.png", (92, 64, 51))
    attach_preview(morning_v2, "morning-cup-export.png", (92, 64, 51), kind="export")
    get_or_create(ChangeRequest,
                  defaults={"created_by": reviewers["riya"].id,
                            "resolved_by_version_id": morning_v2.id},
                  review_round_id=morning_round1.id,
                  instruction="Logo on the dark band, at least 120 pixels wide.")
    get_or_create(VersionCopyVariant, defaults={"placement": "Caption"},
                  creative_version_id=morning_v2.id,
                  copy_variant_id=copy["morning_a"].id)
    morning_round2 = _round(morning_v2, designers["sam"], -5)
    get_or_create(ReviewAssignment, defaults={"can_decide": True},
                  review_round_id=morning_round2.id,
                  reviewer_id=reviewers["riya"].id)
    get_or_create(
        ReviewComment, defaults={"created_at": moment(-5, 11)},
        review_round_id=morning_round2.id, author_id=reviewers["riya"].id,
        body="Much better. The price sits well inside the safe area now.",
    )
    get_or_create(
        ReviewDecision,
        defaults={"decided_by": reviewers["riya"].id, "outcome": "approved",
                  "note": "Approved for the feed.", "created_at": moment(-5, 12)},
        review_round_id=morning_round2.id,
    )

    # 2. In review: waiting on the client ----------------------------------
    beans_v1 = _version(creatives["beans"], designers["mia"], 1,
                        "Close up with the seasonal label.", -3)
    attach_preview(beans_v1, "bean-close-up-v1.png", (120, 84, 54))
    beans_round = _round(beans_v1, designers["mia"], -2, due=days(2))
    get_or_create(ReviewAssignment, defaults={"can_decide": True},
                  review_round_id=beans_round.id,
                  reviewer_id=reviewers["riya"].id)
    get_or_create(
        ReviewComment, defaults={"created_at": moment(-1, 9)},
        review_round_id=beans_round.id, author_id=reviewers["omar"].id,
        body="Grain looks lovely. Checking the price with retail before we decide.",
    )
    get_or_create(VersionCopyVariant, defaults={"placement": "Caption"},
                  creative_version_id=beans_v1.id,
                  copy_variant_id=copy["beans_a"].id)

    # 3. Changes requested: the designer owes a new version ----------------
    story_v1 = _version(creatives["story"], designers["mia"], 1,
                        "Vertical crop of the feed post.", -4)
    attach_preview(story_v1, "story-cutdown-v1.png", (168, 120, 74))
    story_round = _round(story_v1, designers["mia"], -4)
    get_or_create(ReviewAssignment, defaults={"can_decide": True},
                  review_round_id=story_round.id,
                  reviewer_id=reviewers["riya"].id)
    get_or_create(
        ReviewDecision,
        defaults={"decided_by": reviewers["riya"].id,
                  "outcome": "changes_requested",
                  "note": "The headline is cropped on a small phone.",
                  "created_at": moment(-3, 16)},
        review_round_id=story_round.id,
    )
    get_or_create(ChangeRequest, defaults={"created_by": reviewers["riya"].id},
                  review_round_id=story_round.id,
                  instruction="Pull the headline 80 pixels up from the bottom.")

    # 4. Approved, waiting for delivery ------------------------------------
    header_v1 = _version(creatives["header"], designers["sam"], 1,
                         "Email header at 600 by 200.", -7)
    attach_preview(header_v1, "email-header-v1.png", (72, 96, 120))
    header_round = _round(header_v1, designers["sam"], -7)
    get_or_create(ReviewAssignment, defaults={"can_decide": True},
                  review_round_id=header_round.id,
                  reviewer_id=reviewers["riya"].id)
    get_or_create(
        ReviewDecision,
        defaults={"decided_by": reviewers["riya"].id, "outcome": "approved",
                  "note": "Looks right in dark mode too.",
                  "created_at": moment(-6, 10)},
        review_round_id=header_round.id,
    )

    # 5. Drafts that never left the studio ---------------------------------
    grind_v1 = _version(creatives["grind"], designers["sam"], 1,
                        "Rough layout, waiting on the grinder photo.", -1)
    attach_preview(grind_v1, "grind-v1.png", (104, 110, 118))
    member_v1 = _version(creatives["member"], designers["leo"], 1,
                         "Member quote over the gym floor shot.", -2)
    attach_preview(member_v1, "member-story-v1.png", (46, 104, 94))
    get_or_create(VersionCopyVariant, defaults={"placement": "Headline"},
                  creative_version_id=member_v1.id,
                  copy_variant_id=copy["member_a"].id)
    _version(creatives["bumper"], designers["leo"], 1, "Still frame draft.", -1)
    rate_v1 = _version(creatives["rate"], designers["leo"], 1,
                       "Rate led leaderboard with the footnote.", -3)
    attach_preview(rate_v1, "rate-leaderboard-v1.png", (38, 70, 122))
    get_or_create(VersionCopyVariant, defaults={"placement": "Banner"},
                  creative_version_id=rate_v1.id,
                  copy_variant_id=copy["rate_a"].id)

    # Deliveries -----------------------------------------------------------
    sent_batch = get_or_create(
        DeliveryBatch,
        defaults={"prepared_by": manager.id, "sent_at": moment(-4, 9)},
        campaign_id=campaigns["autumn"].id, title="Autumn pack 1",
    )
    get_or_create(DeliveryItem, defaults={"label": "Square feed post, final"},
                  delivery_batch_id=sent_batch.id,
                  creative_version_id=morning_v2.id)
    get_or_create(
        DeliveryReceipt,
        defaults={"received_at": moment(-4, 13),
                  "note": "Received, scheduling for Thursday."},
        delivery_batch_id=sent_batch.id, received_by=reviewers["riya"].id,
    )

    draft_batch = get_or_create(
        DeliveryBatch, defaults={"prepared_by": producer.id},
        campaign_id=campaigns["autumn"].id, title="Autumn pack 2",
    )
    get_or_create(DeliveryItem, defaults={"label": "Email header, final"},
                  delivery_batch_id=draft_batch.id,
                  creative_version_id=header_v1.id)

    db.session.commit()

    def total(model):
        return db.session.scalar(db.select(db.func.count()).select_from(model))

    return {
        "users": total(User),
        "clients": total(Client),
        "campaigns": total(Campaign),
        "briefs": total(Brief),
        "creatives": total(Creative),
        "versions": total(CreativeVersion),
        "reviews": total(ReviewRound),
        "deliveries": total(DeliveryBatch),
    }
