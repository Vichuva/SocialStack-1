from tenacity import (
    retry,
    retry_if_exception_type,
    stop_after_attempt,
    wait_exponential,
    wait_fixed,
)

from socialstack.utils.errors import AIError, RateLimitError


ai_retry = retry(
    retry=retry_if_exception_type(AIError),
    stop=stop_after_attempt(3),
    wait=wait_fixed(2),
    reraise=True,
)

http_429_retry = retry(
    retry=retry_if_exception_type(RateLimitError),
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=2, min=30, max=300),
    reraise=True,
)

http_5xx_retry = retry(
    stop=stop_after_attempt(3),
    wait=wait_exponential(multiplier=1, min=2, max=30),
    reraise=True,
)
