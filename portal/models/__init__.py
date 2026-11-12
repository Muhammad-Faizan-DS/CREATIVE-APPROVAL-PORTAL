"""Every model module is imported here so init-db registers all 40 tables."""

from .accounts import (
    Client,
    ClientContact,
    ClientMembership,
    Role,
    Team,
    TeamMembership,
    User,
)
from .campaigns import (
    Audience,
    Brand,
    BrandAsset,
    BrandGuideline,
    Campaign,
    CampaignAudience,
    CampaignChannel,
    Channel,
)
from .briefs import (
    Brief,
    BriefDeliverable,
    BriefReference,
    BriefRequirement,
    Task,
    TaskAssignee,
    TaskChecklistItem,
    TaskComment,
    utcnow,
)
from .production import (
    CopyVariant,
    Creative,
    CreativeFormat,
    CreativeTag,
    CreativeVersion,
    Tag,
    VersionCopyVariant,
    VersionFile,
)
from .reviews import (
    ChangeRequest,
    DeliveryBatch,
    DeliveryItem,
    DeliveryReceipt,
    ReviewAssignment,
    ReviewAttachment,
    ReviewComment,
    ReviewDecision,
    ReviewRound,
)

__all__ = [
    "Audience", "Brand", "BrandAsset", "BrandGuideline", "Brief",
    "BriefDeliverable", "BriefReference", "BriefRequirement", "Campaign",
    "CampaignAudience", "CampaignChannel", "ChangeRequest", "Channel",
    "Client", "ClientContact", "ClientMembership", "CopyVariant", "Creative",
    "CreativeFormat", "CreativeTag", "CreativeVersion", "DeliveryBatch",
    "DeliveryItem", "DeliveryReceipt", "ReviewAssignment", "ReviewAttachment",
    "ReviewComment", "ReviewDecision", "ReviewRound", "Role", "Tag", "Task",
    "TaskAssignee", "TaskChecklistItem", "TaskComment", "Team",
    "TeamMembership", "User", "VersionCopyVariant", "VersionFile", "utcnow",
]
