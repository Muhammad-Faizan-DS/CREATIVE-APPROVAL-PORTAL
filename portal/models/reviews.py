"""Tables 32-40: review rounds, decisions and delivery batches."""

from ..extensions import db
from .briefs import utcnow


class ReviewRound(db.Model):
    """32 review_rounds - one client review of one creative version."""

    __tablename__ = "review_rounds"

    id = db.Column(db.Integer, primary_key=True)
    creative_version_id = db.Column(
        db.ForeignKey("creative_versions.id"), nullable=False, unique=True
    )
    opened_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    opened_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    due_on = db.Column(db.Date)

    version = db.relationship("CreativeVersion", back_populates="review_round")
    opener = db.relationship("User")
    assignments = db.relationship(
        "ReviewAssignment", back_populates="review_round", passive_deletes="all"
    )
    comments = db.relationship(
        "ReviewComment", back_populates="review_round", passive_deletes="all"
    )
    decision = db.relationship(
        "ReviewDecision",
        back_populates="review_round",
        uselist=False,
        passive_deletes="all",
    )
    change_requests = db.relationship(
        "ChangeRequest", back_populates="review_round", passive_deletes="all"
    )

    def __str__(self):
        return f"Review of version {self.version.version_number}"


class ReviewAssignment(db.Model):
    """33 review_assignments - bridge: the reviewers on a round."""

    __tablename__ = "review_assignments"
    __table_args__ = (db.UniqueConstraint("review_round_id", "reviewer_id"),)

    id = db.Column(db.Integer, primary_key=True)
    review_round_id = db.Column(
        db.ForeignKey("review_rounds.id"), nullable=False, index=True
    )
    reviewer_id = db.Column(
        db.ForeignKey("users.id"), nullable=False, index=True
    )
    can_decide = db.Column(db.Boolean, nullable=False, default=True)

    review_round = db.relationship("ReviewRound", back_populates="assignments")
    reviewer = db.relationship("User")


class ReviewComment(db.Model):
    """34 review_comments - client feedback inside a round."""

    __tablename__ = "review_comments"

    id = db.Column(db.Integer, primary_key=True)
    review_round_id = db.Column(
        db.ForeignKey("review_rounds.id"), nullable=False, index=True
    )
    author_id = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    body = db.Column(db.Text, nullable=False)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    review_round = db.relationship("ReviewRound", back_populates="comments")
    author = db.relationship("User")
    attachments = db.relationship(
        "ReviewAttachment", back_populates="comment", passive_deletes="all"
    )


class ReviewDecision(db.Model):
    """35 review_decisions - the one outcome recorded for a round."""

    __tablename__ = "review_decisions"

    id = db.Column(db.Integer, primary_key=True)
    review_round_id = db.Column(
        db.ForeignKey("review_rounds.id"), nullable=False, unique=True
    )
    decided_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    outcome = db.Column(db.String(24), nullable=False)
    note = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    review_round = db.relationship("ReviewRound", back_populates="decision")
    decider = db.relationship("User")


class ChangeRequest(db.Model):
    """36 change_requests - a change the designer must make next."""

    __tablename__ = "change_requests"

    id = db.Column(db.Integer, primary_key=True)
    review_round_id = db.Column(
        db.ForeignKey("review_rounds.id"), nullable=False, index=True
    )
    created_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    instruction = db.Column(db.Text, nullable=False)
    resolved_by_version_id = db.Column(
        db.ForeignKey("creative_versions.id"), index=True
    )

    review_round = db.relationship("ReviewRound", back_populates="change_requests")
    author = db.relationship("User")
    resolved_by_version = db.relationship("CreativeVersion")


class ReviewAttachment(db.Model):
    """37 review_attachments - a reference link on a review comment."""

    __tablename__ = "review_attachments"

    id = db.Column(db.Integer, primary_key=True)
    review_comment_id = db.Column(
        db.ForeignKey("review_comments.id"), nullable=False, index=True
    )
    label = db.Column(db.String(120), nullable=False)
    url = db.Column(db.String(500), nullable=False)

    comment = db.relationship("ReviewComment", back_populates="attachments")


class DeliveryBatch(db.Model):
    """38 delivery_batches - approved files handed to the client."""

    __tablename__ = "delivery_batches"

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.ForeignKey("campaigns.id"), nullable=False, index=True
    )
    prepared_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    title = db.Column(db.String(160), nullable=False)
    sent_at = db.Column(db.DateTime)

    campaign = db.relationship("Campaign", back_populates="delivery_batches")
    preparer = db.relationship("User")
    items = db.relationship(
        "DeliveryItem", back_populates="batch", passive_deletes="all"
    )
    receipts = db.relationship(
        "DeliveryReceipt", back_populates="batch", passive_deletes="all"
    )

    def __str__(self):
        return self.title

    @property
    def is_sent(self):
        return self.sent_at is not None


class DeliveryItem(db.Model):
    """39 delivery_items - bridge: an approved version inside a batch."""

    __tablename__ = "delivery_items"
    __table_args__ = (
        db.UniqueConstraint("delivery_batch_id", "creative_version_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    delivery_batch_id = db.Column(
        db.ForeignKey("delivery_batches.id"), nullable=False, index=True
    )
    creative_version_id = db.Column(
        db.ForeignKey("creative_versions.id"), nullable=False, index=True
    )
    label = db.Column(db.String(160), nullable=False)

    batch = db.relationship("DeliveryBatch", back_populates="items")
    version = db.relationship("CreativeVersion", back_populates="delivery_items")


class DeliveryReceipt(db.Model):
    """40 delivery_receipts - the client acknowledging a sent batch."""

    __tablename__ = "delivery_receipts"
    __table_args__ = (
        db.UniqueConstraint("delivery_batch_id", "received_by"),
    )

    id = db.Column(db.Integer, primary_key=True)
    delivery_batch_id = db.Column(
        db.ForeignKey("delivery_batches.id"), nullable=False, index=True
    )
    received_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    received_at = db.Column(db.DateTime, nullable=False, default=utcnow)
    note = db.Column(db.Text)

    batch = db.relationship("DeliveryBatch", back_populates="receipts")
    recipient = db.relationship("User")
