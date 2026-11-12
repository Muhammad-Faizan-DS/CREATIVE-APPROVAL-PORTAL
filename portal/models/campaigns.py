"""Tables 08-15: brands, their guidelines and assets, and campaigns."""

from ..extensions import db


class Brand(db.Model):
    """08 brands - a brand owned by one client."""

    __tablename__ = "brands"
    __table_args__ = (db.UniqueConstraint("client_id", "name"),)

    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(
        db.ForeignKey("clients.id"), nullable=False, index=True
    )
    name = db.Column(db.String(120), nullable=False)

    client = db.relationship("Client", back_populates="brands")
    guidelines = db.relationship(
        "BrandGuideline", back_populates="brand", passive_deletes="all"
    )
    assets = db.relationship(
        "BrandAsset", back_populates="brand", passive_deletes="all"
    )
    audiences = db.relationship(
        "Audience", back_populates="brand", passive_deletes="all"
    )
    campaigns = db.relationship(
        "Campaign", back_populates="brand", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class BrandGuideline(db.Model):
    """09 brand_guidelines - a written rule designers must follow."""

    __tablename__ = "brand_guidelines"
    __table_args__ = (db.UniqueConstraint("brand_id", "title"),)

    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.ForeignKey("brands.id"), nullable=False, index=True)
    title = db.Column(db.String(120), nullable=False)
    rule_text = db.Column(db.Text, nullable=False)

    brand = db.relationship("Brand", back_populates="guidelines")


class BrandAsset(db.Model):
    """10 brand_assets - a logo, font or photo library link."""

    __tablename__ = "brand_assets"

    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.ForeignKey("brands.id"), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    asset_type = db.Column(db.String(32), nullable=False)
    url = db.Column(db.String(500), nullable=False)

    brand = db.relationship("Brand", back_populates="assets")


class Campaign(db.Model):
    """11 campaigns - a run of work for one brand by one team."""

    __tablename__ = "campaigns"
    __table_args__ = (db.UniqueConstraint("brand_id", "name"),)

    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.ForeignKey("brands.id"), nullable=False, index=True)
    team_id = db.Column(db.ForeignKey("teams.id"), nullable=False, index=True)
    name = db.Column(db.String(120), nullable=False)
    starts_on = db.Column(db.Date, nullable=False)
    ends_on = db.Column(db.Date)
    status = db.Column(db.String(16), nullable=False, default="planned")

    brand = db.relationship("Brand", back_populates="campaigns")
    team = db.relationship("Team", back_populates="campaigns")
    campaign_channels = db.relationship(
        "CampaignChannel", back_populates="campaign", passive_deletes="all"
    )
    campaign_audiences = db.relationship(
        "CampaignAudience", back_populates="campaign", passive_deletes="all"
    )
    briefs = db.relationship(
        "Brief", back_populates="campaign", passive_deletes="all"
    )
    delivery_batches = db.relationship(
        "DeliveryBatch", back_populates="campaign", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class Channel(db.Model):
    """12 channels - a placement such as Instagram feed or display."""

    __tablename__ = "channels"

    id = db.Column(db.Integer, primary_key=True)
    name = db.Column(db.String(80), nullable=False, unique=True)

    campaign_channels = db.relationship(
        "CampaignChannel", back_populates="channel", passive_deletes="all"
    )

    def __str__(self):
        return self.name


class CampaignChannel(db.Model):
    """13 campaign_channels - bridge: the channels a campaign runs on."""

    __tablename__ = "campaign_channels"
    __table_args__ = (db.UniqueConstraint("campaign_id", "channel_id"),)

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.ForeignKey("campaigns.id"), nullable=False, index=True
    )
    channel_id = db.Column(
        db.ForeignKey("channels.id"), nullable=False, index=True
    )
    note = db.Column(db.Text)

    campaign = db.relationship("Campaign", back_populates="campaign_channels")
    channel = db.relationship("Channel", back_populates="campaign_channels")
    deliverables = db.relationship(
        "BriefDeliverable",
        back_populates="campaign_channel",
        passive_deletes="all",
    )

    def __str__(self):
        return self.channel.name if self.channel else f"channel {self.id}"


class Audience(db.Model):
    """14 audiences - a target group defined for a brand."""

    __tablename__ = "audiences"
    __table_args__ = (db.UniqueConstraint("brand_id", "label"),)

    id = db.Column(db.Integer, primary_key=True)
    brand_id = db.Column(db.ForeignKey("brands.id"), nullable=False, index=True)
    label = db.Column(db.String(120), nullable=False)
    description = db.Column(db.Text, nullable=False)

    brand = db.relationship("Brand", back_populates="audiences")
    campaign_audiences = db.relationship(
        "CampaignAudience", back_populates="audience", passive_deletes="all"
    )

    def __str__(self):
        return self.label


class CampaignAudience(db.Model):
    """15 campaign_audiences - bridge: audiences a campaign targets."""

    __tablename__ = "campaign_audiences"
    __table_args__ = (db.UniqueConstraint("campaign_id", "audience_id"),)

    id = db.Column(db.Integer, primary_key=True)
    campaign_id = db.Column(
        db.ForeignKey("campaigns.id"), nullable=False, index=True
    )
    audience_id = db.Column(
        db.ForeignKey("audiences.id"), nullable=False, index=True
    )
    priority = db.Column(db.Integer, nullable=False, default=1)

    campaign = db.relationship("Campaign", back_populates="campaign_audiences")
    audience = db.relationship("Audience", back_populates="campaign_audiences")
