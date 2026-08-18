"""Retries a model call that failed for a reason that will pass on its own.

A provider answering 529 Overloaded is saying "not now", not "never". Treating
that the same as a real error failed whole analyses: the request was sound, the
data was there, and the user was told the analysis failed. Two runs of the same
question failed this way within three minutes.

Only errors that are transient by definition are retried — overload, rate
limiting, gateway failures and timeouts. A refusal, a bad request or an
authentication failure is returned immediately, because repeating it would only
waste the user's time and the provider's quota.
"""

import asyncio
import logging
import re
from collections.abc import Awaitable, Callable

logger = logging.getLogger(__name__)

# Status codes the provider uses to say the request could succeed later.
TRANSIENT_STATUS_CODES = frozenset({408, 409, 425, 429, 500, 502, 503, 504, 529})

_TRANSIENT_PHRASES = (
    "overloaded",
    "rate limit",
    "rate_limit",
    "timeout",
    "timed out",
    "temporarily unavailable",
    "service unavailable",
    "connection reset",
    "connection error",
    "bad gateway",
)

_STATUS_IN_TEXT = re.compile(r"\berror code:\s*(\d{3})\b", re.IGNORECASE)

# An analysis job holds a fifteen-minute lease, so it can afford to wait out a
# provider overload that lasts a minute. Six attempts spend about sixty seconds
# sleeping in total, which is well inside the lease and far cheaper than
# telling the user their sound question failed.
DEFAULT_MAX_ATTEMPTS = 6
DEFAULT_BASE_DELAY_SECONDS = 2.0
DEFAULT_MAX_DELAY_SECONDS = 30.0


def status_code_of(error: BaseException) -> int | None:
    """The HTTP status an exception carries, however the client exposes it."""
    for attribute in ("status_code", "http_status", "code"):
        value = getattr(error, attribute, None)
        if isinstance(value, int):
            return value

    response = getattr(error, "response", None)
    status = getattr(response, "status_code", None)
    if isinstance(status, int):
        return status

    match = _STATUS_IN_TEXT.search(str(error))
    return int(match.group(1)) if match else None


def is_transient(error: BaseException) -> bool:
    """True when repeating the identical call could plausibly succeed."""
    if isinstance(error, (asyncio.TimeoutError, ConnectionError)):
        return True

    status = status_code_of(error)
    if status is not None:
        return status in TRANSIENT_STATUS_CODES

    text = str(error).casefold()
    return any(phrase in text for phrase in _TRANSIENT_PHRASES)


def backoff_delay(
    attempt: int,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
) -> float:
    """Seconds to wait before `attempt` (1-based), doubling and then flattening.

    No jitter: this worker processes one analysis at a time, so there is no
    thundering herd to spread out, and a predictable delay is easier to reason
    about when reading a log.
    """
    return min(base_delay * (2 ** max(0, attempt - 1)), max_delay)


async def call_with_transient_retry[T](
    operation: Callable[[], Awaitable[T]],
    *,
    description: str = "model call",
    max_attempts: int = DEFAULT_MAX_ATTEMPTS,
    base_delay: float = DEFAULT_BASE_DELAY_SECONDS,
    max_delay: float = DEFAULT_MAX_DELAY_SECONDS,
    sleep: Callable[[float], Awaitable[None]] = asyncio.sleep,
) -> T:
    """Run `operation`, retrying only while it fails for a transient reason.

    The last error is raised once the attempts are used up, so a provider that
    stays down still surfaces as a failure rather than hanging.
    """
    last_error: BaseException | None = None

    for attempt in range(1, max_attempts + 1):
        try:
            return await operation()
        except Exception as error:
            last_error = error
            if not is_transient(error) or attempt == max_attempts:
                raise
            delay = backoff_delay(attempt, base_delay, max_delay)
            logger.warning(
                "TRANSIENT_PROVIDER_ERROR_RETRYING: %s attempt=%d/%d delay=%.1fs status=%s",
                description,
                attempt,
                max_attempts,
                delay,
                status_code_of(error),
            )
            await sleep(delay)

    raise last_error  # pragma: no cover - loop either returns or raises
