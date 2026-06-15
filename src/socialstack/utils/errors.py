class SocialStackError(Exception):
    """Base exception for all SocialStack errors."""
    def __init__(self, message: str, code: str = "internal_error"):
        self.message = message
        self.code = code
        super().__init__(message)


class NotFoundError(SocialStackError):
    def __init__(self, resource: str, resource_id: str):
        super().__init__(f"{resource} '{resource_id}' not found", "not_found")
        self.resource = resource
        self.resource_id = resource_id


class ValidationError(SocialStackError):
    def __init__(self, message: str):
        super().__init__(message, "validation_error")


class AIError(SocialStackError):
    def __init__(self, message: str, provider: str = "unknown"):
        super().__init__(message, "ai_error")
        self.provider = provider


class AIParseError(AIError):
    """AI returned output that couldn't be parsed as expected JSON."""
    def __init__(self, raw: str, provider: str = "unknown"):
        super().__init__(f"Failed to parse AI response: {raw[:200]}", provider)
        self.raw = raw


class TwitterCharLimitError(SocialStackError):
    def __init__(self, char_count: int):
        super().__init__(
            f"Twitter/X caption exceeds 280 chars ({char_count} chars). Shorten required.",
            "twitter_char_limit",
        )
        self.char_count = char_count


class PublishValidationError(SocialStackError):
    def __init__(self, message: str, platform: str):
        super().__init__(message, "publish_validation_error")
        self.platform = platform


class PublishError(SocialStackError):
    def __init__(self, message: str, platform: str, status_code: int | None = None):
        super().__init__(message, "publish_error")
        self.platform = platform
        self.status_code = status_code


class RateLimitError(SocialStackError):
    def __init__(self, service: str, retry_after_seconds: int = 60):
        super().__init__(f"Rate limited by {service}. Retry after {retry_after_seconds}s.", "rate_limit")
        self.service = service
        self.retry_after_seconds = retry_after_seconds


class StorageError(SocialStackError):
    def __init__(self, message: str):
        super().__init__(message, "storage_error")


class EncryptionError(SocialStackError):
    def __init__(self, message: str):
        super().__init__(message, "encryption_error")


class IdempotencyConflictError(SocialStackError):
    """Returned when an idempotency key matches an in-progress or completed run."""
    def __init__(self, run_id: str, status: str):
        super().__init__(f"Duplicate request. Existing run_id={run_id} status={status}", "idempotency_conflict")
        self.run_id = run_id
        self.status = status
