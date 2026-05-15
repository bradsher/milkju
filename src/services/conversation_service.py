"""Conversation service for managing message history."""

from __future__ import annotations

from typing import Optional, List

from src.repositories.message_repository import MessageRepository
from src.models.message import Message
from src.core.constants import MessageRole, TimeUnits


class ConversationService:
    """Service for managing conversation history and messages."""

    def __init__(self, message_repo: Optional[MessageRepository] = None):
        """Initialize conversation service.

        Args:
            message_repo: Message repository.
        """
        self.message_repo = message_repo or MessageRepository()

    async def add_message(
        self,
        user_id: int,
        role: str,
        content: str,
        message_id: Optional[int] = None,
        **metadata  # Accept all metadata as kwargs
    ) -> Message:
        """Add a message to conversation history.

        Args:
            user_id: User or chat ID.
            role: Message role (system, user, assistant).
            content: Message content.
            message_id: Telegram message ID.
            **metadata: Additional metadata fields (sender_id, chat_id, etc.)

        Returns:
            Created message instance.
        """
        return await self.message_repo.create(
            user_id, role, content, message_id, **metadata
        )

    async def add_user_message(
        self, 
        user_id: int, 
        content: str, 
        message_id: Optional[int] = None,
        **metadata
    ) -> Message:
        """Add a user message to conversation history.

        Args:
            user_id: User or chat ID.
            content: Message content.
            message_id: Telegram message ID.
            **metadata: Additional metadata fields.

        Returns:
            Created message instance.
        """
        return await self.add_message(
            user_id, MessageRole.USER.value, content, message_id, **metadata
        )

    async def add_assistant_message(
        self, 
        user_id: int, 
        content: str, 
        message_id: Optional[int] = None,
        **metadata
    ) -> Message:
        """Add an assistant message to conversation history.

        Args:
            user_id: User or chat ID.
            content: Message content.
            message_id: Telegram message ID.
            **metadata: Additional metadata fields.

        Returns:
            Created message instance.
        """
        return await self.add_message(
            user_id, MessageRole.ASSISTANT.value, content, message_id, **metadata
        )

    async def add_system_message(self, user_id: int, content: str) -> Message:
        """Add a system message to conversation history.

        Args:
            user_id: User or chat ID.
            content: Message content.

        Returns:
            Created message instance.
        """
        return await self.add_message(user_id, MessageRole.SYSTEM.value, content)

    async def get_conversation_history(
        self, user_id: int, limit: int = 10
    ) -> List[Message]:
        """Get conversation history in chronological order (oldest first).

        Args:
            user_id: User or chat ID.
            limit: Maximum number of messages.

        Returns:
            List of messages in chronological order.
        """
        return await self.message_repo.find_conversation_history(user_id, limit)

    async def get_messages_for_api(
        self, user_id: int, limit: int = 10, system_prompt: Optional[str] = None
    ) -> List[dict]:
        """Get conversation history formatted for AI API.

        Args:
            user_id: User or chat ID.
            limit: Maximum number of messages.
            system_prompt: Optional system prompt to prepend.

        Returns:
            List of message dicts with 'role' and 'content' keys.
        """
        messages = await self.get_conversation_history(user_id, limit)
        api_messages = [msg.to_dict() for msg in messages]

        # Prepend system prompt if provided
        if system_prompt:
            # Check if first message is already a system message
            if api_messages and api_messages[0]["role"] == MessageRole.SYSTEM.value:
                # Replace existing system message
                api_messages[0]["content"] = system_prompt
            else:
                # Insert system message at beginning
                api_messages.insert(
                    0, {"role": MessageRole.SYSTEM.value, "content": system_prompt}
                )

        return api_messages

    async def get_messages_since(
        self, user_id: int, start_time: float
    ) -> List[Message]:
        """Get messages since a specific time.

        Args:
            user_id: User or chat ID.
            start_time: Unix timestamp.

        Returns:
            List of messages since start_time.
        """
        return await self.message_repo.find_by_time_range(user_id, start_time)

    async def clear_conversation(self, user_id: int) -> int:
        """Clear all messages for a user/chat.

        Args:
            user_id: User or chat ID.

        Returns:
            Number of messages deleted.
        """
        return await self.message_repo.delete_by_user(user_id)

    async def count_messages(self, user_id: int) -> int:
        """Count messages for a user/chat.

        Args:
            user_id: User or chat ID.

        Returns:
            Total message count.
        """
        return await self.message_repo.count_messages(user_id)

    async def cleanup_old_messages(self, days: int = 30) -> int:
        """Delete messages older than specified days.

        Args:
            days: Age threshold in days (default: 30).

        Returns:
            Number of messages deleted.
        """
        seconds = days * TimeUnits.SECONDS_PER_DAY
        return await self.message_repo.cleanup_old_messages(seconds)

    async def has_conversation_history(self, user_id: int) -> bool:
        """Check if user has any conversation history.

        Args:
            user_id: User or chat ID.

        Returns:
            True if user has messages, False otherwise.
        """
        count = await self.count_messages(user_id)
        return count > 0

    async def delete_all_messages(self) -> int:
        """Delete all messages from all chats.
        
        Warning: This is a destructive operation that cannot be undone.
        Should only be called by super administrators.
        
        Returns:
            Number of messages deleted.
        """
        return await self.message_repo.delete_all()
