"""Provider data model."""

from __future__ import annotations

from dataclasses import dataclass
from src.core.constants import ClientType


@dataclass
class Provider:
    """Represents an AI provider."""

    id: int
    name: str
    base_url: str
    is_active: bool = True
    client_type: str = ClientType.OPENAI.value

    def __post_init__(self) -> None:
        """Validate provider data after initialization."""
        if not self.name:
            raise ValueError("Provider name cannot be empty")
        if not self.base_url:
            raise ValueError("Provider base_url cannot be empty")

    @property
    def is_google(self) -> bool:
        """Check if this is a Google provider."""
        return self.client_type == ClientType.GOOGLE.value

    @property
    def is_openai(self) -> bool:
        """Check if this is an OpenAI-compatible provider."""
        return self.client_type == ClientType.OPENAI.value


@dataclass
class APIKey:
    """Represents an API key for a provider."""

    id: int
    provider_id: int
    key: str
    is_active: bool = True

    def __post_init__(self) -> None:
        """Validate API key data after initialization."""
        if not self.key:
            raise ValueError("API key cannot be empty")
        if self.provider_id <= 0:
            raise ValueError("provider_id must be positive")

    @property
    def masked_key(self) -> str:
        """Return a masked version of the key for display."""
        if len(self.key) < 8:
            return "***"
        return f"{self.key[:5]}...{self.key[-3:]}"


@dataclass
class ProviderModel:
    """Represents a model available for a provider."""

    id: int
    provider_id: int
    model: str

    def __post_init__(self) -> None:
        """Validate provider model data after initialization."""
        if not self.model:
            raise ValueError("Model name cannot be empty")
        if self.provider_id <= 0:
            raise ValueError("provider_id must be positive")
