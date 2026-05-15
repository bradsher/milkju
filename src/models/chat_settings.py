"""Chat settings data model."""

from __future__ import annotations

from dataclasses import dataclass
from typing import Optional


@dataclass
class ChatSettings:
    """Represents settings for a chat (user or group)."""

    chat_id: int
    system_prompt: Optional[str] = None
    model: Optional[str] = None
    provider_id: Optional[int] = None

    def __post_init__(self) -> None:
        """Validate chat settings data after initialization."""
        if self.chat_id == 0:
            raise ValueError("chat_id cannot be 0")

    @property
    def has_custom_model(self) -> bool:
        """Check if chat has a custom model configured."""
        return self.model is not None

    @property
    def has_custom_provider(self) -> bool:
        """Check if chat has a custom provider configured."""
        return self.provider_id is not None

    @property
    def has_custom_system_prompt(self) -> bool:
        """Check if chat has a custom system prompt."""
        return self.system_prompt is not None


@dataclass
class AutoSummarySettings:
    """Represents auto-summary configuration for a chat."""

    chat_id: int
    enabled: bool = False
    hour: Optional[int] = None
    minute: Optional[int] = None
    language: Optional[str] = None
    last_run_date: Optional[str] = None
    # Dual time slot support
    time2_hour: Optional[int] = None
    time2_minute: Optional[int] = None
    pin_enabled: bool = False
    last_run_slot: Optional[str] = None  # Format: "YYYY-MM-DD_H:M"
    last_pinned_message_id: Optional[int] = None  # For unpin-before-pin

    def __post_init__(self) -> None:
        """Validate auto-summary settings data after initialization."""
        if self.chat_id == 0:
            raise ValueError("chat_id cannot be 0")
        if self.enabled:
            if self.hour is None or self.minute is None:
                raise ValueError("hour and minute are required when enabled")
            if not (0 <= self.hour <= 23):
                raise ValueError("hour must be between 0 and 23")
            if not (0 <= self.minute <= 59):
                raise ValueError("minute must be between 0 and 59")

    @property
    def has_two_times(self) -> bool:
        """Return True if a second time slot is configured."""
        return self.time2_hour is not None and self.time2_minute is not None

    @property
    def summary_hours(self) -> int:
        """Hours to summarize per trigger: 12 for dual slots, 24 for single."""
        return 12 if self.has_two_times else 24

    @property
    def time_string(self) -> str:
        """Return formatted time string (HH:MM)."""
        if self.hour is None or self.minute is None:
            return "Not set"
        return f"{self.hour:02d}:{self.minute:02d}"

    @property
    def time2_string(self) -> str:
        """Return formatted second time string (HH:MM)."""
        if self.time2_hour is None or self.time2_minute is None:
            return "Not set"
        return f"{self.time2_hour:02d}:{self.time2_minute:02d}"
