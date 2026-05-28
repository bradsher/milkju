"""Database connection management."""

from __future__ import annotations

import aiosqlite
from contextlib import asynccontextmanager
from typing import AsyncGenerator
from src.core.constants import DB_NAME


class DatabaseConnection:
    """Manages database connections with context manager support."""

    def __init__(self, db_path: str = DB_NAME):
        """Initialize database connection manager.

        Args:
            db_path: Path to the SQLite database file.
        """
        self.db_path = db_path

    @asynccontextmanager
    async def get_connection(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a database connection as an async context manager.

        Yields:
            Database connection.

        Example:
            async with db.get_connection() as conn:
                cursor = await conn.execute("SELECT * FROM users")
                rows = await cursor.fetchall()
        """
        async with aiosqlite.connect(self.db_path, timeout=20.0) as conn:
            conn.row_factory = aiosqlite.Row
            yield conn

    @asynccontextmanager
    async def transaction(self) -> AsyncGenerator[aiosqlite.Connection, None]:
        """Get a database connection with transaction support.

        Automatically commits on successful completion or rolls back on error.

        Yields:
            Database connection with transaction.

        Example:
            async with db.transaction() as conn:
                await conn.execute("INSERT INTO users ...")
                await conn.execute("UPDATE settings ...")
                # Commits automatically if no exception
        """
        async with aiosqlite.connect(self.db_path, timeout=20.0) as conn:
            conn.row_factory = aiosqlite.Row
            try:
                yield conn
                await conn.commit()
            except Exception:
                await conn.rollback()
                raise


# Global database connection instance
db = DatabaseConnection()
