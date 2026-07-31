import json
from typing import Any, ClassVar

from services.api.app.orchestration.policy_engine import DataClassification


class ProviderPayloadBuilder:
    """Constructs sanitized, classification-enforced model payloads with zero parameter leakage."""

    FORBIDDEN_KEYS: ClassVar[set[str]] = {
        "organization_id",
        "tenant_id",
        "user_id",
        "role",
        "permission",
        "api_key",
        "auth_token",
        "app_check_token",
        "object_key",
        "file_path",
        "raw_sql",
    }

    @classmethod
    def sanitize_dict(cls, data: dict[str, Any]) -> dict[str, Any]:
        """Recursively strip forbidden parameters from payload dictionary."""
        sanitized: dict[str, Any] = {}
        for k, v in data.items():
            if k in cls.FORBIDDEN_KEYS:
                continue
            if isinstance(v, dict):
                sanitized[k] = cls.sanitize_dict(v)
            elif isinstance(v, list):
                sanitized[k] = [cls.sanitize_dict(item) if isinstance(item, dict) else item for item in v]
            else:
                sanitized[k] = v
        return sanitized

    @classmethod
    def build_messages_payload(
        cls,
        user_prompt: str,
        classification: DataClassification,
        source_excerpts: list[str] | None = None,
        context_data: dict[str, Any] | None = None,
    ) -> list[dict[str, Any]]:
        """Construct Anthropic messages array enforcing data classification limits."""
        if classification == DataClassification.STRICTLY_CONFIDENTIAL:
            raise ValueError(
                "STRICTLY_CONFIDENTIAL_NETWORK_DENY: Payload construction forbidden for strictly confidential data"
            )

        messages = []

        # Sanitize context data
        clean_context = cls.sanitize_dict(context_data or {})

        content_blocks = [user_prompt]

        if source_excerpts:
            excerpts_text = "\n---\n".join(source_excerpts[:5])  # Max 5 excerpts
            content_blocks.append(f"\n[Source Excerpts]\n{excerpts_text}")

        if clean_context:
            content_blocks.append(f"\n[Context Data]\n{json.dumps(clean_context)}")

        messages.append(
            {
                "role": "user",
                "content": "\n".join(content_blocks),
            }
        )

        return messages
