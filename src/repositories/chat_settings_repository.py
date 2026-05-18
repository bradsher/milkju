"""Chat settings repository for database operations."""

from __future__ import annotations

from typing import Optional, List
import aiosqlite

from src.repositories.base import BaseRepository
from src.models.chat_settings import ChatSettings, AutoSummarySettings


class ChatSettingsRepository(BaseRepository[ChatSettings]):
    """Repository for chat settings database operations."""

    @property
    def table_name(self) -> str:
        """Return the chat_settings table name."""
        return "chat_settings"

    async def _row_to_model(self, row: aiosqlite.Row) -> ChatSettings:
        """Convert database row to ChatSettings model.

        Args:
            row: Database row.

        Returns:
            ChatSettings instance.
        """
        return ChatSettings(
            chat_id=row["chat_id"],
            system_prompt=self._get_row_value(row, "system_prompt"),
            model=self._get_row_value(row, "model"),
            provider_id=self._get_row_value(row, "provider_id"),
        )

    async def find_by_chat_id(self, chat_id: int) -> Optional[ChatSettings]:
        """Find chat settings by chat ID.

        Args:
            chat_id: Chat ID.

        Returns:
            ChatSettings instance if found, None otherwise.
        """
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE chat_id = ?", (chat_id,)
        )
        if row:
            return await self._row_to_model(row)
        return None

    async def set_system_prompt(
        self, chat_id: int, system_prompt: Optional[str]
    ) -> ChatSettings:
        """Set or update system prompt for a chat.

        Args:
            chat_id: Chat ID.
            system_prompt: System prompt (None to clear).

        Returns:
            Updated ChatSettings instance.
        """
        await self.execute_query(
            f"""INSERT INTO {self.table_name} (chat_id, system_prompt)
                VALUES (?, ?)
                ON CONFLICT(chat_id) DO UPDATE SET system_prompt = excluded.system_prompt""",
            (chat_id, system_prompt),
        )
        return await self.find_by_chat_id(chat_id) or ChatSettings(
            chat_id=chat_id, system_prompt=system_prompt
        )

    async def set_model(
        self, chat_id: int, model: Optional[str], provider_id: Optional[int]
    ) -> ChatSettings:
        """Set or update model and provider for a chat.

        Args:
            chat_id: Chat ID.
            model: Model name (None to clear).
            provider_id: Provider ID (None to clear).

        Returns:
            Updated ChatSettings instance.
        """
        existing = await self.find_by_chat_id(chat_id)

        if existing:
            if model:
                await self.execute_query(
                    f"UPDATE {self.table_name} SET model = ?, provider_id = ? WHERE chat_id = ?",
                    (model, provider_id, chat_id),
                )
            else:
                # Reset
                await self.execute_query(
                    f"UPDATE {self.table_name} SET model = NULL, provider_id = NULL WHERE chat_id = ?",
                    (chat_id,),
                )
        else:
            if model:
                await self.execute_query(
                    f"INSERT INTO {self.table_name} (chat_id, model, provider_id) VALUES (?, ?, ?)",
                    (chat_id, model, provider_id),
                )

        return await self.find_by_chat_id(chat_id) or ChatSettings(
            chat_id=chat_id, model=model, provider_id=provider_id
        )


class AutoSummarySettingsRepository(BaseRepository[AutoSummarySettings]):
    """Repository for auto-summary settings database operations."""

    @property
    def table_name(self) -> str:
        """Return the auto_summary_settings table name."""
        return "auto_summary_settings"

    async def _row_to_model(self, row: aiosqlite.Row) -> AutoSummarySettings:
        """Convert database row to AutoSummarySettings model.

        Args:
            row: Database row.

        Returns:
            AutoSummarySettings instance.
        """
        return AutoSummarySettings(
            chat_id=row["chat_id"],
            enabled=bool(row["enabled"]),
            hour=self._get_row_value(row, "hour"),
            minute=self._get_row_value(row, "minute"),
            language=self._get_row_value(row, "language"),
            last_run_date=self._get_row_value(row, "last_run_date"),
            time2_hour=self._get_row_value(row, "time2_hour"),
            time2_minute=self._get_row_value(row, "time2_minute"),
            pin_enabled=bool(self._get_row_value(row, "pin_enabled") or 0),
            last_run_slot=self._get_row_value(row, "last_run_slot"),
            last_pinned_message_id=self._get_row_value(row, "last_pinned_message_id"),
            summary_model=self._get_row_value(row, "summary_model"),
            summary_provider_id=self._get_row_value(row, "summary_provider_id"),
        )

    async def find_by_chat_id(self, chat_id: int) -> Optional[AutoSummarySettings]:
        """Find auto-summary settings by chat ID.

        Args:
            chat_id: Chat ID.

        Returns:
            AutoSummarySettings instance if found, None otherwise.
        """
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE chat_id = ?", (chat_id,)
        )
        if row:
            return await self._row_to_model(row)
        return None

    async def find_all_enabled(self) -> List[AutoSummarySettings]:
        """Find all enabled auto-summary settings.

        Returns:
            List of enabled auto-summary settings.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE enabled = 1"
        )
        return [await self._row_to_model(row) for row in rows]

    async def upsert(
        self,
        chat_id: int,
        enabled: bool,
        hour: Optional[int] = None,
        minute: Optional[int] = None,
        language: Optional[str] = None,
        time2_hour: Optional[int] = None,
        time2_minute: Optional[int] = None,
        pin_enabled: bool = False,
    ) -> AutoSummarySettings:
        """Create or update auto-summary settings.

        Args:
            chat_id: Chat ID.
            enabled: Whether auto-summary is enabled.
            hour: Hour for time slot 1 (0-23).
            minute: Minute for time slot 1 (0-59).
            language: Summary language.
            time2_hour: Hour for optional time slot 2 (0-23).
            time2_minute: Minute for optional time slot 2 (0-59).
            pin_enabled: Whether to pin summary messages.

        Returns:
            Updated AutoSummarySettings instance.
        """
        existing = await self.find_by_chat_id(chat_id)

        if existing:
            await self.execute_query(
                f"""UPDATE {self.table_name}
                    SET enabled = ?, hour = ?, minute = ?, language = ?,
                        time2_hour = ?, time2_minute = ?, pin_enabled = ?
                    WHERE chat_id = ?""",
                (enabled, hour, minute, language, time2_hour, time2_minute, pin_enabled, chat_id),
            )
        else:
            await self.execute_query(
                f"""INSERT INTO {self.table_name}
                    (chat_id, enabled, hour, minute, language, time2_hour, time2_minute, pin_enabled)
                    VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
                (chat_id, enabled, hour, minute, language, time2_hour, time2_minute, pin_enabled),
            )

        return await self.find_by_chat_id(chat_id) or AutoSummarySettings(
            chat_id=chat_id,
            enabled=enabled,
            hour=hour,
            minute=minute,
            language=language,
            time2_hour=time2_hour,
            time2_minute=time2_minute,
            pin_enabled=pin_enabled,
        )

    async def update_last_run(self, chat_id: int, date: Optional[str]) -> bool:
        """Update last run date for auto-summary.

        Args:
            chat_id: Chat ID.
            date: Last run date (YYYY-MM-DD format) or None to clear.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET last_run_date = ? WHERE chat_id = ?",
            (date, chat_id),
        )
        return cursor.rowcount > 0

    async def update_last_run_slot(self, chat_id: int, slot: Optional[str]) -> bool:
        """Update last run slot for dual-time auto-summary.

        Args:
            chat_id: Chat ID.
            slot: Last run slot string ("YYYY-MM-DD_H:M") or None to clear.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET last_run_slot = ? WHERE chat_id = ?",
            (slot, chat_id),
        )
        return cursor.rowcount > 0

    async def update_last_pinned_message_id(self, chat_id: int, message_id: Optional[int]) -> bool:
        """Update the ID of the last pinned auto-summary message.

        Args:
            chat_id: Chat ID.
            message_id: Telegram message ID of the pinned message, or None to clear.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET last_pinned_message_id = ? WHERE chat_id = ?",
            (message_id, chat_id),
        )
        return cursor.rowcount > 0

    async def set_summary_model(
        self, chat_id: int, model: Optional[str], provider_id: Optional[int]
    ) -> AutoSummarySettings:
        """Set or update model and provider for summary.

        Args:
            chat_id: Chat ID.
            model: Model name (None to clear).
            provider_id: Provider ID (None to clear).

        Returns:
            Updated AutoSummarySettings instance.
        """
        existing = await self.find_by_chat_id(chat_id)

        if existing:
            await self.execute_query(
                f"UPDATE {self.table_name} SET summary_model = ?, summary_provider_id = ? WHERE chat_id = ?",
                (model, provider_id, chat_id),
            )
        else:
            await self.execute_query(
                f"INSERT INTO {self.table_name} (chat_id, summary_model, summary_provider_id) VALUES (?, ?, ?)",
                (chat_id, model, provider_id),
            )

        return await self.find_by_chat_id(chat_id) or AutoSummarySettings(
            chat_id=chat_id, summary_model=model, summary_provider_id=provider_id
        )
