"""User data model."""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class User:
    """Represents a user in the system."""

    user_id: int
    is_admin: bool = False

    def __post_init__(self) -> None:
        """Validate user data after initialization."""
        if self.user_id <= 0:
            raise ValueError("user_id must be positive")
