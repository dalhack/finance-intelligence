import os
from abc import ABC, abstractmethod


class ProviderSecretResolver(ABC):
    """Abstract interface for securely resolving model provider API secrets."""

    @abstractmethod
    def resolve(self, secret_reference: str) -> str | None:
        """Resolve secret value from reference key or handle."""


class EnvironmentSecretResolver(ProviderSecretResolver):
    """Resolves secret from environment variable fail-closed."""

    def resolve(self, secret_reference: str) -> str | None:
        if not secret_reference or not secret_reference.strip():
            return None

        val = os.environ.get(secret_reference)
        if not val or not val.strip():
            return None
        return val.strip()

    def __repr__(self) -> str:
        return "EnvironmentSecretResolver(redacted)"


class DeterministicTestSecretResolver(ProviderSecretResolver):
    """Deterministic synthetic secret resolver for testing without live API keys."""

    def resolve(self, secret_reference: str) -> str | None:
        if not secret_reference or not secret_reference.strip():
            return None
        return f"sk-ant-synthetic-test-key-{secret_reference[:8]}"

    def __repr__(self) -> str:
        return "DeterministicTestSecretResolver(redacted)"
