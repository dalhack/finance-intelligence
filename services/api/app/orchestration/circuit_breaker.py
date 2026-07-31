import time
from enum import Enum


class CircuitState(str, Enum):
    CLOSED = "CLOSED"
    OPEN = "OPEN"
    HALF_OPEN = "HALF_OPEN"


class ModelProviderUnavailableException(Exception):
    """Fail-fast exception when circuit breaker is OPEN."""


class ProviderCircuitBreaker:
    def __init__(
        self,
        provider_alias: str = "anthropic",
        failure_threshold: int = 5,
        cooldown_seconds: float = 60.0,
        half_open_max_probes: int = 2,
    ):
        self.provider_alias = provider_alias
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self.half_open_max_probes = half_open_max_probes

        self.state: CircuitState = CircuitState.CLOSED
        self.consecutive_failures: int = 0
        self.last_failure_time: float = 0.0
        self.half_open_probes: int = 0

    def check_allow_execution(self) -> None:
        now = time.time()
        if self.state == CircuitState.OPEN:
            if now - self.last_failure_time >= self.cooldown_seconds:
                self.state = CircuitState.HALF_OPEN
                self.half_open_probes = 0
            else:
                raise ModelProviderUnavailableException(
                    f"Provider {self.provider_alias} circuit breaker is OPEN. Cooldown active."
                )

        if self.state == CircuitState.HALF_OPEN:
            if self.half_open_probes >= self.half_open_max_probes:
                raise ModelProviderUnavailableException(
                    f"Provider {self.provider_alias} circuit breaker is HALF_OPEN probe limit reached."
                )
            self.half_open_probes += 1

    def record_success(self) -> None:
        self.consecutive_failures = 0
        self.half_open_probes = 0
        self.state = CircuitState.CLOSED

    def record_failure(self, is_transient: bool = True) -> None:
        if not is_transient:
            return  # Non-transient errors (auth, schema, policy) don't trip circuit breaker

        self.consecutive_failures += 1
        self.last_failure_time = time.time()

        if self.state == CircuitState.HALF_OPEN or self.consecutive_failures >= self.failure_threshold:
            self.state = CircuitState.OPEN


class DistributedCircuitBreaker:
    """PostgreSQL-backed distributed provider circuit breaker with fencing token probes."""

    def __init__(
        self,
        provider_key: str = "anthropic",
        model_alias: str = "finance_analysis_balanced",
        failure_threshold: int = 5,
        cooldown_seconds: int = 60,
    ):
        self.provider_key = provider_key
        self.model_alias = model_alias
        self.failure_threshold = failure_threshold
        self.cooldown_seconds = cooldown_seconds
        self._local_fallback = ProviderCircuitBreaker(
            provider_alias=provider_key,
            failure_threshold=failure_threshold,
            cooldown_seconds=float(cooldown_seconds),
        )

    async def record_failure_async(self, session, is_transient: bool = True) -> str:
        """Record provider failure in PostgreSQL using SECURITY DEFINER function."""
        if not is_transient:
            return "CLOSED"

        from sqlalchemy import text

        stmt = text("SELECT record_provider_failure(:pkey, :alias, :thresh, :dur);")
        res = await session.execute(
            stmt,
            {
                "pkey": self.provider_key,
                "alias": self.model_alias,
                "thresh": self.failure_threshold,
                "dur": self.cooldown_seconds,
            },
        )
        row = res.fetchone()
        state = row[0] if row else "CLOSED"
        self._local_fallback.record_failure(is_transient=is_transient)
        return state

    async def record_success_async(self, session) -> str:
        """Record provider success in PostgreSQL using SECURITY DEFINER function."""
        from sqlalchemy import text

        stmt = text("SELECT record_provider_success(:pkey, :alias);")
        res = await session.execute(stmt, {"pkey": self.provider_key, "alias": self.model_alias})
        row = res.fetchone()
        state = row[0] if row else "CLOSED"
        self._local_fallback.record_success()
        return state
