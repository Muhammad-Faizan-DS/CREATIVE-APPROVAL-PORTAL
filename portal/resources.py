"""The record registry that drives the shared create, edit and delete views.

Every table that does not need its own business rules is described here
once: its fields, its list columns, who may change it, and where to go
back to. views/manage.py turns that description into working screens.
"""

from flask import url_for
from werkzeug.security import generate_password_hash

from .access import (
    can_brief,
    can_produce,
    can_view_campaign,
    campaign_of_brief,
    campaign_of_creative,
    campaign_of_deliverable,
    campaign_of_round,
    campaign_of_task,
    campaign_of_version,
    in_client,
    is_client,
    is_manager,
)
from .extensions import db
from .forms import Field
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
from .workflow import (
    CAMPAIGN_STATUSES,
    FILE_KINDS,
    TASK_STATUSES,
    can_start_next_version,
    is_approved,
    is_draft,
    next_version_number,
    version_status,
)


# --- where each record lives ---------------------------------------------

def record_url(obj):
    """The detail page that owns a record."""
    if isinstance(obj, Client):
        return url_for("clients.detail", client_id=obj.id)
    if isinstance(obj, Team):
        return url_for("settings.team_detail", team_id=obj.id)
    if isinstance(obj, Brand):
        return url_for("campaigns.brand_detail", brand_id=obj.id)
    if isinstance(obj, Campaign):
        return url_for("campaigns.campaign_detail", campaign_id=obj.id)
    if isinstance(obj, Brief):
        return url_for("briefs.detail", brief_id=obj.id)
    if isinstance(obj, Task):
        return url_for("briefs.task_detail", task_id=obj.id)
    if isinstance(obj, BriefDeliverable):
        return url_for("creatives.deliverable_detail", deliverable_id=obj.id)
    if isinstance(obj, Creative):
        return url_for("creatives.detail", creative_id=obj.id)
    if isinstance(obj, CreativeVersion):
        return url_for("creatives.version_detail", version_id=obj.id)
    if isinstance(obj, ReviewRound):
        return url_for("reviews.detail", round_id=obj.id)
    if isinstance(obj, ReviewComment):
        return url_for("reviews.detail", round_id=obj.review_round_id)
    if isinstance(obj, DeliveryBatch):
        return url_for("deliveries.detail", batch_id=obj.id)
    raise ValueError(f"No detail page for {type(obj).__name__}")


class Resource:
    """One table managed through the shared screens."""

    def __init__(
        self,
        key,
        model,
        title,
        singular,
        fields,
        columns,
        parent_attr=None,
        parent_model=None,
        allow=None,
        back=None,
        prepare=None,
        validate=None,
        order_by=None,
        top_level=False,
        list_title=None,
        creatable=True,
        editable=True,
        deletable=True,
        nav_group=None,
    ):
        self.key = key
        self.model = model
        self.title = title
        self.singular = singular
        self.fields = fields
        self.columns = columns
        self.parent_attr = parent_attr
        self.parent_model = parent_model
        self._allow = allow or (lambda user, action, parent, obj: is_manager(user))
        self._back = back
        self._prepare = prepare
        self._validate = validate
        self.order_by = order_by
        self.top_level = top_level
        self.list_title = list_title or title
        self.creatable = creatable
        self.editable = editable
        self.deletable = deletable
        self.nav_group = nav_group

    # -- behaviour hooks --
    def allow(self, user, action, parent=None, obj=None):
        return bool(self._allow(user, action, parent, obj))

    def back_url(self, parent=None, obj=None):
        if self._back:
            return self._back(parent, obj)
        if parent is not None:
            return record_url(parent)
        return url_for("manage.index", key=self.key)

    def prepare(self, obj, values, parent, user):
        """Set server-side fields. Return an error message to stop saving."""
        if self._prepare:
            return self._prepare(obj, values, parent, user)
        return None

    def validate(self, obj, values, parent, user):
        if self._validate:
            return self._validate(obj, values, parent, user)
        return None

    def query(self, parent=None):
        query = db.select(self.model)
        if parent is not None and self.parent_attr:
            query = query.filter(
                getattr(self.model, self.parent_attr) == parent.id
            )
        if self.order_by is not None:
            query = query.order_by(*self.order_by())
        else:
            query = query.order_by(self.model.id)
        return query

    def rows(self, parent=None):
        return db.session.scalars(self.query(parent)).all()

    def cells(self, obj):
        return [render(obj) for _, render in self.columns]

    @property
    def headers(self):
        return [header for header, _ in self.columns]


REGISTRY = {}


def register(resource):
    REGISTRY[resource.key] = resource
    return resource


def get_resource(key):
    return REGISTRY.get(key)


# --- reusable choice lists ------------------------------------------------

def _ordered(model, order_column):
    return db.session.scalars(db.select(model).order_by(order_column)).all()


def role_choices(parent, obj):
    return [(r.id, r.label) for r in _ordered(Role, Role.label)]


def user_choices(parent, obj):
    return [
        (u.id, f"{u.name} ({u.role.code})") for u in _ordered(User, User.name)
    ]


def client_choices(parent, obj):
    return [(c.id, c.name) for c in _ordered(Client, Client.name)]


def team_choices(parent, obj):
    return [(t.id, t.name) for t in _ordered(Team, Team.name)]


def brand_choices(parent, obj):
    brands = db.session.scalars(
        db.select(Brand).join(Client).order_by(Client.name, Brand.name)
    ).all()
    return [(b.id, f"{b.client.name} / {b.name}") for b in brands]


def channel_choices(parent, obj):
    return [(c.id, c.name) for c in _ordered(Channel, Channel.name)]


def format_choices(parent, obj):
    return [(f.id, str(f)) for f in _ordered(CreativeFormat, CreativeFormat.name)]


def tag_choices(parent, obj):
    return [(t.id, t.name) for t in _ordered(Tag, Tag.name)]


def designer_choices(parent, obj):
    """Only members of the campaign team may be assigned a task."""
    campaign = campaign_of_task(parent)
    members = sorted(campaign.team.memberships, key=lambda m: m.user.name)
    return [(m.user.id, m.user.name) for m in members]


def reviewer_choices_for_campaign(campaign):
    """Only members of the campaign's client organisation may review."""
    members = sorted(
        campaign.brand.client.memberships, key=lambda m: m.user.name
    )
    return [(m.user.id, m.user.name) for m in members]


def brand_audience_choices(parent, obj):
    """An audience must belong to the campaign's own brand."""
    audiences = sorted(parent.brand.audiences, key=lambda a: a.label)
    return [(a.id, a.label) for a in audiences]


def campaign_channel_choices(parent, obj):
    """A deliverable channel must belong to the brief's campaign."""
    links = sorted(parent.campaign.campaign_channels, key=lambda cc: str(cc))
    return [(cc.id, cc.channel.name) for cc in links]


def creative_copy_choices(parent, obj):
    """Copy variants must come from the version's own creative."""
    variants = sorted(parent.creative.copy_variants, key=lambda c: c.label)
    return [(c.id, c.label) for c in variants]


def sibling_version_choices(parent, obj):
    """A change request is resolved by a later version of the same creative."""
    versions = parent.version.creative.versions
    return [
        (v.id, f"Version {v.version_number}")
        for v in versions
        if v.version_number > parent.version.version_number
    ]


def approved_version_choices(parent, obj):
    """A delivery item must be an approved version of the same campaign."""
    options = []
    for brief in parent.campaign.briefs:
        for deliverable in brief.deliverables:
            for creative in deliverable.creatives:
                for version in creative.versions:
                    if is_approved(version):
                        options.append(
                            (
                                version.id,
                                f"{creative.name} v{version.version_number}",
                            )
                        )
    return sorted(options, key=lambda pair: pair[1])


# --- access rules ---------------------------------------------------------

def managers(user, action, parent, obj):
    return is_manager(user)


def brief_rule(user, action, parent, obj):
    """Brief contents: the client who owns the campaign, while in draft."""
    brief = parent if isinstance(parent, Brief) else getattr(obj, "brief", None)
    if brief is None:
        return False
    campaign = campaign_of_brief(brief)
    if action == "view":
        return can_view_campaign(user, campaign)
    if not can_brief(user, campaign):
        return False
    return brief.status == "draft" or is_manager(user)


def production_rule(user, action, parent, obj):
    """Production records: the campaign's designers and the manager."""
    campaign = _campaign_for(parent, obj)
    if campaign is None:
        return False
    if action == "view":
        return can_view_campaign(user, campaign)
    return can_produce(user, campaign)


def draft_version_rule(user, action, parent, obj):
    """Files and copy links freeze once the version is in review."""
    version = parent if isinstance(parent, CreativeVersion) else None
    if version is None and obj is not None:
        version = obj.version
    if version is None:
        return False
    campaign = campaign_of_version(version)
    if action == "view":
        return can_view_campaign(user, campaign)
    return can_produce(user, campaign) and is_draft(version)


def review_rule(user, action, parent, obj):
    """Review feedback: assigned client reviewers and the manager."""
    review_round = _round_for(parent, obj)
    if review_round is None:
        return False
    campaign = campaign_of_round(review_round)
    if action == "view":
        return can_view_campaign(user, campaign)
    if is_manager(user):
        return True
    if not is_client(user) or not in_client(user, campaign.brand.client_id):
        return False
    assigned = any(a.reviewer_id == user.id for a in review_round.assignments)
    if not assigned:
        return False
    if action == "create":
        return review_round.decision is None
    author_id = getattr(obj, "author_id", None) or getattr(obj, "created_by", None)
    return author_id == user.id


def own_comment_rule(user, action, parent, obj):
    """Attachments follow the comment they hang on."""
    comment = parent if isinstance(parent, ReviewComment) else obj.comment
    return review_rule(user, action, comment.review_round, comment)


def _campaign_for(parent, obj):
    target = parent if parent is not None else obj
    if target is None:
        return None
    if isinstance(target, Campaign):
        return target
    if isinstance(target, Brief):
        return campaign_of_brief(target)
    if isinstance(target, Task):
        return campaign_of_task(target)
    if isinstance(target, BriefDeliverable):
        return campaign_of_deliverable(target)
    if isinstance(target, Creative):
        return campaign_of_creative(target)
    if isinstance(target, CreativeVersion):
        return campaign_of_version(target)
    if isinstance(target, ReviewRound):
        return campaign_of_round(target)
    if isinstance(target, DeliveryBatch):
        return target.campaign
    for attr in ("task", "creative", "version", "brief", "batch"):
        related = getattr(target, attr, None)
        if related is not None:
            return _campaign_for(related, None)
    return None


def _round_for(parent, obj):
    if isinstance(parent, ReviewRound):
        return parent
    if obj is not None:
        return getattr(obj, "review_round", None)
    return None


# --- small helpers used by the list columns -------------------------------

Resource.has_detail = False


def text(value):
    return "" if value is None else str(value)


def yes_no(flag):
    return "Yes" if flag else "No"


def stamp(value):
    return value.strftime("%Y-%m-%d %H:%M") if value else ""


def _register_detail(resource):
    resource.has_detail = True
    return resource


# --- 01-07 accounts, clients and teams ------------------------------------

register(Resource(
    key="roles", model=Role, title="Roles", singular="role",
    top_level=True, nav_group="Settings",
    fields=[
        Field("code", "Code", maxlength=32),
        Field("label", "Label", maxlength=80),
    ],
    columns=[("Code", lambda o: o.code), ("Label", lambda o: o.label)],
    order_by=lambda: [Role.label],
))


def _prepare_user(obj, values, parent, user):
    password = values.pop("password", None)
    if obj.id is None and not password:
        return "Enter a password for the new account."
    if password:
        if len(password) < 8:
            return "Use a password of at least 8 characters."
        obj.password_hash = generate_password_hash(password)
    return None


register(Resource(
    key="users", model=User, title="Users", singular="user",
    top_level=True, nav_group="Settings",
    fields=[
        Field("role_id", "Role", kind="select", choices=role_choices),
        Field("name", "Name", maxlength=120),
        Field("email", "Email", kind="email", maxlength=254),
        Field("password", "Password", required=False, maxlength=128,
              help_text="Leave blank to keep the current password."),
        Field("is_active", "Active", kind="bool", required=False),
    ],
    columns=[
        ("Name", lambda o: o.name),
        ("Email", lambda o: o.email),
        ("Role", lambda o: o.role.label),
        ("Active", lambda o: yes_no(o.is_active)),
    ],
    order_by=lambda: [User.name],
    prepare=_prepare_user,
))

_register_detail(register(Resource(
    key="clients", model=Client, title="Clients", singular="client",
    top_level=True, nav_group="Records",
    fields=[
        Field("name", "Name", maxlength=120),
        Field("website_url", "Website", kind="url", required=False,
              maxlength=500),
    ],
    columns=[
        ("Name", lambda o: o.name),
        ("Website", lambda o: text(o.website_url)),
        ("Brands", lambda o: len(o.brands)),
    ],
    order_by=lambda: [Client.name],
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else url_for("clients.index")
    ),
)))

register(Resource(
    key="client_memberships", model=ClientMembership,
    title="Members", singular="member",
    parent_attr="client_id", parent_model=Client,
    fields=[
        Field("user_id", "Reviewer", kind="select", choices=user_choices,
              create_only=True),
        Field("can_approve", "Can approve", kind="bool", required=False),
    ],
    columns=[
        ("Reviewer", lambda o: o.user.name),
        ("Role", lambda o: o.user.role.label),
        ("Can approve", lambda o: yes_no(o.can_approve)),
    ],
))

_register_detail(register(Resource(
    key="teams", model=Team, title="Teams", singular="team",
    top_level=True, nav_group="Settings",
    fields=[
        Field("name", "Name", maxlength=120),
        Field("description", "Description", kind="textarea", required=False),
    ],
    columns=[
        ("Name", lambda o: o.name),
        ("Members", lambda o: len(o.memberships)),
        ("Campaigns", lambda o: len(o.campaigns)),
    ],
    order_by=lambda: [Team.name],
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else url_for("manage.index",
                                                        key="teams")
    ),
)))

register(Resource(
    key="team_memberships", model=TeamMembership,
    title="Members", singular="member",
    parent_attr="team_id", parent_model=Team,
    fields=[
        Field("user_id", "Designer", kind="select", choices=user_choices,
              create_only=True),
        Field("joined_on", "Joined on", kind="date"),
    ],
    columns=[
        ("Designer", lambda o: o.user.name),
        ("Role", lambda o: o.user.role.label),
        ("Joined", lambda o: text(o.joined_on)),
    ],
))

register(Resource(
    key="client_contacts", model=ClientContact,
    title="Contacts", singular="contact",
    parent_attr="client_id", parent_model=Client,
    fields=[
        Field("name", "Name", maxlength=120),
        Field("email", "Email", kind="email", maxlength=254),
        Field("job_title", "Job title", required=False, maxlength=120),
    ],
    columns=[
        ("Name", lambda o: o.name),
        ("Email", lambda o: o.email),
        ("Job title", lambda o: text(o.job_title)),
    ],
))


# --- 09-15 brand and campaign detail --------------------------------------

register(Resource(
    key="brand_guidelines", model=BrandGuideline,
    title="Guidelines", singular="guideline",
    parent_attr="brand_id", parent_model=Brand,
    fields=[
        Field("title", "Title", maxlength=120),
        Field("rule_text", "Rule", kind="textarea"),
    ],
    columns=[
        ("Title", lambda o: o.title),
        ("Rule", lambda o: o.rule_text),
    ],
))

register(Resource(
    key="brand_assets", model=BrandAsset, title="Assets", singular="asset",
    parent_attr="brand_id", parent_model=Brand,
    fields=[
        Field("label", "Label", maxlength=120),
        Field("asset_type", "Asset type", maxlength=32),
        Field("url", "Link", kind="url", maxlength=500),
    ],
    columns=[
        ("Label", lambda o: o.label),
        ("Type", lambda o: o.asset_type),
        ("Link", lambda o: o.url),
    ],
))

register(Resource(
    key="audiences", model=Audience, title="Audiences", singular="audience",
    parent_attr="brand_id", parent_model=Brand,
    fields=[
        Field("label", "Label", maxlength=120),
        Field("description", "Description", kind="textarea"),
    ],
    columns=[
        ("Label", lambda o: o.label),
        ("Description", lambda o: o.description),
        ("Campaigns", lambda o: len(o.campaign_audiences)),
    ],
))

register(Resource(
    key="channels", model=Channel, title="Channels", singular="channel",
    top_level=True, nav_group="Settings",
    fields=[Field("name", "Name", maxlength=80)],
    columns=[
        ("Name", lambda o: o.name),
        ("Campaigns", lambda o: len(o.campaign_channels)),
    ],
    order_by=lambda: [Channel.name],
))


def _validate_campaign(obj, values, parent, user):
    starts_on = values.get("starts_on")
    ends_on = values.get("ends_on")
    if starts_on and ends_on and ends_on < starts_on:
        return "The end date cannot fall before the start date."
    return None


_register_detail(register(Resource(
    key="campaigns", model=Campaign, title="Campaigns", singular="campaign",
    top_level=True, nav_group="Records",
    fields=[
        Field("brand_id", "Brand", kind="select", choices=brand_choices,
              create_only=True),
        Field("team_id", "Team", kind="select", choices=team_choices),
        Field("name", "Name", maxlength=120),
        Field("starts_on", "Starts on", kind="date"),
        Field("ends_on", "Ends on", kind="date", required=False),
        Field("status", "Status", kind="enum", values=CAMPAIGN_STATUSES),
    ],
    columns=[
        ("Campaign", lambda o: o.name),
        ("Brand", lambda o: f"{o.brand.client.name} / {o.brand.name}"),
        ("Team", lambda o: o.team.name),
        ("Starts", lambda o: text(o.starts_on)),
        ("Status", lambda o: o.status),
    ],
    order_by=lambda: [Campaign.name],
    validate=_validate_campaign,
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else url_for("manage.index",
                                                        key="campaigns")
    ),
)))

register(Resource(
    key="campaign_channels", model=CampaignChannel,
    title="Channels", singular="channel link",
    parent_attr="campaign_id", parent_model=Campaign,
    fields=[
        Field("channel_id", "Channel", kind="select", choices=channel_choices,
              create_only=True),
        Field("note", "Note", kind="textarea", required=False),
    ],
    columns=[
        ("Channel", lambda o: o.channel.name),
        ("Note", lambda o: text(o.note)),
        ("Deliverables", lambda o: len(o.deliverables)),
    ],
))

register(Resource(
    key="campaign_audiences", model=CampaignAudience,
    title="Audiences", singular="audience link",
    parent_attr="campaign_id", parent_model=Campaign,
    fields=[
        Field("audience_id", "Audience", kind="select",
              choices=brand_audience_choices, create_only=True),
        Field("priority", "Priority", kind="int", min_value=1, max_value=99),
    ],
    columns=[
        ("Audience", lambda o: o.audience.label),
        ("Priority", lambda o: o.priority),
    ],
    order_by=lambda: [CampaignAudience.priority],
))


# --- 16-23 briefs and tasks -----------------------------------------------

def brief_record_rule(user, action, parent, obj):
    """A brief belongs to the client who wrote it; drafts stay editable."""
    campaign = parent
    if action == "view":
        return can_view_campaign(user, campaign)
    if not can_brief(user, campaign):
        return False
    if obj is not None and obj.status != "draft" and not is_manager(user):
        return False
    return True


def _stamp_author(attr):
    def prepare(obj, values, parent, user):
        if obj.id is None:
            setattr(obj, attr, user.id)
        return None

    return prepare


register(Resource(
    key="briefs", model=Brief, title="Briefs", singular="brief",
    parent_attr="campaign_id", parent_model=Campaign,
    allow=brief_record_rule,
    fields=[
        Field("title", "Title", maxlength=160),
        Field("goal", "Goal", kind="textarea"),
        Field("due_on", "Due on", kind="date"),
    ],
    columns=[
        ("Title", lambda o: o.title),
        ("Due", lambda o: text(o.due_on)),
        ("Status", lambda o: o.status),
        ("Deliverables", lambda o: len(o.deliverables)),
    ],
    prepare=_stamp_author("created_by"),
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else record_url(parent)
    ),
))
REGISTRY["briefs"].has_detail = True

register(Resource(
    key="brief_references", model=BriefReference,
    title="References", singular="reference",
    parent_attr="brief_id", parent_model=Brief, allow=brief_rule,
    fields=[
        Field("label", "Label", maxlength=120),
        Field("url", "Link", kind="url", maxlength=500),
    ],
    columns=[("Label", lambda o: o.label), ("Link", lambda o: o.url)],
))

register(Resource(
    key="brief_requirements", model=BriefRequirement,
    title="Requirements", singular="requirement",
    parent_attr="brief_id", parent_model=Brief, allow=brief_rule,
    fields=[
        Field("label", "Label", maxlength=120),
        Field("details", "Details", kind="textarea"),
    ],
    columns=[("Label", lambda o: o.label), ("Details", lambda o: o.details)],
))

register(Resource(
    key="brief_deliverables", model=BriefDeliverable,
    title="Deliverables", singular="deliverable",
    parent_attr="brief_id", parent_model=Brief, allow=brief_rule,
    fields=[
        Field("campaign_channel_id", "Channel", kind="select",
              choices=campaign_channel_choices, create_only=True),
        Field("creative_format_id", "Format", kind="select",
              choices=format_choices, create_only=True),
        Field("label", "Label", maxlength=120),
        Field("quantity", "Quantity", kind="int", min_value=1, max_value=999),
    ],
    columns=[
        ("Label", lambda o: o.label),
        ("Channel", lambda o: o.campaign_channel.channel.name),
        ("Format", lambda o: str(o.creative_format)),
        ("Quantity", lambda o: o.quantity),
        ("Creatives", lambda o: len(o.creatives)),
    ],
))
REGISTRY["brief_deliverables"].has_detail = True


def task_rule(user, action, parent, obj):
    """Managers plan tasks; the campaign's designers update them."""
    campaign = _campaign_for(parent, obj)
    if campaign is None:
        return False
    if action == "view":
        return can_view_campaign(user, campaign)
    if action == "edit":
        return can_produce(user, campaign)
    return is_manager(user)


register(Resource(
    key="tasks", model=Task, title="Tasks", singular="task",
    parent_attr="brief_id", parent_model=Brief, allow=task_rule,
    fields=[
        Field("title", "Title", maxlength=160),
        Field("due_on", "Due on", kind="date", required=False),
        Field("status", "Status", kind="enum", values=TASK_STATUSES),
    ],
    columns=[
        ("Task", lambda o: o.title),
        ("Due", lambda o: text(o.due_on)),
        ("Status", lambda o: o.status),
        ("Assignees", lambda o: len(o.assignees)),
    ],
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else record_url(parent)
    ),
))
REGISTRY["tasks"].has_detail = True

register(Resource(
    key="task_assignees", model=TaskAssignee,
    title="Assignees", singular="assignee",
    parent_attr="task_id", parent_model=Task,
    fields=[
        Field("user_id", "Designer", kind="select", choices=designer_choices,
              create_only=True),
        Field("note", "Note", required=False, maxlength=200),
    ],
    columns=[
        ("Designer", lambda o: o.user.name),
        ("Note", lambda o: text(o.note)),
    ],
))

register(Resource(
    key="task_checklist_items", model=TaskChecklistItem,
    title="Checklist", singular="checklist item",
    parent_attr="task_id", parent_model=Task, allow=production_rule,
    fields=[
        Field("label", "Step", maxlength=160),
        Field("is_done", "Done", kind="bool", required=False),
    ],
    columns=[
        ("Step", lambda o: o.label),
        ("Done", lambda o: yes_no(o.is_done)),
    ],
))


def own_record_rule(base_rule, author_attr):
    """Everyone with access may post; only the author may change a post."""

    def rule(user, action, parent, obj):
        if not base_rule(user, action, parent, obj):
            return False
        if action in ("view", "create"):
            return True
        return is_manager(user) or getattr(obj, author_attr, None) == user.id

    return rule


register(Resource(
    key="task_comments", model=TaskComment,
    title="Comments", singular="comment",
    parent_attr="task_id", parent_model=Task,
    allow=own_record_rule(production_rule, "author_id"),
    fields=[Field("body", "Comment", kind="textarea")],
    columns=[
        ("Author", lambda o: o.author.name),
        ("Comment", lambda o: o.body),
        ("Posted", lambda o: stamp(o.created_at)),
    ],
    order_by=lambda: [TaskComment.created_at],
    prepare=_stamp_author("author_id"),
))


# --- 24-31 creatives, versions, files, copy and tags ----------------------

def creative_rule(user, action, parent, obj):
    """Drafts may only start once the brief has been submitted."""
    if not production_rule(user, action, parent, obj):
        return False
    if action == "view":
        return True
    deliverable = parent if isinstance(parent, BriefDeliverable) else None
    if deliverable is not None and deliverable.brief.status != "submitted":
        return False
    return True


register(Resource(
    key="creatives", model=Creative, title="Creatives", singular="creative",
    parent_attr="brief_deliverable_id", parent_model=BriefDeliverable,
    allow=creative_rule,
    fields=[Field("name", "Name", maxlength=160)],
    columns=[
        ("Creative", lambda o: o.name),
        ("Versions", lambda o: len(o.versions)),
        ("Status", lambda o: (
            version_status(o.latest_version) if o.latest_version
            else "No version yet"
        )),
    ],
    prepare=_stamp_author("created_by"),
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else record_url(parent)
    ),
))
REGISTRY["creatives"].has_detail = True


def _prepare_version(obj, values, parent, user):
    if obj.id is None:
        obj.created_by = user.id
        obj.version_number = next_version_number(parent)
    return None


def _validate_version(obj, values, parent, user):
    if obj.id is None and not can_start_next_version(parent):
        return (
            "Finish the current version first. A new version can only start "
            "after the client requests changes."
        )
    return None


def version_record_rule(user, action, parent, obj):
    """A reviewed version stays as history; only drafts change."""
    if not production_rule(user, action, parent, obj):
        return False
    if action in ("view", "create"):
        return True
    return obj is None or is_draft(obj)


register(Resource(
    key="creative_versions", model=CreativeVersion,
    title="Versions", singular="version",
    parent_attr="creative_id", parent_model=Creative,
    allow=version_record_rule,
    fields=[Field("notes", "Notes", kind="textarea", required=False)],
    columns=[
        ("Version", lambda o: o.version_number),
        ("Status", lambda o: version_status(o)),
        ("Files", lambda o: len(o.files)),
        ("Created", lambda o: stamp(o.created_at)),
    ],
    order_by=lambda: [CreativeVersion.version_number],
    prepare=_prepare_version,
    validate=_validate_version,
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else record_url(parent)
    ),
))
REGISTRY["creative_versions"].has_detail = True

register(Resource(
    key="creative_formats", model=CreativeFormat,
    title="Formats", singular="format",
    top_level=True, nav_group="Settings",
    fields=[
        Field("name", "Name", maxlength=80),
        Field("width_px", "Width in pixels", kind="int", min_value=1,
              max_value=10000),
        Field("height_px", "Height in pixels", kind="int", min_value=1,
              max_value=10000),
    ],
    columns=[
        ("Name", lambda o: o.name),
        ("Width", lambda o: o.width_px),
        ("Height", lambda o: o.height_px),
    ],
    order_by=lambda: [CreativeFormat.name],
))

register(Resource(
    key="version_files", model=VersionFile, title="Files", singular="file",
    parent_attr="creative_version_id", parent_model=CreativeVersion,
    allow=draft_version_rule, creatable=False,
    fields=[
        Field("display_name", "Display name", maxlength=160),
        Field("kind", "Kind", kind="enum", values=FILE_KINDS),
    ],
    columns=[
        ("File", lambda o: o.display_name),
        ("Kind", lambda o: o.kind),
        ("Type", lambda o: o.mime_type),
        ("Size", lambda o: f"{o.size_bytes} bytes"),
    ],
))

register(Resource(
    key="copy_variants", model=CopyVariant, title="Copy", singular="copy variant",
    parent_attr="creative_id", parent_model=Creative, allow=production_rule,
    fields=[
        Field("label", "Label", maxlength=120),
        Field("headline", "Headline", maxlength=200),
        Field("primary_text", "Primary text", kind="textarea"),
    ],
    columns=[
        ("Label", lambda o: o.label),
        ("Headline", lambda o: o.headline),
        ("Used in", lambda o: len(o.version_links)),
    ],
))

register(Resource(
    key="version_copy_variants", model=VersionCopyVariant,
    title="Copy", singular="copy link",
    parent_attr="creative_version_id", parent_model=CreativeVersion,
    allow=draft_version_rule,
    fields=[
        Field("copy_variant_id", "Copy variant", kind="select",
              choices=creative_copy_choices, create_only=True),
        Field("placement", "Placement", required=False, maxlength=80),
    ],
    columns=[
        ("Copy", lambda o: o.copy_variant.label),
        ("Headline", lambda o: o.copy_variant.headline),
        ("Placement", lambda o: text(o.placement)),
    ],
))

register(Resource(
    key="tags", model=Tag, title="Tags", singular="tag",
    top_level=True, nav_group="Settings",
    fields=[Field("name", "Name", maxlength=60)],
    columns=[
        ("Name", lambda o: o.name),
        ("Creatives", lambda o: len(o.creative_tags)),
    ],
    order_by=lambda: [Tag.name],
))

register(Resource(
    key="creative_tags", model=CreativeTag, title="Tags", singular="tag link",
    parent_attr="creative_id", parent_model=Creative, allow=production_rule,
    fields=[
        Field("tag_id", "Tag", kind="select", choices=tag_choices,
              create_only=True),
        Field("note", "Note", required=False, maxlength=200),
    ],
    columns=[
        ("Tag", lambda o: o.tag.name),
        ("Note", lambda o: text(o.note)),
    ],
))


# --- 32-40 reviews and deliveries -----------------------------------------

def assignment_rule(user, action, parent, obj):
    """The manager keeps the reviewer list current until a decision lands."""
    review_round = _round_for(parent, obj)
    if review_round is None:
        return False
    campaign = campaign_of_round(review_round)
    if action == "view":
        return can_view_campaign(user, campaign)
    return is_manager(user) and review_round.decision is None


def _reviewer_choices(parent, obj):
    return reviewer_choices_for_campaign(campaign_of_round(parent))


register(Resource(
    key="review_assignments", model=ReviewAssignment,
    title="Reviewers", singular="reviewer",
    parent_attr="review_round_id", parent_model=ReviewRound,
    allow=assignment_rule,
    fields=[
        Field("reviewer_id", "Reviewer", kind="select",
              choices=_reviewer_choices, create_only=True),
        Field("can_decide", "Can decide", kind="bool", required=False),
    ],
    columns=[
        ("Reviewer", lambda o: o.reviewer.name),
        ("Can decide", lambda o: yes_no(o.can_decide)),
    ],
))

register(Resource(
    key="review_comments", model=ReviewComment,
    title="Comments", singular="comment",
    parent_attr="review_round_id", parent_model=ReviewRound,
    allow=review_rule,
    fields=[Field("body", "Comment", kind="textarea")],
    columns=[
        ("Author", lambda o: o.author.name),
        ("Comment", lambda o: o.body),
        ("Posted", lambda o: stamp(o.created_at)),
    ],
    order_by=lambda: [ReviewComment.created_at],
    prepare=_stamp_author("author_id"),
))
REGISTRY["review_comments"].has_detail = False

register(Resource(
    key="review_attachments", model=ReviewAttachment,
    title="References", singular="reference",
    parent_attr="review_comment_id", parent_model=ReviewComment,
    allow=own_comment_rule,
    fields=[
        Field("label", "Label", maxlength=120),
        Field("url", "Link", kind="url", maxlength=500),
    ],
    columns=[("Label", lambda o: o.label), ("Link", lambda o: o.url)],
))


def _validate_change_request(obj, values, parent, user):
    """A change request is only resolved by a later version of the creative."""
    version_id = values.get("resolved_by_version_id")
    if version_id is None:
        return None
    allowed = {pair[0] for pair in sibling_version_choices(parent, obj)}
    if version_id not in allowed:
        return "Choose a later version of the same creative."
    return None


register(Resource(
    key="change_requests", model=ChangeRequest,
    title="Changes", singular="change request",
    parent_attr="review_round_id", parent_model=ReviewRound,
    allow=review_rule,
    fields=[
        Field("instruction", "Instruction", kind="textarea"),
        Field("resolved_by_version_id", "Resolved by version", kind="select",
              choices=sibling_version_choices, required=False),
    ],
    columns=[
        ("Instruction", lambda o: o.instruction),
        ("Raised by", lambda o: o.author.name),
        ("Resolved by", lambda o: (
            f"Version {o.resolved_by_version.version_number}"
            if o.resolved_by_version else "Open"
        )),
    ],
    prepare=_stamp_author("created_by"),
    validate=_validate_change_request,
))

def batch_rule(user, action, parent, obj):
    """The manager prepares batches; a sent batch stays as history."""
    campaign = parent if isinstance(parent, Campaign) else obj.campaign
    if action == "view":
        return is_manager(user) or can_produce(user, campaign)
    if not is_manager(user):
        return False
    if action == "delete" and obj is not None and obj.is_sent:
        return False
    return True


register(Resource(
    key="delivery_batches", model=DeliveryBatch,
    title="Deliveries", singular="delivery batch",
    parent_attr="campaign_id", parent_model=Campaign, allow=batch_rule,
    fields=[Field("title", "Title", maxlength=160)],
    columns=[
        ("Batch", lambda o: o.title),
        ("Items", lambda o: len(o.items)),
        ("Sent", lambda o: stamp(o.sent_at) or "Draft"),
        ("Receipts", lambda o: len(o.receipts)),
    ],
    prepare=_stamp_author("prepared_by"),
    back=lambda parent, obj: (
        record_url(obj) if obj is not None else record_url(parent)
    ),
))
REGISTRY["delivery_batches"].has_detail = True


def delivery_item_rule(user, action, parent, obj):
    """Items may only change while the batch is still a draft."""
    batch = parent if isinstance(parent, DeliveryBatch) else obj.batch
    if action == "view":
        return can_view_campaign(user, batch.campaign)
    return is_manager(user) and not batch.is_sent


def _validate_delivery_item(obj, values, parent, user):
    version_id = values.get("creative_version_id")
    if version_id is None:
        return None
    allowed = {pair[0] for pair in approved_version_choices(parent, obj)}
    if version_id not in allowed:
        return "Only an approved version from this campaign can be delivered."
    return None


register(Resource(
    key="delivery_items", model=DeliveryItem, title="Items", singular="item",
    parent_attr="delivery_batch_id", parent_model=DeliveryBatch,
    allow=delivery_item_rule,
    fields=[
        Field("creative_version_id", "Approved version", kind="select",
              choices=approved_version_choices, create_only=True),
        Field("label", "Label", maxlength=160),
    ],
    columns=[
        ("Label", lambda o: o.label),
        ("Creative", lambda o: o.version.creative.name),
        ("Version", lambda o: o.version.version_number),
    ],
    validate=_validate_delivery_item,
))


def receipt_rule(user, action, parent, obj):
    """A client records, edits or withdraws only their own receipt."""
    batch = parent if isinstance(parent, DeliveryBatch) else obj.batch
    if action == "view":
        return can_view_campaign(user, batch.campaign)
    if not is_client(user) or not in_client(user, batch.campaign.brand.client_id):
        return False
    if obj is None:
        return batch.is_sent
    return obj.received_by == user.id


register(Resource(
    key="delivery_receipts", model=DeliveryReceipt,
    title="Receipts", singular="receipt",
    parent_attr="delivery_batch_id", parent_model=DeliveryBatch,
    allow=receipt_rule, creatable=False,
    fields=[Field("note", "Note", kind="textarea", required=False)],
    columns=[
        ("Recipient", lambda o: o.recipient.name),
        ("Received", lambda o: stamp(o.received_at)),
        ("Note", lambda o: text(o.note)),
    ],
))


def settings_groups():
    """The lookup tables shown on the Settings page."""
    return [
        REGISTRY[key] for key in
        ("roles", "users", "teams", "channels", "creative_formats", "tags")
    ]
