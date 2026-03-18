"""Base protocol and data types for provider adapters."""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Protocol, runtime_checkable


@dataclass
class ModelInfo:
    """Metadata about a model from a provider."""

    id: str
    provider: str
    aliases: list[str] = field(default_factory=list)
    is_active: bool = True
    created_date: str | None = None


@dataclass
class DeprecationNotice:
    """Structured deprecation information for a model."""

    model_id: str
    provider: str
    sunset_date: str | None = None
    replacement: str | None = None
    replacement_confidence: str = "medium"
    breaking_changes: bool = False
    source_url: str | None = None
    raw_text: str | None = None


@runtime_checkable
class ProviderAdapter(Protocol):
    """Protocol that all provider scrapers must implement."""

    name: str

    async def fetch_models(self) -> list[ModelInfo]:
        """Fetch the list of known models from this provider."""
        ...

    async def fetch_deprecations(self) -> list[DeprecationNotice]:
        """Fetch deprecation/sunset notices from this provider."""
        ...
