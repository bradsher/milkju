"""Repository for global system configuration."""

from __future__ import annotations

from typing import Optional

from src.database.connection import db


class ConfigRepository:
    """Repository for managing global system configuration."""

    def __init__(self):
        """Initialize config repository."""
        self.db = db

    async def get(self, key: str) -> Optional[str]:
        """Get a config value by key.

        Args:
            key: Configuration key.

        Returns:
            Config value if found, None otherwise.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "SELECT value FROM config WHERE key = ?", (key,)
            )
            row = await cursor.fetchone()
            return row[0] if row else None

    async def set(self, key: str, value: Optional[str]) -> None:
        """Set a config value.

        Args:
            key: Configuration key.
            value: Configuration value (None to delete).
        """
        async with self.db.get_connection() as conn:
            if value is None:
                await conn.execute("DELETE FROM config WHERE key = ?", (key,))
            else:
                await conn.execute(
                    "INSERT OR REPLACE INTO config (key, value) VALUES (?, ?)",
                    (key, value),
                )
            await conn.commit()

    async def get_all(self) -> dict[str, str]:
        """Get all config values.

        Returns:
            Dictionary of all config key-value pairs.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute("SELECT key, value FROM config")
            rows = await cursor.fetchall()
            return {row[0]: row[1] for row in rows}

    async def delete(self, key: str) -> bool:
        """Delete a config value.

        Args:
            key: Configuration key.

        Returns:
            True if deleted, False if not found.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                "DELETE FROM config WHERE key = ?", (key,)
            )
            await conn.commit()
            return cursor.rowcount > 0
