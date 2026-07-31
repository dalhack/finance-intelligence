import pytest

from services.api.app.orchestration.circuit_breaker import (
    CircuitState,
    ModelProviderUnavailableException,
    ProviderCircuitBreaker,
)


def test_circuit_breaker_transitions():
    cb = ProviderCircuitBreaker(provider_alias="anthropic", failure_threshold=3, cooldown_seconds=10.0)

    # Initial state: CLOSED
    assert cb.state == CircuitState.CLOSED
    cb.check_allow_execution()

    # Record 2 transient failures -> still CLOSED
    cb.record_failure(is_transient=True)
    cb.record_failure(is_transient=True)
    assert cb.state == CircuitState.CLOSED

    # Record 3rd failure -> trips to OPEN
    cb.record_failure(is_transient=True)
    assert cb.state == CircuitState.OPEN

    # Executing while OPEN throws fail-fast exception
    with pytest.raises(ModelProviderUnavailableException):
        cb.check_allow_execution()

    # Non-transient failure does not increase consecutive failures
    cb_closed = ProviderCircuitBreaker(failure_threshold=3)
    cb_closed.record_failure(is_transient=False)
    assert cb_closed.consecutive_failures == 0
