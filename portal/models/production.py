"""Tables 24-31: creatives, their versions, files, copy and tags."""

from ..extensions import db
from .briefs import utcnow


class Creative(db.Model):
    """24 creatives - one ad concept under a brief deliverable."""

    __tablename__ = "creatives"

    id = db.Column(db.Integer, primary_key=True)
    brief_deliverable_id = db.Column(
        db.ForeignKey("brief_deliverables.id"), nullable=False, index=True
    )
    created_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    name = db.Column(db.String(160), nullable=False)

    deliverable = db.relationship("BriefDeliverable", back_populates="creatives")
    author = db.relationship("User")
    versions = db.relationship(
        "CreativeVersion",
        back_populates="creative",
        passive_deletes="all",
        order_by="CreativeVersion.version_number",
    )
    copy_variants = db.relationship(
        "CopyVariant", back_populates="creative", passive_deletes="all"
    )
    creative_tags = db.relationship(
        "CreativeTag", back_populates="creative", passive_deletes="all"
    )

    def __str__(self):
        return self.name

    @property
    def latest_version(self):
        return self.versions[-1] if self.versions else None


class CreativeVersion(db.Model):
    """25 creative_versions - the draft a reviewer actually sees."""

    __tablename__ = "creative_versions"
    __table_args__ = (db.UniqueConstraint("creative_id", "version_number"),)

    id = db.Column(db.Integer, primary_key=True)
    creative_id = db.Column(
        db.ForeignKey("creatives.id"), nullable=False, index=True
    )
    created_by = db.Column(db.ForeignKey("users.id"), nullable=False, index=True)
    version_number = db.Column(db.Integer, nullable=False)
    notes = db.Column(db.Text)
    created_at = db.Column(db.DateTime, nullable=False, default=utcnow)

    creative = db.relationship("Creative", back_populates="versions")
    author = db.relationship("User")
    files = db.relationship(
        "VersionFile", back_populates="version", passive_deletes="all"
    )
    copy_links = db.relationship(
        "VersionCopyVariant", back_populates="version", passive_deletes="all"
    )
    review_round = db.relationship(
        "ReviewRound",
        back_populates="version",
        uselist=False,
        passive_deletes="all",
    )
    delivery_items = db.relationship(
        "DeliveryItem", back_populates="version", passive_deletes="all"
    )

    def __str__(self):
        return f"Version {self.version_number}"

    @property
    def previews(self):
        return [f for f in self.files if f.kind == "preview"]


class CreativeFormat(db.Model):
    """26 creative_formats - a named pixel size such as Square 1080."""

    __tablename__ = "creative_formats"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)
    width_px = db.Column(db.Integer, nullable=False)
    height_px = db.Column(db.Integer, nullable=False)

    deliverables = db.relationship(
        "BriefDeliverable",
        back_populates="creative_format",
        passive_deletes="all",
    )

    def __str__(self):
        return f"{self.name} ({self.width_px} x {self.height_px})"


class VersionFile(db.Model):
    """27 version_files - an uploaded preview or export image."""

    __tablename__ = "version_files"

    id = db.Column(db.Integer, primary_key=True)
    creative_version_id = db.Column(
        db.ForeignKey("creative_versions.id"), nullable=False, index=True
    )
    kind = db.Column(db.String(16), nullable=False, default="preview")
    display_name = db.Column(db.String(160), nullable=False)
    stored_name = db.Column(db.String(80), nullable=False, unique=True)
    mime_type = db.Column(db.String(64), nullable=False)
    size_bytes = db.Column(db.Integer, nullable=False)

    version = db.relationship("CreativeVersion", back_populates="files")

    def __str__(self):
        return self.display_name


class CopyVariant(db.Model):
    """28 copy_variants - a headline and body text option."""

    __tablename__ = "copy_variants"
    __table_args__ = (db.UniqueConstraint("creative_id", "label"),)

    id = db.Column(db.Integer, primary_key=True)
    creative_id = db.Column(
        db.ForeignKey("creatives.id"), nullable=False, index=True
    )
    label = db.Column(db.String(120), nullable=False)
    headline = db.Column(db.String(200), nullable=False)
    primary_text = db.Column(db.Text, nullable=False)

    creative = db.relationship("Creative", back_populates="copy_variants")
    version_links = db.relationship(
        "VersionCopyVariant", back_populates="copy_variant", passive_deletes="all"
    )

    def __str__(self):
        return self.label


class VersionCopyVariant(db.Model):
    """29 version_copy_variants - bridge: the copy shown in a version."""

    __tablename__ = "version_copy_variants"
    __table_args__ = (
        db.UniqueConstraint("creative_version_id", "copy_variant_id"),
    )

    id = db.Column(db.Integer, primary_key=True)
    creative_version_id = db.Column(
        db.ForeignKey("creative_versions.id"), nullable=False, index=True
    )
    copy_variant_id = db.Column(
        db.ForeignKey("copy_variants.id"), nullable=False, index=True
    )
    placement = db.Column(db.String(80))

    version = db.relationship("CreativeVersion", back_populates="copy_links")
    copy_variant = db.relationship("CopyVariant", back_populates="version_links")


class Tag(db.Model):
    """30 tags - a free label used to group creatives."""

    __tablename__ = "tags"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(60), nullable=False, unique=True)

    creative_tags = db.relationship(
        "CreativeTag", back_populates="tag", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class CreativeTag(db.Model):
    """31 creative_tags - bridge: the tags put on a creative."""

    __tablename__ = "creative_tags"
    __table_args__ = (db.UniqueConstraint("creative_id", "tag_id"),)

    id = db.Column(db.Integer, primary_key=True)
    creative_id = db.Column(
        db.ForeignKey("creatives.id"), nullable=False, index=True
    )
    tag_id = db.Column(db.ForeignKey("tags.id"), nullable=False, index=True)
    note = db.Column(db.String(200))

    creative = db.relationship("Creative", back_populates="creative_tags")
    tag = db.relationship("Tag", back_populates="creative_tags")
