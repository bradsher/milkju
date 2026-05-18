"""Message data model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional
from src.core.constants import MessageRole


@dataclass
class Message:
    """Represents a conversation message."""

    id: Optional[int]
    user_id: int  # DEPRECATED: 保留向后兼容，新代码使用chat_id
    role: str
    content: str
    message_id: Optional[int] = None  # Telegram message ID
    message_ids: Optional[str] = None # 存储多个 message_id (逗号分隔)
    timestamp: Optional[datetime] = None
    
    # New fields for metadata
    sender_id: Optional[int] = None           # 发送者Telegram ID
    sender_username: Optional[str] = None     # 发送者@username
    sender_first_name: Optional[str] = None   # 发送者名字快照
    sender_full_name: Optional[str] = None    # 发送者全名
    
    chat_id: Optional[int] = None             # 消息所属chat ID
    chat_type: Optional[str] = None           # private/group/supergroup/channel
    chat_username: Optional[str] = None       # 公开群组username
    
    is_forwarded: bool = False                # 是否为转发
    forward_from_id: Optional[int] = None     # 原始发送者ID
    forward_from_username: Optional[str] = None
    forward_from_name: Optional[str] = None
    forward_date: Optional[datetime] = None
    
    reply_to_message_id: Optional[int] = None # 回复的消息ID
    reply_to_user_id: Optional[int] = None    # 被回复者ID

    def __post_init__(self) -> None:
        """Validate message data after initialization."""
        if self.user_id == 0:
            raise ValueError("user_id cannot be zero")
        if not self.content:
            raise ValueError("Message content cannot be empty")
        if self.role not in [MessageRole.SYSTEM.value, MessageRole.USER.value, MessageRole.ASSISTANT.value]:
            raise ValueError(f"Invalid role: {self.role}")

    @property
    def is_system(self) -> bool:
        """Check if this is a system message."""
        return self.role == MessageRole.SYSTEM.value

    @property
    def is_user(self) -> bool:
        """Check if this is a user message."""
        return self.role == MessageRole.USER.value

    @property
    def is_assistant(self) -> bool:
        """Check if this is an assistant message."""
        return self.role == MessageRole.ASSISTANT.value

    def to_dict(self) -> dict:
        """Convert message to dictionary format for AI API."""
        return {"role": self.role, "content": self.content}
    
    def generate_message_url(self) -> Optional[str]:
        """生成t.me消息链接
        
        Returns:
            消息的t.me URL，如果无法生成则返回None
        """
        if not self.message_id or not self.chat_id:
            return None
        
        # 公开群组/频道：使用username
        if self.chat_username:
            return f"https://t.me/{self.chat_username}/{self.message_id}"
        
        # 私有群组/超级群组：使用chat_id（需要去掉-100前缀）
        if self.chat_type in ['supergroup', 'group']:
            # Telegram私有超级群组ID格式：-100xxxxxxxxxx
            chat_id_str = str(self.chat_id)
            if chat_id_str.startswith('-100'):
                chat_id_clean = chat_id_str[4:]  # 去掉-100
                return f"https://t.me/c/{chat_id_clean}/{self.message_id}"
        
        # 私聊消息无法生成公开链接
        return None

