"""Author preset data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class AuthorPreset:
    """Represents a NovelAI author string preset.
    
    Author presets allow storing artist tags/styles with a codename alias,
    enabling use in public chats without exposing the actual content.
    """

    id: int
    name: str           # Alias/codename (no spaces)
    content: str        # Actual author string (hidden from non-owners)
    created_by: int     # User ID of creator
    is_active: bool = True
    created_at: Optional[datetime] = None

    def __post_init__(self) -> None:
        """Validate preset data after initialization."""
        if not self.name:
            raise ValueError("Preset name cannot be empty")
        if ' ' in self.name:
            raise ValueError("Preset name cannot contain spaces")
        if not self.content:
            raise ValueError("Preset content cannot be empty")
        if self.created_by <= 0:
            raise ValueError("created_by must be positive")

    @property
    def masked_content(self) -> str:
        """Return a masked version of the content for display to non-owners."""
        if len(self.content) < 12:
            return "***"
        return f"{self.content[:8]}...{self.content[-4:]}"
