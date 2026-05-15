"""File attachment repository for database operations."""

from __future__ import annotations

from typing import List, Optional
from datetime import datetime, timedelta
import aiosqlite

from src.repositories.base import BaseRepository
from src.models.file_attachment import FileAttachment


class FileRepository(BaseRepository[FileAttachment]):
    """Repository for file attachment database operations."""

    @property
    def table_name(self) -> str:
        """Return the file_attachments table name."""
        return "file_attachments"

    async def _row_to_model(self, row: aiosqlite.Row) -> FileAttachment:
        """Convert database row to FileAttachment model.

        Args:
            row: Database row.

        Returns:
            FileAttachment instance.
        """
        timestamp = row["created_at"]
        if isinstance(timestamp, str):
            timestamp = datetime.fromisoformat(timestamp)

        return FileAttachment(
            id=row["id"],
            chat_id=row["chat_id"],
            user_id=row["user_id"],
            file_id=row["file_id"],
            file_unique_id=row["file_unique_id"],
            file_name=row["file_name"],
            file_type=row["file_type"],
            file_size=row["file_size"],
            file_path=row["file_path"],
            caption=self._get_row_value(row, "caption"),
            created_at=timestamp,
        )

    async def create(
        self,
        chat_id: int,
        user_id: int,
        file_id: str,
        file_unique_id: str,
        file_name: str,
        file_type: str,
        file_size: int,
        file_path: str,
        caption: Optional[str] = None,
    ) -> FileAttachment:
        """Create a new file attachment record.

        Args:
            chat_id: Chat ID.
            user_id: User ID.
            file_id: Telegram file_id.
            file_unique_id: Telegram file_unique_id.
            file_name: Original file name.
            file_type: MIME type.
            file_size: File size in bytes.
            file_path: Local storage path.
            caption: Optional user caption.

        Returns:
            Created FileAttachment instance.
        """
        cursor = await self.execute_query(
            f"""INSERT INTO {self.table_name} 
                (chat_id, user_id, file_id, file_unique_id, file_name, file_type, file_size, file_path, caption) 
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
            (chat_id, user_id, file_id, file_unique_id, file_name, file_type, file_size, file_path, caption),
        )
        return FileAttachment(
            id=cursor.lastrowid,
            chat_id=chat_id,
            user_id=user_id,
            file_id=file_id,
            file_unique_id=file_unique_id,
            file_name=file_name,
            file_type=file_type,
            file_size=file_size,
            file_path=file_path,
            caption=caption,
            created_at=datetime.now(),
        )

    async def get_total_size(self) -> int:
        """Get total size of all stored files in bytes.

        Returns:
            Total file size in bytes.
        """
        row = await self.fetch_one(
            f"SELECT COALESCE(SUM(file_size), 0) as total FROM {self.table_name}"
        )
        return row["total"] if row else 0

    async def count_all(self) -> int:
        """Count total number of files.

        Returns:
            Total file count.
        """
        row = await self.fetch_one(
            f"SELECT COUNT(*) as count FROM {self.table_name}"
        )
        return row["count"] if row else 0

    async def get_oldest_files(self, limit: int = 10) -> List[FileAttachment]:
        """Get oldest files sorted by creation date.

        Args:
            limit: Number of files to retrieve.

        Returns:
            List of oldest FileAttachment instances.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} ORDER BY created_at ASC LIMIT ?",
            (limit,)
        )
        return [await self._row_to_model(row) for row in rows]
    
    async def get_oldest_file_date(self) -> Optional[datetime]:
        """Get the creation date of the oldest file.

        Returns:
            Datetime of oldest file or None.
        """
        row = await self.fetch_one(
            f"SELECT MIN(created_at) as oldest FROM {self.table_name}"
        )
        if row and row["oldest"]:
            oldest = row["oldest"]
            return datetime.fromisoformat(oldest) if isinstance(oldest, str) else oldest
        return None

    async def get_newest_file_date(self) -> Optional[datetime]:
        """Get the creation date of the newest file.

        Returns:
            Datetime of newest file or None.
        """
        row = await self.fetch_one(
            f"SELECT MAX(created_at) as newest FROM {self.table_name}"
        )
        if row and row["newest"]:
            newest = row["newest"]
            return datetime.fromisoformat(newest) if isinstance(newest, str) else newest
        return None

    async def delete_by_id(self, file_id: int) -> bool:
        """Delete a file attachment by ID.

        Args:
            file_id: File attachment ID.

        Returns:
            True if deleted, False if not found.
        """
        cursor = await self.execute_query(
            f"DELETE FROM {self.table_name} WHERE id = ?",
            (file_id,)
        )
        return cursor.rowcount > 0

    async def delete_older_than(self, days: int) -> int:
        """Delete files older than specified days.

        Args:
            days: Age threshold in days.

        Returns:
            Number of deleted files.
        """
        threshold_date = datetime.now() - timedelta(days=days)
        cursor = await self.execute_query(
            f"DELETE FROM {self.table_name} WHERE created_at < ?",
            (threshold_date.isoformat(),)
        )
        return cursor.rowcount

    async def delete_all(self) -> int:
        """Delete all file attachments.

        Returns:
            Number of deleted files.
        """
        cursor = await self.execute_query(f"DELETE FROM {self.table_name}")
        return cursor.rowcount

    async def get_all_file_paths(self) -> List[str]:
        """Get all file paths for cleanup purposes.

        Returns:
            List of file paths.
        """
        rows = await self.fetch_all(
            f"SELECT file_path FROM {self.table_name}"
        )
        return [row["file_path"] for row in rows]

    async def get_all_files(self) -> List[FileAttachment]:
        """Get all file attachments.

        Returns:
            List of all FileAttachment instances.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} ORDER BY created_at DESC"
        )
        return [await self._row_to_model(row) for row in rows]

    async def get_files_by_chat(self, chat_id: int, limit: int = 50) -> List[FileAttachment]:

        """Get files for a specific chat.

        Args:
            chat_id: Chat ID.
            limit: Maximum number of files.

        Returns:
            List of FileAttachment instances.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE chat_id = ? ORDER BY created_at DESC LIMIT ?",
            (chat_id, limit)
        )
        return [await self._row_to_model(row) for row in rows]
