"""Service for rate limiting user requests and preventing abuse."""

from __future__ import annotations

import time
import logging
from collections import defaultdict
from typing import Literal

from src.services.permission_service import PermissionService

logger = logging.getLogger(__name__)

RateLimitStatus = Literal["ALLOWED", "RATE_LIMITED", "BANNED"]

class RateLimitService:
    """Service for handling user request rate limits and auto-bans."""
    
    # Store request timestamps per user_id (In-memory token bucket)
    _user_requests: dict[int, list[float]] = defaultdict(list)
    # Track violations for DDoS protection
    _user_violations: dict[int, int] = defaultdict(int)
    
    # After how many rate limit violations should we ban the user?
    MAX_VIOLATIONS = 5

    def __init__(self, permission_service: PermissionService | None = None):
        """Initialize the rate limit service."""
        self.permission_service = permission_service or PermissionService()

    async def check_and_record(self, user_id: int, limit: int, window_seconds: int = 3600) -> RateLimitStatus:
        """Check if user has exceeded their rate limit.
        
        Args:
            user_id: The Telegram user ID.
            limit: Maximum requests allowed in the time window.
            window_seconds: Time window in seconds (default 1 hour).
            
        Returns:
            RateLimitStatus enum indicating if the request should proceed.
        """
        # 1. If user is already banned in DB, return BANNED immediately
        if await self.permission_service.is_banned(user_id):
            return "BANNED"
            
        now = time.time()
        
        # 2. Clean up old timestamps outside the sliding window
        self._user_requests[user_id] = [
            t for t in self._user_requests[user_id] 
            if now - t <= window_seconds
        ]
        
        # 3. Check if they are currently rate limited
        if len(self._user_requests[user_id]) >= limit:
            # They exceeded the limit. Increment violation counter.
            self._user_violations[user_id] += 1
            
            # If they keep spamming after being limited, ban them
            if self._user_violations[user_id] >= self.MAX_VIOLATIONS:
                logger.warning(f"User {user_id} exceeded violation limit. Auto-banning user.")
                await self.permission_service.ban_user(user_id)
                # Cleanup memory as they are now persistently banned in DB
                self._user_requests.pop(user_id, None)
                self._user_violations.pop(user_id, None)
                return "BANNED"
                
            return "RATE_LIMITED"
            
        # 4. User is within limits. 
        # Reset violations since they might have waited enough time to recover
        if user_id in self._user_violations:
            self._user_violations[user_id] = 0
            
        # Record this valid request
        self._user_requests[user_id].append(now)
        
        return "ALLOWED"
