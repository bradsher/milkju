"""Base repository with common database operations."""

from __future__ import annotations

from typing import Generic, TypeVar, Optional, List, Any
from abc import ABC, abstractmethod
import aiosqlite

from src.database.connection import db

T = TypeVar("T")


class BaseRepository(ABC, Generic[T]):
    """Base repository providing common CRUD operations.

    Type parameter T represents the model type (User, Provider, etc.)
    """

    def __init__(self):
        """Initialize base repository."""
        self.db = db

    @property
    @abstractmethod
    def table_name(self) -> str:
        """Return the database table name.

        Must be implemented by subclasses.
        """
        pass

    @abstractmethod
    async def _row_to_model(self, row: aiosqlite.Row) -> T:
        """Convert database row to model instance.

        Args:
            row: Database row.

        Returns:
            Model instance.

        Must be implemented by subclasses.
        """
        pass

    @staticmethod
    def _get_row_value(row: aiosqlite.Row, key: str, default: Any = None) -> Any:
        """Safely get value from row with default for NULL/missing columns.

        Args:
            row: Database row.
            key: Column name.
            default: Default value if column is NULL or missing.

        Returns:
            Column value or default.
        """
        try:
            value = row[key]
            return value if value is not None else default
        except (KeyError, IndexError):
            return default

    async def find_by_id(self, id: int) -> Optional[T]:
        """Find entity by ID.

        Args:
            id: Entity ID.

        Returns:
            Model instance if found, None otherwise.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                f"SELECT * FROM {self.table_name} WHERE id = ?", (id,)
            )
            row = await cursor.fetchone()
            if row:
                return await self._row_to_model(row)
            return None

    async def find_all(self, limit: Optional[int] = None, offset: int = 0) -> List[T]:
        """Find all entities.

        Args:
            limit: Maximum number of results.
            offset: Number of results to skip.

        Returns:
            List of model instances.
        """
        query = f"SELECT * FROM {self.table_name}"
        params: List[Any] = []

        if limit is not None:
            query += " LIMIT ? OFFSET ?"
            params.extend([limit, offset])

        async with self.db.get_connection() as conn:
            cursor = await conn.execute(query, params)
            rows = await cursor.fetchall()
            return [await self._row_to_model(row) for row in rows]

    async def count(self) -> int:
        """Count total entities.

        Returns:
            Total count.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(f"SELECT COUNT(*) FROM {self.table_name}")
            row = await cursor.fetchone()
            return row[0] if row else 0

    async def delete_by_id(self, id: int) -> bool:
        """Delete entity by ID.

        Args:
            id: Entity ID.

        Returns:
            True if deleted, False if not found.
        """
        async with self.db.transaction() as conn:
            cursor = await conn.execute(
                f"DELETE FROM {self.table_name} WHERE id = ?", (id,)
            )
            return cursor.rowcount > 0

    async def exists(self, id: int) -> bool:
        """Check if entity exists by ID.

        Args:
            id: Entity ID.

        Returns:
            True if exists, False otherwise.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(
                f"SELECT 1 FROM {self.table_name} WHERE id = ? LIMIT 1", (id,)
            )
            row = await cursor.fetchone()
            return row is not None

    async def delete(self, id: int) -> bool:
        """Delete entity by ID (alias for delete_by_id).

        Args:
            id: Entity ID.

        Returns:
            True if deleted, False if not found.
        """
        return await self.delete_by_id(id)

    async def execute_query(

        self, query: str, params: tuple = ()
    ) -> aiosqlite.Cursor:
        """Execute a custom query with transaction support.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            Database cursor.
        """
        async with self.db.transaction() as conn:
            return await conn.execute(query, params)

    async def fetch_one(
        self, query: str, params: tuple = ()
    ) -> Optional[aiosqlite.Row]:
        """Fetch single row from custom query.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            Database row if found, None otherwise.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchone()

    async def fetch_all(self, query: str, params: tuple = ()) -> List[aiosqlite.Row]:
        """Fetch all rows from custom query.

        Args:
            query: SQL query.
            params: Query parameters.

        Returns:
            List of database rows.
        """
        async with self.db.get_connection() as conn:
            cursor = await conn.execute(query, params)
            return await cursor.fetchall()
