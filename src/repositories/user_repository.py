"""User repository for database operations."""

from __future__ import annotations

from typing import Optional
import aiosqlite

from src.repositories.base import BaseRepository
from src.models.user import User


class UserRepository(BaseRepository[User]):
    """Repository for user database operations."""

    @property
    def table_name(self) -> str:
        """Return the users table name."""
        return "users"

    async def _row_to_model(self, row: aiosqlite.Row) -> User:
        """Convert database row to User model.

        Args:
            row: Database row.

        Returns:
            User instance.
        """
        # Handle older database versions where is_banned might not exist yet
        is_banned = False
        if "is_banned" in row.keys():
            is_banned = bool(row["is_banned"])
            
        return User(
            user_id=row["user_id"],
            is_admin=bool(row["is_admin"]),
            is_banned=is_banned,
        )

    async def find_by_user_id(self, user_id: int) -> Optional[User]:
        """Find user by user_id.

        Args:
            user_id: Telegram user ID.

        Returns:
            User instance if found, None otherwise.
        """
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE user_id = ?", (user_id,)
        )
        if row:
            return await self._row_to_model(row)
        return None

    async def is_admin(self, user_id: int) -> bool:
        """Check if user is an admin.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if user is admin, False otherwise.
        """
        user = await self.find_by_user_id(user_id)
        return user.is_admin if user else False
        
    async def is_banned(self, user_id: int) -> bool:
        """Check if user is banned.

        Args:
            user_id: Telegram user ID.

        Returns:
            True if user is banned, False otherwise.
        """
        user = await self.find_by_user_id(user_id)
        return user.is_banned if user else False

    async def create_or_update_admin(self, user_id: int, is_admin: bool = True) -> User:
        """Create or update user admin status.

        Args:
            user_id: Telegram user ID.
            is_admin: Admin status.

        Returns:
            User instance.
        """
        await self.execute_query(
            f"""
            INSERT INTO {self.table_name} (user_id, is_admin) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_admin = excluded.is_admin
            """,
            (user_id, is_admin),
        )
        return await self.find_by_user_id(user_id)

    async def set_banned(self, user_id: int, is_banned: bool = True) -> User:
        """Create or update user ban status.

        Args:
            user_id: Telegram user ID.
            is_banned: Ban status.

        Returns:
            User instance.
        """
        await self.execute_query(
            f"""
            INSERT INTO {self.table_name} (user_id, is_banned) 
            VALUES (?, ?)
            ON CONFLICT(user_id) DO UPDATE SET is_banned = excluded.is_banned
            """,
            (user_id, is_banned),
        )
        return await self.find_by_user_id(user_id)

    async def add_admin(self, user_id: int) -> User:
        """Add user as admin.

        Args:
            user_id: Telegram user ID.

        Returns:
            User instance with admin privileges.
        """
        return await self.create_or_update_admin(user_id, True)

    async def remove_admin(self, user_id: int) -> User:
        """Remove admin privileges from user.

        Args:
            user_id: Telegram user ID.

        Returns:
            User instance without admin privileges.
        """
        return await self.create_or_update_admin(user_id, False)
