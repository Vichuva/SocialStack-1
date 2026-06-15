from enum import StrEnum


class Platform(StrEnum):
    INSTAGRAM = "instagram"
    FACEBOOK = "facebook"
    LINKEDIN = "linkedin"
    TWITTER = "twitter"


class SlotStatus(StrEnum):
    DRAFT = "draft"
    PENDING_BRIEF = "pending_brief"
    PENDING_CAPTION = "pending_caption"
    PENDING_REVIEW = "pending_review"
    APPROVED = "approved"
    PUBLISHED = "published"
    FAILED = "failed"


class ObjectiveType(StrEnum):
    AWARENESS = "awareness"
    EDUCATION = "education"
    PROMOTION = "promotion"
    TRUST = "trust"
    ENGAGEMENT = "engagement"


class RunStatus(StrEnum):
    QUEUED = "queued"
    RUNNING = "running"
    SUCCEEDED = "succeeded"
    FAILED = "failed"


class NotificationType(StrEnum):
    APPROVAL_REQUIRED = "approval_required"
    CONTENT_READY = "content_ready"
    PUBLISH_SUCCESS = "publish_success"
    PUBLISH_FAILURE = "publish_failure"
    TOKEN_EXPIRATION = "token_expiration"
    WORKFLOW_FAILURE = "workflow_failure"


PLATFORM_IMAGE_SIZES: dict[Platform, str] = {
    Platform.INSTAGRAM: "1024x1024",
    Platform.FACEBOOK: "1024x1024",
    Platform.LINKEDIN: "1024x1024",
    Platform.TWITTER: "1536x1024",
}
