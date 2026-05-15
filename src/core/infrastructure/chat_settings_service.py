"""Chat settings service for per-chat configuration."""

from __future__ import annotations

from typing import Optional

from src.repositories.chat_settings_repository import (
    ChatSettingsRepository,
    AutoSummarySettingsRepository,
)
from src.models.chat_settings import ChatSettings, AutoSummarySettings


class ChatSettingsService:
    """Service for managing per-chat settings."""

    def __init__(
        self,
        settings_repo: Optional[ChatSettingsRepository] = None,
        summary_repo: Optional[AutoSummarySettingsRepository] = None,
    ):
        """Initialize chat settings service.

        Args:
            settings_repo: Chat settings repository.
            summary_repo: Auto-summary settings repository.
        """
        self.settings_repo = settings_repo or ChatSettingsRepository()
        self.summary_repo = summary_repo or AutoSummarySettingsRepository()

    # Chat Settings

    async def get_settings(self, chat_id: int) -> Optional[ChatSettings]:
        """Get settings for a chat.

        Args:
            chat_id: Chat ID.

        Returns:
            ChatSettings if found, None otherwise.
        """
        return await self.settings_repo.find_by_chat_id(chat_id)

    async def get_system_prompt(self, chat_id: int) -> Optional[str]:
        """Get system prompt for a chat.

        Args:
            chat_id: Chat ID.

        Returns:
            System prompt if set, None otherwise.
        """
        settings = await self.get_settings(chat_id)
        return settings.system_prompt if settings else None

    async def set_system_prompt(
        self, chat_id: int, system_prompt: Optional[str]
    ) -> ChatSettings:
        """Set system prompt for a chat.

        Args:
            chat_id: Chat ID.
            system_prompt: System prompt (None to clear).

        Returns:
            Updated ChatSettings.
        """
        return await self.settings_repo.set_system_prompt(chat_id, system_prompt)

    async def get_model_and_provider(
        self, chat_id: int
    ) -> tuple[Optional[str], Optional[int]]:
        """Get model and provider ID for a chat.

        Args:
            chat_id: Chat ID.

        Returns:
            Tuple of (model, provider_id).
        """
        settings = await self.get_settings(chat_id)
        if settings:
            return settings.model, settings.provider_id
        return None, None

    async def set_model(
        self, chat_id: int, model: Optional[str], provider_id: Optional[int]
    ) -> ChatSettings:
        """Set model and provider for a chat.

        Args:
            chat_id: Chat ID.
            model: Model name (None to clear).
            provider_id: Provider ID (None to clear).

        Returns:
            Updated ChatSettings.
        """
        return await self.settings_repo.set_model(chat_id, model, provider_id)

    async def clear_model(self, chat_id: int) -> ChatSettings:
        """Clear model settings for a chat (revert to default).

        Args:
            chat_id: Chat ID.

        Returns:
            Updated ChatSettings.
        """
        return await self.set_model(chat_id, None, None)

    # Auto-Summary Settings

    async def get_auto_summary_settings(
        self, chat_id: int
    ) -> Optional[AutoSummarySettings]:
        """Get auto-summary settings for a chat.

        Args:
            chat_id: Chat ID.

        Returns:
            AutoSummarySettings if found, None otherwise.
        """
        return await self.summary_repo.find_by_chat_id(chat_id)

    async def get_all_enabled_auto_summaries(self) -> list[AutoSummarySettings]:
        """Get all enabled auto-summary settings.

        Returns:
            List of enabled auto-summary settings.
        """
        return await self.summary_repo.find_all_enabled()

    async def is_auto_summary_enabled(self, chat_id: int) -> bool:
        """Check if auto-summary is enabled for a chat.

        Args:
            chat_id: Chat ID.

        Returns:
            True if enabled, False otherwise.
        """
        settings = await self.get_auto_summary_settings(chat_id)
        return settings.enabled if settings else False

    async def enable_auto_summary(
        self,
        chat_id: int,
        hour: int,
        minute: int,
        language: Optional[str] = None,
        time2_hour: Optional[int] = None,
        time2_minute: Optional[int] = None,
        pin_enabled: bool = False,
    ) -> AutoSummarySettings:
        """Enable auto-summary for a chat.

        Args:
            chat_id: Chat ID.
            hour: Hour for time slot 1 (0-23).
            minute: Minute for time slot 1 (0-59).
            language: Summary language.
            time2_hour: Hour for optional second time slot (0-23).
            time2_minute: Minute for optional second time slot (0-59).
            pin_enabled: Whether to pin summary messages on success.

        Returns:
            Updated AutoSummarySettings.
        """
        return await self.summary_repo.upsert(
            chat_id=chat_id,
            enabled=True,
            hour=hour,
            minute=minute,
            language=language,
            time2_hour=time2_hour,
            time2_minute=time2_minute,
            pin_enabled=pin_enabled,
        )

    async def disable_auto_summary(self, chat_id: int) -> AutoSummarySettings:
        """Disable auto-summary for a chat.

        Args:
            chat_id: Chat ID.

        Returns:
            Updated AutoSummarySettings.
        """
        # Get existing settings to preserve all current values
        existing = await self.get_auto_summary_settings(chat_id)

        return await self.summary_repo.upsert(
            chat_id=chat_id,
            enabled=False,
            hour=existing.hour if existing else None,
            minute=existing.minute if existing else None,
            language=existing.language if existing else None,
            time2_hour=existing.time2_hour if existing else None,
            time2_minute=existing.time2_minute if existing else None,
            pin_enabled=existing.pin_enabled if existing else False,
        )

    async def update_auto_summary_last_run(
        self, chat_id: int, date: Optional[str]
    ) -> bool:
        """Update last run date for auto-summary.

        Args:
            chat_id: Chat ID.
            date: Last run date (YYYY-MM-DD) or None to clear.

        Returns:
            True if updated, False if not found.
        """
        return await self.summary_repo.update_last_run(chat_id, date)

    async def update_auto_summary_last_run_slot(
        self, chat_id: int, slot: Optional[str]
    ) -> bool:
        """Update last run slot for dual-time auto-summary.

        Args:
            chat_id: Chat ID.
            slot: Slot string ("YYYY-MM-DD_H:M") or None to clear.

        Returns:
            True if updated, False if not found.
        """
        return await self.summary_repo.update_last_run_slot(chat_id, slot)

    async def update_auto_summary_last_pinned_message_id(
        self, chat_id: int, message_id: Optional[int]
    ) -> bool:
        """Update the last pinned auto-summary message ID.

        Args:
            chat_id: Chat ID.
            message_id: Telegram message ID or None to clear.

        Returns:
            True if updated, False if not found.
        """
        return await self.summary_repo.update_last_pinned_message_id(chat_id, message_id)

    async def clear_auto_summary_last_run(self, chat_id: int) -> bool:
        """Clear last run tracking fields (allows immediate re-run after re-enable).

        Args:
            chat_id: Chat ID.

        Returns:
            True if updated, False if not found.
        """
        await self.update_auto_summary_last_run(chat_id, None)
        return await self.update_auto_summary_last_run_slot(chat_id, None)
