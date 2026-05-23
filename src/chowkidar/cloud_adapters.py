"""Cloud environment adapter contracts.

Adapters are intentionally explicit: local deployment signals never grant
permission to mutate remote environments or secret stores.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from typing import Protocol

from .config import Config


@dataclass
class CloudTarget:
    adapter: str
    name: str
    metadata: dict = field(default_factory=dict)


@dataclass
class CloudOperationResult:
    status: str
    adapter: str
    target: str
    message: str
    metadata: dict = field(default_factory=dict)

    def to_dict(self) -> dict:
        return asdict(self)


class CloudEnvAdapter(Protocol):
    name: str

    def discover(self) -> list[CloudTarget]:
        ...

    def dry_run(self, target: CloudTarget, variable_name: str, new_value: str) -> CloudOperationResult:
        ...

    def write(self, target: CloudTarget, variable_name: str, new_value: str) -> CloudOperationResult:
        ...

    def verify(self, target: CloudTarget, variable_name: str, expected_value: str) -> CloudOperationResult:
        ...


class DisabledCloudAdapter:
    """Base adapter that documents unsupported writes until credentials are configured."""

    def __init__(self, name: str, config: Config | None = None) -> None:
        self.name = name
        self.config = config or Config()

    @property
    def enabled(self) -> bool:
        return bool(self.config.get(f"cloud_{self.name}_enabled", False))

    def discover(self) -> list[CloudTarget]:
        if not self.enabled:
            return []
        return [CloudTarget(self.name, "configured-target", {"confirmed": False})]

    def dry_run(self, target: CloudTarget, variable_name: str, new_value: str) -> CloudOperationResult:
        return self._blocked(target, "dry_run")

    def write(self, target: CloudTarget, variable_name: str, new_value: str) -> CloudOperationResult:
        return self._blocked(target, "write")

    def verify(self, target: CloudTarget, variable_name: str, expected_value: str) -> CloudOperationResult:
        return self._blocked(target, "verify")

    def _blocked(self, target: CloudTarget, operation: str) -> CloudOperationResult:
        return CloudOperationResult(
            status="blocked",
            adapter=self.name,
            target=target.name,
            message=(
                f"{self.name} {operation} requires a concrete provider client, "
                "explicit credentials, dry-run mapping, and verification support."
            ),
            metadata={"operation": operation},
        )


class VercelAdapter(DisabledCloudAdapter):
    def __init__(self, config: Config | None = None) -> None:
        super().__init__("vercel", config)


class KubernetesAdapter(DisabledCloudAdapter):
    def __init__(self, config: Config | None = None) -> None:
        super().__init__("kubernetes", config)


class AWSSecretsAdapter(DisabledCloudAdapter):
    def __init__(self, config: Config | None = None) -> None:
        super().__init__("aws", config)


class GCPSecretManagerAdapter(DisabledCloudAdapter):
    def __init__(self, config: Config | None = None) -> None:
        super().__init__("gcp", config)


class AzureKeyVaultAdapter(DisabledCloudAdapter):
    def __init__(self, config: Config | None = None) -> None:
        super().__init__("azure", config)


def get_cloud_adapters(config: Config | None = None) -> list[CloudEnvAdapter]:
    cfg = config or Config()
    return [
        VercelAdapter(cfg),
        KubernetesAdapter(cfg),
        AWSSecretsAdapter(cfg),
        GCPSecretManagerAdapter(cfg),
        AzureKeyVaultAdapter(cfg),
    ]
