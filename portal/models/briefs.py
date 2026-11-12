"""Tables 16-23: client briefs and the tasks they create."""

from datetime import datetime, timezone

from ..extensions import db


def utcnow():
    """Timestamps are stored in UTC."""
    return datetime.now(timezone.utc)


class Brief(db.Model):
    """16 briefs - what the client asks the team to produce."""

    __tablename__ = "briefs"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.ForeignKey("campaigns.id"), nullable=False, index=True
    )
    created_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    goal = db.Column(db.Text, nullable=False)
    due_on = db.Column(db.Date, nullable=False)
    status = db.Column(db.String(16), nullable=False, default="draft")

    campaign = db.relationship("Campaign", back_populates="briefs")
    author = db.relationship("User")
    references = db.relationship(
        "BriefReference", back_populates="brief", passive_deletes="all"
    )
    requirements = db.relationship(
        "BriefRequirement", back_populates="brief", passive_deletes="all"
    )
    deliverables = db.relationship(
        "BriefDeliverable", back_populates="brief", passive_deletes="all"
    )
    tasks = db.relationship(
        "Task", back_populates="brief", passive_deletes="all"
    )

    def __str__(self):
        return self.title


class BriefReference(db.Model):
    """17 brief_references - an inspiration or example link."""

    __tablename__ = "brief_references"

    id = db.Column(db.Integer, primary_key=True)
    brief_id = db.Column(db.ForeignKey("briefs.id"), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(500), nullable=False)

    brief = db.relationship("Brief", back_populates="references")


class BriefRequirement(db.Model):
    """18 brief_requirements - a rule the finished ad must satisfy."""

    __tablename__ = "brief_requirements"

    id = db.Column(db.Integer, primary_key=True)
    brief_id = db.Column(db.ForeignKey("briefs.id"), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    details = db.Column(db.Text, nullable=False)

    brief = db.relationship("Brief", back_populates="requirements")


class BriefDeliverable(db.Model):
    """19 brief_deliverables - how many ads, in which channel and size."""

    __tablename__ = "brief_deliverables"

    id = db.Column(db.Integer, primary_key=True)
    brief_id = db.Column(db.ForeignKey("briefs.id"), nullable=False, index=True)
    campaign_channel_id = db.Column(
        db.ForeignKey("campaign_channels.id"), nullable=False, index=True
    )
    creative_format_id = db.Column(
        db.ForeignKey("creative_formats.id"), nullable=False, index=True
    )
    label = db.Column(db.String(120), nullable=False)
    quantity = db.Column(db.Integer, nullable=False, default=1)

    brief = db.relationship("Brief", back_populates="deliverables")
    campaign_channel = db.relationship(
        "CampaignChannel", back_populates="deliverables"
    )
    creative_format = db.relationship(
        "CreativeFormat", back_populates="deliverables"
    )
    creatives = db.relationship(
        "Creative", back_populates="deliverable", passive_deletes="all"
    )

    def __str__(self):
        return self.label


class Task(db.Model):
    """20 tasks - a unit of production work under a brief."""

    __tablename__ = "tasks"

    id = db.Column(db.Integer, primary_key=True)
    brief_id = db.Column(db.ForeignKey("briefs.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    due_on = db.Column(db.Date)
    status = db.Column(db.String(16), nullable=False, default="todo")

    brief = db.relationship("Brief", back_populates="tasks")
    assignees = db.relationship(
        "TaskAssignee", back_populates="task", passive_deletes="all"
    )
    checklist_items = db.relationship(
        "TaskChecklistItem", back_populates="task", passive_deletes="all"
    )
    comments = db.relationship(
        "TaskComment", back_populates="task", passive_deletes="all"
    )

    def __str__(self):
        return self.title


class TaskAssignee(db.Model):
    """21 task_assignees - bridge: the designers working on a task."""

    __tablename__ = "task_assignees"
    __table_args__ = (db.UniqueConstraint("task_id", "user_id"),)

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.ForeignKey("tasks.id"), nullable=False, index=True)
    user_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    note = db.Column(db.String(200))

    task = db.relationship("Task", back_populates="assignees")
    user = db.relationship("User")


class TaskChecklistItem(db.Model):
    """22 task_checklist_items - a small step inside a task."""

    __tablename__ = "task_checklist_items"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.ForeignKey("tasks.id"), nullable=False, index=True)
    label = db.Column(db.String(160), nullable=False)
    is_done = db.Column(db.Boolean, nullable=False, default=False)

    task = db.relationship("Task", back_populates="checklist_items")


class TaskComment(db.Model):
    """23 task_comments - production chatter on a task."""

    __tablename__ = "task_comments"

    id = db.Column(db.Integer, primary_key=True)
    task_id = db.Column(db.ForeignKey("tasks.id"), nullable=False, index=True)
    author_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    task = db.relationship("Task", back_populates="comments")
    author = db.relationship("User")
