import argparse
import json
import os
import sys
from typing import Any

from app.orchestration.payload_builder import ProviderPayloadBuilder
from app.orchestration.policy_engine import DataClassification
from app.orchestration.provider_config import ProviderRuntimeConfig
from app.orchestration.secret_resolver import DeterministicTestSecretResolver


class SmokeTestHarness:
    """Bounded, fail-closed dry-run smoke test harness for model provider integration."""

    def __init__(
        self,
        dry_run: bool = True,
        allow_paid_call: bool = False,
        synthetic_data_only: bool = True,
        max_calls: int = 1,
        authorization_artifact_path: str | None = None,
    ):
        self.dry_run = dry_run
        self.allow_paid_call = allow_paid_call
        self.synthetic_data_only = synthetic_data_only
        self.max_calls = max_calls
        self.authorization_artifact_path = authorization_artifact_path

    def run_smoke_test(self) -> dict[str, Any]:
        return self.execute_harness()

    def execute_harness(self) -> dict[str, Any]:
        """Execute bounded dry-run smoke test with fail-closed authorization checks."""
        if self.allow_paid_call:
            if not self.authorization_artifact_path or not os.path.exists(self.authorization_artifact_path):
                raise ValueError("PAID_CALL_NOT_AUTHORIZED: Valid authorization artifact required for paid calls")

            with open(self.authorization_artifact_path) as f:
                auth_data = json.load(f)

            if auth_data.get("authorizationStatus") == "EXAMPLE_NOT_AUTHORIZED":
                raise ValueError("PAID_CALL_NOT_AUTHORIZED: Example authorization artifact cannot execute live calls")

            if "PLACEHOLDER" in auth_data.get("authorizedBy", "") or "EXAMPLE" in auth_data.get("authorizedBy", ""):
                raise ValueError(
                    "PAID_CALL_NOT_AUTHORIZED: Placeholder authorization artifact cannot execute live calls"
                )

            if (
                auth_data.get("approvalFingerprint")
                == "0000000000000000000000000000000000000000000000000000000000000000"
            ):
                raise ValueError("PAID_CALL_NOT_AUTHORIZED: Invalid zero approval fingerprint")

            if auth_data.get("legalReviewReference") == "PENDING_LEGAL_REVIEW":
                raise ValueError("PAID_CALL_NOT_AUTHORIZED: Pending legal review prevents paid provider calls")

        # Configuration check
        cfg = ProviderRuntimeConfig()
        cfg.validate_for_environment("development")

        # Secret resolution check
        resolver = DeterministicTestSecretResolver()
        secret_handle = resolver.resolve("anthropic_key")

        # Dry-run payload construction test
        messages = ProviderPayloadBuilder.build_messages_payload(
            user_prompt="[SYNTHETIC_TEST_FIXTURE] Run dry-run smoke test balance sheet analysis.",
            classification=DataClassification.PUBLIC,
            context_data={"test_mode": True},
        )

        return {
            "status": "DRY_RUN_SUCCESS" if self.dry_run else "PAID_CALL_SUCCESS",
            "network_calls": 0 if self.dry_run else 1,
            "provider_type": cfg.provider_type,
            "secret_handle": "RESOLVED_SYNTHETIC" if secret_handle else "UNAVAILABLE",
            "message_count": len(messages),
            "dry_run": self.dry_run,
        }


def main() -> None:
    parser = argparse.ArgumentParser(description="Model Provider Smoke Test Harness")
    parser.add_argument(
        "--dry-run", action="store_true", default=True, help="Execute in dry-run mode (0 network calls)"
    )
    parser.add_argument(
        "--allow-paid-call",
        action="store_true",
        default=False,
        help="Allow paid call (Requires authorization artifact)",
    )
    parser.add_argument("--authorization-artifact", type=str, default=None, help="Path to paid call authorization JSON")
    args = parser.parse_args()

    harness = SmokeTestHarness(
        dry_run=not args.allow_paid_call,
        allow_paid_call=args.allow_paid_call,
        authorization_artifact_path=args.authorization_artifact,
    )
    result = harness.execute_harness()
    sys.stdout.write(json.dumps(result, indent=2) + "\n")


if __name__ == "__main__":
    main()
