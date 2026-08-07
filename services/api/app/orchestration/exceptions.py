class OrchestrationException(Exception):
    """Base exception for all AI Orchestration errors."""

    def __init__(self, code: str, message: str):
        self.code = code
        self.message = message
        super().__init__(f"{code}: {message}")


class ModelProviderNotConfiguredException(OrchestrationException):
    def __init__(self, message: str = "Model provider credential is missing or not configured."):
        super().__init__("MODEL_PROVIDER_NOT_CONFIGURED", message)


class ModelCapabilityUnavailableException(OrchestrationException):
    def __init__(self, message: str = "Requested model capability is unavailable."):
        super().__init__("MODEL_CAPABILITY_UNAVAILABLE", message)


class ModelFailoverProhibitedException(OrchestrationException):
    def __init__(self, message: str = "Model failover is prohibited by policy or classification mismatch."):
        super().__init__("MODEL_FAILOVER_PROHIBITED", message)


class PromptTemplateIntegrityFailedException(OrchestrationException):
    def __init__(self, message: str = "Prompt template SHA-256 checksum verification failed."):
        super().__init__("PROMPT_TEMPLATE_INTEGRITY_FAILED", message)


class PolicyDeniedException(OrchestrationException):
    def __init__(self, message: str = "Policy engine denied model invocation or data transmission."):
        super().__init__("POLICY_DENIED", message)


class AnalysisPlanInvalidException(OrchestrationException):
    def __init__(self, message: str = "Analysis plan validation failed."):
        super().__init__("ANALYSIS_PLAN_INVALID", message)


class ToolNotAllowedException(OrchestrationException):
    def __init__(self, message: str = "Requested tool is forbidden or not in allowlist."):
        super().__init__("TOOL_NOT_ALLOWED", message)


class ToolInputInvalidException(OrchestrationException):
    def __init__(self, message: str = "Tool argument validation failed."):
        super().__init__("TOOL_INPUT_INVALID", message)


class AnalysisBudgetExceededException(OrchestrationException):
    def __init__(self, message: str = "Analysis job budget exceeded maximum limits."):
        super().__init__("ANALYSIS_BUDGET_EXCEEDED", message)


class UnsupportedNumericClaimException(OrchestrationException):
    def __init__(
        self, message: str = "Narrative text contains unverified numeric claim not found in authoritative dataset."
    ):
        super().__init__("UNSUPPORTED_NUMERIC_CLAIM", message)


class QualityGateFailedException(OrchestrationException):
    def __init__(self, message: str = "Analysis job failed quality gate verification."):
        super().__init__("QUALITY_GATE_FAILED", message)


class ClaimOwnershipLostException(OrchestrationException):
    def __init__(self, message: str = "Worker lost claim ownership token or lease expired."):
        super().__init__("CLAIM_OWNERSHIP_LOST", message)
