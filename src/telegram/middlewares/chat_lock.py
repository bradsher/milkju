"""Per-chat asyncio lock for concurrent update safety.

When concurrent_updates is enabled, multiple handlers can run simultaneously.
This module provides per-chat locks to ensure that within the same chat,
long-running operations (AI responses, search, image generation) are still
serialized to prevent conversation history corruption and message interleaving.

Different chats can still be processed concurrently.
"""

import asyncio
from collections import defaultdict
from contextlib import asynccontextmanager

# Global per-chat lock dictionary
# defaultdict(asyncio.Lock) creates a new Lock automatically for each new chat_id
_chat_locks: dict[int, asyncio.Lock] = defaultdict(asyncio.Lock)


def get_chat_lock(chat_id: int) -> asyncio.Lock:
    """Get the asyncio Lock for a specific chat.
    
    Args:
        chat_id: Telegram chat ID.
        
    Returns:
        asyncio.Lock instance for the given chat.
    """
    return _chat_locks[chat_id]


@asynccontextmanager
async def chat_lock_with_timeout(chat_id: int, timeout: float = 60.0):
    """Acquire a chat lock with a timeout to prevent hanging.
    
    Args:
        chat_id: Telegram chat ID.
        timeout: Maximum time to wait for the lock in seconds.
        
    Raises:
        asyncio.TimeoutError: If the lock cannot be acquired within the timeout.
    """
    lock = _chat_locks[chat_id]
    try:
        await asyncio.wait_for(lock.acquire(), timeout=timeout)
    except asyncio.TimeoutError:
        raise asyncio.TimeoutError(f"Could not acquire lock for chat {chat_id} within {timeout}s")
        
    try:
        yield
    finally:
        lock.release()
