from enum import Enum

from app.orchestration.exceptions import PolicyDeniedException


class DataClassification(str, Enum):
    PUBLIC = "PUBLIC"
    INTERNAL = "INTERNAL"
    CONFIDENTIAL = "CONFIDENTIAL"
    STRICTLY_CONFIDENTIAL = "STRICTLY_CONFIDENTIAL"
    PERSONAL_DATA = "PERSONAL_DATA"


class PolicyDecision(str, Enum):
    ALLOW = "ALLOW"
    DENY = "DENY"
    REQUIRE_MASKING = "REQUIRE_MASKING"
    REQUIRE_HUMAN_APPROVAL = "REQUIRE_HUMAN_APPROVAL"
    INTERNAL_ONLY = "INTERNAL_ONLY"


class PolicyEngine:
    """Central Policy Engine evaluating data classification and external model transmission rules."""

    POLICY_VERSION = "1.0.0"

    @classmethod
    def evaluate_model_transmission(
        cls,
        classification: DataClassification,
        provider_alias: str,
        is_external_provider: bool = True,
    ) -> PolicyDecision:
        try:
            if classification == DataClassification.STRICTLY_CONFIDENTIAL:
                # Strictly confidential data must NEVER leave tenant boundary
                return PolicyDecision.DENY

            if classification == DataClassification.PERSONAL_DATA:
                # Personal data requires masking and explicit tenant policy override
                return PolicyDecision.REQUIRE_MASKING

            if classification == DataClassification.CONFIDENTIAL:
                # Confidential data defaults to DENY for external providers unless internal
                if is_external_provider:
                    return PolicyDecision.DENY
                return PolicyDecision.ALLOW

            if classification in (DataClassification.INTERNAL, DataClassification.PUBLIC):
                return PolicyDecision.ALLOW

            return PolicyDecision.DENY
        except Exception:  # noqa: BLE001
            # Fail closed on any evaluation exception
            return PolicyDecision.DENY

    @classmethod
    def enforce_transmission_policy(
        cls,
        classification: DataClassification,
        provider_alias: str,
        is_external_provider: bool = True,
    ) -> None:
        decision = cls.evaluate_model_transmission(
            classification=classification,
            provider_alias=provider_alias,
            is_external_provider=is_external_provider,
        )
        if decision not in (PolicyDecision.ALLOW, PolicyDecision.REQUIRE_MASKING):
            raise PolicyDeniedException(
                f"Policy Engine denied transmission of classification '{classification.value}' to model '{provider_alias}'. Decision: '{decision.value}'"
            )
