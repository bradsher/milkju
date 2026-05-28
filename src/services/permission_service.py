"""Permission service for authorization checks."""

from __future__ import annotations

from typing import Optional
from telegram import Update, constants

from src.repositories.user_repository import UserRepository
from src.core.exceptions import PermissionDeniedError


class PermissionService:
    """Service for handling user permissions and authorization."""

    def __init__(self, user_repo: Optional[UserRepository] = None):
        """Initialize permission service.

        Args:
            user_repo: User repository (creates default if not provided).
        """
        self.user_repo = user_repo or UserRepository()

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin.

        Args:
            user_id: User ID to check.

        Returns:
            True if user is admin, False otherwise.
        """
        return await self.user_repo.is_admin(user_id)
        
    async def is_banned(self, user_id: int) -> bool:
        """Check if user is banned.

        Args:
            user_id: User ID to check.

        Returns:
            True if user is banned, False otherwise.
        """
        return await self.user_repo.is_banned(user_id)

    async def ban_user(self, user_id: int) -> None:
        """Ban a user.

        Args:
            user_id: User ID to ban.
        """
        await self.user_repo.set_banned(user_id, True)

    async def require_admin(self, user_id: int) -> None:
        """Require that user is an admin, raise exception if not.

        Args:
            user_id: User ID to check.

        Raises:
            PermissionDeniedError: If user is not an admin.
        """
        if not await self.is_admin(user_id):
            raise PermissionDeniedError(f"User {user_id} is not authorized as admin")

    async def is_super_admin(self, user_id: int) -> bool:
        """Check if user is a super admin.
        
        Super admins are defined in the SUPER_ADMIN_ID environment variable.
        They have unrestricted access to all system settings.
        
        Args:
            user_id: User ID to check.
            
        Returns:
            True if user is super admin.
        """
        import os
        super_admin_str = os.getenv("SUPER_ADMIN_ID", "")
        # Allow multiple IDs separated by comma
        super_admin_ids = [int(x.strip()) for x in super_admin_str.split(",") if x.strip().isdigit()]
        
        return user_id in super_admin_ids

    async def is_group_admin(self, update: Update) -> bool:
        """Check if user in update is a group admin or bot admin.
        
        Args:
            update: Telegram update object.
            
        Returns:
            True if user has admin rights.
        """
        user_id = self.get_user_id_from_update(update)
        if not user_id:
            return False
            
        # 1. Check Bot Admin (Super or Global)
        if await self.is_super_admin(user_id) or await self.is_admin(user_id):
            return True
            
        # 2. Check Group Admin
        chat = update.effective_chat
        if chat and chat.type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
            try:
                member = await chat.get_member(user_id)
                return member.status in [
                    constants.ChatMemberStatus.ADMINISTRATOR,
                    constants.ChatMemberStatus.OWNER,
                ]
            except Exception:
                return False
                
        # 3. Private Chat - user is "admin" of their own chat
        return chat.type == constants.ChatType.PRIVATE

    async def add_admin(self, user_id: int, is_admin: bool = True) -> None:
        """Add or update admin status for a user.

        Args:
            user_id: User ID.
            is_admin: Admin status.
        """
        await self.user_repo.create_or_update_admin(user_id, is_admin)

    async def remove_admin(self, user_id: int) -> None:
        """Remove admin privileges from a user.

        Args:
            user_id: User ID.
        """
        await self.user_repo.remove_admin(user_id)

    async def get_all_admins(self) -> list[int]:
        """Get list of all admin user IDs.

        Returns:
            List of admin user IDs.
        """
        users = await self.user_repo.find_all()
        return [user.user_id for user in users if user.is_admin]

    @staticmethod
    def get_user_id_from_update(update: Update) -> Optional[int]:
        """Extract user ID from Telegram update.

        Args:
            update: Telegram update object.

        Returns:
            User ID if found, None otherwise.
        """
        if update.effective_user:
            return update.effective_user.id
        return None

    async def check_admin_from_update(self, update: Update) -> bool:
        """Check if user from update is admin.

        Args:
            update: Telegram update object.

        Returns:
            True if user is admin, False otherwise.
        """
        user_id = self.get_user_id_from_update(update)
        if user_id is None:
            return False
        return await self.is_admin(user_id)
