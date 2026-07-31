import hmac
import os
from collections.abc import Callable
from dataclasses import dataclass, field
from datetime import UTC, datetime, timedelta
from hashlib import sha256
from uuid import UUID, uuid4


class InvalidCommandEnvelopeError(ValueError):
    """Raised when command envelope integrity, expiry, skew, or signature check fails."""


@dataclass(frozen=True)
class IngestionCommandEnvelope:
    job_id: UUID = field(default_factory=uuid4)
    command_id: UUID = field(default_factory=uuid4)
    command_type: str = "PROCESS_INGESTION_JOB"
    issued_at: datetime = field(default_factory=lambda: datetime.now(UTC))
    expires_at: datetime = field(default_factory=lambda: datetime.now(UTC) + timedelta(minutes=15))
    idempotency_key: str = field(default_factory=lambda: uuid4().hex)
    schema_version: str = "2.0.0"
    key_id: str = "key-v1"
    signature: str = ""

    def get_canonical_payload(self) -> str:
        """Construct deterministic, delimiter-injection-proof length-prefixed canonical payload."""
        issued_iso = self.issued_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        expires_iso = self.expires_at.astimezone(UTC).strftime("%Y-%m-%dT%H:%M:%S.%fZ")
        parts = [
            self.schema_version,
            str(self.command_id),
            str(self.job_id),
            self.command_type,
            issued_iso,
            expires_iso,
            self.idempotency_key,
            self.key_id,
        ]
        return "|".join(f"{len(p)}:{p}" for p in parts)

    def compute_signature(self, secret: str) -> str:
        """Compute HMAC-SHA256 signature over length-prefixed canonical payload."""
        if not secret:
            raise InvalidCommandEnvelopeError("COMMAND_KEY_UNAVAILABLE")
        canonical_str = self.get_canonical_payload()
        return hmac.new(secret.encode("utf-8"), canonical_str.encode("utf-8"), sha256).hexdigest()

    def with_signature(self, secret: str) -> "IngestionCommandEnvelope":
        """Return new envelope instance with computed HMAC signature."""
        sig = self.compute_signature(secret)
        return IngestionCommandEnvelope(
            job_id=self.job_id,
            command_id=self.command_id,
            command_type=self.command_type,
            issued_at=self.issued_at,
            expires_at=self.expires_at,
            idempotency_key=self.idempotency_key,
            schema_version=self.schema_version,
            key_id=self.key_id,
            signature=sig,
        )

    def is_expired(self, now: datetime | None = None) -> bool:
        current = now or datetime.now(UTC)
        return current > self.expires_at

    def validate_envelope(
        self,
        secret_resolver: Callable[[str], str] | None = None,
        now: datetime | None = None,
        max_skew_seconds: int = 300,
    ) -> None:
        """Strict fail-closed validation with safe allowlist error codes and zero log interpolation."""
        current = now or datetime.now(UTC)

        # 1. Schema Version Check
        if self.schema_version != "2.0.0":
            raise InvalidCommandEnvelopeError("COMMAND_SCHEMA_REJECTED")

        # 2. Command Type Check
        if self.command_type != "PROCESS_INGESTION_JOB":
            raise InvalidCommandEnvelopeError("COMMAND_TYPE_INVALID")

        # 3. Expiry Check
        if self.is_expired(current):
            raise InvalidCommandEnvelopeError("COMMAND_EXPIRED")

        # 4. Future / Clock Skew Check
        skew = (current - self.issued_at).total_seconds()
        if abs(skew) > max_skew_seconds:
            raise InvalidCommandEnvelopeError("COMMAND_CLOCK_SKEW")

        # 5. Key ID & HMAC Signature Verification
        resolver = secret_resolver or default_secret_resolver
        secret = resolver(self.key_id)
        if not secret:
            raise InvalidCommandEnvelopeError("COMMAND_KEY_UNAVAILABLE")

        expected_sig = self.compute_signature(secret)
        if not hmac.compare_digest(self.signature, expected_sig):
            raise InvalidCommandEnvelopeError("COMMAND_SIGNATURE_INVALID")


def default_secret_resolver(key_id: str) -> str:
    """Resolve secret from environment without hardcoding secrets in repo or fallback values."""
    env_var_name = f"INGESTION_HMAC_SECRET_{key_id.upper().replace('-', '_')}"
    return os.environ.get(env_var_name) or os.environ.get("INGESTION_HMAC_SECRET", "")
