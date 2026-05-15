"""Author preset repository for database operations."""

from __future__ import annotations

from typing import Optional, List
import aiosqlite

from src.repositories.base import BaseRepository
from src.models.author_preset import AuthorPreset
from src.core.exceptions import DuplicateEntityError


class AuthorPresetRepository(BaseRepository[AuthorPreset]):
    """Repository for author preset database operations."""

    @property
    def table_name(self) -> str:
        """Return the author_presets table name."""
        return "author_presets"

    async def _row_to_model(self, row: aiosqlite.Row) -> AuthorPreset:
        """Convert database row to AuthorPreset model.

        Args:
            row: Database row.

        Returns:
            AuthorPreset instance.
        """
        return AuthorPreset(
            id=row["id"],
            name=row["name"],
            content=row["content"],
            created_by=row["created_by"],
            is_active=bool(row["is_active"]),
            created_at=row["created_at"],
        )

    async def find_by_name(self, name: str) -> Optional[AuthorPreset]:
        """Find preset by name (case-insensitive).

        Args:
            name: Preset name/alias.

        Returns:
            AuthorPreset instance if found, None otherwise.
        """
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE LOWER(name) = LOWER(?)", (name,)
        )
        if row:
            return await self._row_to_model(row)
        return None

    async def find_all(self) -> List[AuthorPreset]:
        """Find all presets.

        Returns:
            List of all presets.
        """
        rows = await self.fetch_all(f"SELECT * FROM {self.table_name} ORDER BY name")
        return [await self._row_to_model(row) for row in rows]

    async def find_active(self) -> List[AuthorPreset]:
        """Find all active presets.

        Returns:
            List of active presets.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE is_active = 1 ORDER BY name"
        )
        return [await self._row_to_model(row) for row in rows]

    async def find_by_creator(self, user_id: int) -> List[AuthorPreset]:
        """Find all presets created by a user.

        Args:
            user_id: Creator's user ID.

        Returns:
            List of presets by that user.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE created_by = ? ORDER BY name",
            (user_id,),
        )
        return [await self._row_to_model(row) for row in rows]

    async def create(self, name: str, content: str, created_by: int) -> AuthorPreset:
        """Create a new author preset.

        Args:
            name: Preset name/alias (no spaces).
            content: Actual author string.
            created_by: Creator's user ID.

        Returns:
            Created AuthorPreset instance.

        Raises:
            DuplicateEntityError: If preset with name already exists.
            ValueError: If name contains spaces.
        """
        if ' ' in name:
            raise ValueError("Preset name cannot contain spaces")
        
        existing = await self.find_by_name(name)
        if existing:
            raise DuplicateEntityError(f"Preset with name '{name}' already exists")

        cursor = await self.execute_query(
            f"INSERT INTO {self.table_name} (name, content, created_by) VALUES (?, ?, ?)",
            (name, content, created_by),
        )
        return AuthorPreset(
            id=cursor.lastrowid,
            name=name,
            content=content,
            created_by=created_by,
            is_active=True,
        )

    async def update(
        self, preset_id: int, name: Optional[str] = None, content: Optional[str] = None
    ) -> bool:
        """Update a preset.

        Args:
            preset_id: Preset ID.
            name: New name (optional).
            content: New content (optional).

        Returns:
            True if updated, False if not found.
        """
        updates = []
        params = []
        
        if name is not None:
            if ' ' in name:
                raise ValueError("Preset name cannot contain spaces")
            updates.append("name = ?")
            params.append(name)
        
        if content is not None:
            updates.append("content = ?")
            params.append(content)
        
        if not updates:
            return False
        
        params.append(preset_id)
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET {', '.join(updates)} WHERE id = ?",
            tuple(params),
        )
        return cursor.rowcount > 0

    async def update_active_status(self, preset_id: int, is_active: bool) -> bool:
        """Update preset active status.

        Args:
            preset_id: Preset ID.
            is_active: New active status.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET is_active = ? WHERE id = ?",
            (is_active, preset_id),
        )
        return cursor.rowcount > 0

    async def delete(self, preset_id: int) -> bool:
        """Delete a preset by ID.

        Args:
            preset_id: Preset ID.

        Returns:
            True if deleted, False if not found.
        """
        return await self.delete_by_id(preset_id)
