"""Message repository for database operations."""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime
import aiosqlite

from src.repositories.base import BaseRepository
from src.models.message import Message
from src.core.constants import TimeUnits
from src.utils.text_sanitizer import sanitize_text


class MessageRepository(BaseRepository[Message]):
    """Repository for message database operations."""

    @property
    def table_name(self) -> str:
        """Return the conversations table name."""
        return "conversations"

    async def _row_to_model(self, row: aiosqlite.Row) -> Message:
        """Convert database row to Message model.

        Args:
            row: Database row.

        Returns:
            Message instance.
        """
        # Parse timestamp if it's a string
        timestamp = row["timestamp"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)
        
        # Parse forward_date if exists and is string
        forward_date = self._get_row_value(row, "forward_date")
        if forward_date and isinstance(forward_date, str):
            forward_date = datetime.fromisoformat(forward_date)

        return Message(
            id=row["id"],
            user_id=row["user_id"],
            role=row["role"],
            content=row["content"],
            message_id=self._get_row_value(row, "message_id"),
            message_ids=self._get_row_value(row, "message_ids"),
            timestamp=timestamp,
            # New metadata fields
            sender_id=self._get_row_value(row, "sender_id"),
            sender_username=self._get_row_value(row, "sender_username"),
            sender_first_name=self._get_row_value(row, "sender_first_name"),
            sender_full_name=self._get_row_value(row, "sender_full_name"),
            chat_id=self._get_row_value(row, "chat_id"),
            chat_type=self._get_row_value(row, "chat_type"),
            chat_username=self._get_row_value(row, "chat_username"),
            is_forwarded=bool(self._get_row_value(row, "is_forwarded")),
            forward_from_id=self._get_row_value(row, "forward_from_id"),
            forward_from_username=self._get_row_value(row, "forward_from_username"),
            forward_from_name=self._get_row_value(row, "forward_from_name"),
            forward_date=forward_date,
            reply_to_message_id=self._get_row_value(row, "reply_to_message_id"),
            reply_to_user_id=self._get_row_value(row, "reply_to_user_id"),
        )

    async def create(
        self,
        user_id: int,
        role: str,
        content: str,
        message_id: Optional[int] = None,
        message_ids: Optional[str] = None,
        # New metadata parameters
        sender_id: Optional[int] = None,
        sender_username: Optional[str] = None,
        sender_first_name: Optional[str] = None,
        sender_full_name: Optional[str] = None,
        chat_id: Optional[int] = None,
        chat_type: Optional[str] = None,
        chat_username: Optional[str] = None,
        is_forwarded: bool = False,
        forward_from_id: Optional[int] = None,
        forward_from_username: Optional[str] = None,
        forward_from_name: Optional[str] = None,
        forward_date: Optional[datetime] = None,
        reply_to_message_id: Optional[int] = None,
        reply_to_user_id: Optional[int] = None,
    ) -> Message:
        """Create a new message with metadata.

        Args:
            user_id: User or chat ID (保留向后兼容).
            role: Message role (system, user, assistant).
            content: Message content.
            message_id: Telegram message ID.
            sender_id: Sender's Telegram numeric ID.
            sender_username: Sender's @username.
            sender_first_name: Sender's first name snapshot.
            sender_full_name: Sender's full name snapshot.
            chat_id: Chat ID where message was sent.
            chat_type: Chat type (private/group/supergroup/channel).
            chat_username: Public chat's @username.
            is_forwarded: Whether this is a forwarded message.
            forward_from_id: Original sender ID (for forwards).
            forward_from_username: Original sender username (for forwards).
            forward_from_name: Original sender name (for forwards).
            forward_date: Original message date (for forwards).
            reply_to_message_id: ID of replied-to message.
            reply_to_user_id: User ID of replied-to message sender.

        Returns:
            Created message instance.
        """
        # 清洗敏感内容（插入零宽字符）
        sanitized_content = sanitize_text(content)
        
        cursor = await self.execute_query(
            f"""INSERT INTO {self.table_name} (
                user_id, role, content, message_id, message_ids,
                sender_id, sender_username, sender_first_name, sender_full_name,
                chat_id, chat_type, chat_username,
                is_forwarded, forward_from_id, forward_from_username, forward_from_name, forward_date,
                reply_to_message_id, reply_to_user_id
            ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (
                user_id, role, sanitized_content, message_id, message_ids,
                sender_id, sender_username, sender_first_name, sender_full_name,
                chat_id, chat_type, chat_username,
                is_forwarded, forward_from_id, forward_from_username, forward_from_name, forward_date,
                reply_to_message_id, reply_to_user_id
            ),
        )
        return Message(
            id=cursor.lastrowid,
            user_id=user_id,
            role=role,
            content=sanitized_content,
            message_id=message_id,
            message_ids=message_ids,
            timestamp=datetime.now(),
            sender_id=sender_id,
            sender_username=sender_username,
            sender_first_name=sender_first_name,
            sender_full_name=sender_full_name,
            chat_id=chat_id,
            chat_type=chat_type,
            chat_username=chat_username,
            is_forwarded=is_forwarded,
            forward_from_id=forward_from_id,
            forward_from_username=forward_from_username,
            forward_from_name=forward_from_name,
            forward_date=forward_date,
            reply_to_message_id=reply_to_message_id,
            reply_to_user_id=reply_to_user_id,
        )

    async def find_by_user(
        self, user_id: int, limit: int = 10, offset: int = 0
    ) -> List[Message]:
        """Find messages for a user, ordered by timestamp descending.

        Args:
            user_id: User or chat ID.
            limit: Maximum number of messages.
            offset: Number of messages to skip.

        Returns:
            List of messages (most recent first).
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE user_id = ? ORDER BY timestamp DESC LIMIT ? OFFSET ?",
            (user_id, limit, offset),
        )
        return [await self._row_to_model(row) for row in rows]

    async def find_conversation_history(
        self, user_id: int, limit: int = 10
    ) -> List[Message]:
        """Get conversation history in chronological order.

        Args:
            user_id: User or chat ID.
            limit: Maximum number of messages.

        Returns:
            List of messages (oldest first).
        """
        messages = await self.find_by_user(user_id, limit=limit)
        return list(reversed(messages))  # Reverse to get chronological order

    async def find_by_time_range(
        self, user_id: int, start_time: float
    ) -> List[Message]:
        """Find messages since a specific time.

        Args:
            user_id: User or chat ID.
            start_time: Unix timestamp.

        Returns:
            List of messages since start_time, ordered chronologically.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE user_id = ? AND timestamp >= datetime(?, 'unixepoch') ORDER BY timestamp ASC",
            (user_id, start_time),
        )
        return [await self._row_to_model(row) for row in rows]

    async def delete_by_user(self, user_id: int) -> int:
        """Delete all messages for a user.

        Args:
            user_id: User or chat ID.

        Returns:
            Number of deleted messages.
        """
        cursor = await self.execute_query(
            f"DELETE FROM {self.table_name} WHERE user_id = ?", (user_id,)
        )
        return cursor.rowcount

    async def cleanup_old_messages(
        self, seconds: int = TimeUnits.SECONDS_PER_DAY * 30
    ) -> int:
        """Delete messages older than specified seconds.

        Args:
            seconds: Age threshold in seconds (default: 30 days).

        Returns:
            Number of deleted messages.
        """
        cursor = await self.execute_query(
            f"DELETE FROM {self.table_name} WHERE timestamp < datetime('now', '-{seconds} seconds')"
        )
        return cursor.rowcount

    async def count_messages(self, user_id: int) -> int:
        """Count messages for a user.

        Args:
            user_id: User or chat ID.

        Returns:
            Total message count.
        """
        row = await self.fetch_one(
            f"SELECT COUNT(*) as count FROM {self.table_name} WHERE user_id = ?",
            (user_id,),
        )
        return row["count"] if row else 0

    async def delete_all(self) -> int:
        """Delete all messages from all chats.
        
        Warning: This is a destructive operation that cannot be undone.
        
        Returns:
            Number of deleted messages.
        """
        cursor = await self.execute_query(
            f"DELETE FROM {self.table_name}"
        )
        return cursor.rowcount
