"""A provider saying "not now" must not read as "your analysis failed"."""

import asyncio

import pytest
from app.orchestration.transient_retry import (
    backoff_delay,
    call_with_transient_retry,
    is_transient,
    status_code_of,
)


class ApiError(Exception):
    def __init__(self, message, status_code=None):
        super().__init__(message)
        self.status_code = status_code


@pytest.mark.parametrize("status", [408, 429, 500, 502, 503, 504, 529])
def test_statuses_that_pass_on_their_own_are_transient(status):
    assert is_transient(ApiError("upstream", status_code=status))


@pytest.mark.parametrize("status", [400, 401, 403, 404, 422])
def test_a_request_the_provider_refuses_is_not_retried(status):
    assert not is_transient(ApiError("bad request", status_code=status))


def test_the_status_is_read_out_of_the_message_when_not_exposed():
    """The overload that failed two analyses arrived only as text."""
    error = Exception("Error code: 529 - {'type': 'error', 'error': {'type': 'overloaded_error'}}")
    assert status_code_of(error) == 529
    assert is_transient(error)


def test_wording_alone_is_enough_when_there_is_no_status():
    assert is_transient(Exception("Overloaded"))
    assert is_transient(asyncio.TimeoutError())
    assert not is_transient(Exception("invalid tool schema"))


def test_delays_grow_then_flatten():
    assert backoff_delay(1) == 2.0
    assert backoff_delay(2) == 4.0
    assert backoff_delay(3) == 8.0
    assert backoff_delay(9) == 30.0
    assert backoff_delay(5) == 30.0


@pytest.mark.asyncio
async def test_a_transient_failure_is_retried_until_it_succeeds():
    slept: list[float] = []
    attempts = {"n": 0}

    async def operation():
        attempts["n"] += 1
        if attempts["n"] < 3:
            raise ApiError("Overloaded", status_code=529)
        return "table"

    result = await call_with_transient_retry(
        operation, sleep=lambda d: _record(slept, d)
    )

    assert result == "table"
    assert attempts["n"] == 3
    assert slept == [2.0, 4.0]


@pytest.mark.asyncio
async def test_a_permanent_failure_is_raised_at_once():
    attempts = {"n": 0}

    async def operation():
        attempts["n"] += 1
        raise ApiError("bad request", status_code=400)

    with pytest.raises(ApiError):
        await call_with_transient_retry(operation, sleep=lambda d: _record([], d))

    assert attempts["n"] == 1


@pytest.mark.asyncio
async def test_a_provider_that_stays_down_still_fails():
    attempts = {"n": 0}

    async def operation():
        attempts["n"] += 1
        raise ApiError("Overloaded", status_code=529)

    with pytest.raises(ApiError):
        await call_with_transient_retry(
            operation, max_attempts=3, sleep=lambda d: _record([], d)
        )

    assert attempts["n"] == 3


async def _record(sink: list[float], delay: float) -> None:
    sink.append(delay)
