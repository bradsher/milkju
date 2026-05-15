"""File attachment model."""

from __future__ import annotations

from dataclasses import dataclass
from datetime import datetime
from typing import Optional


@dataclass
class FileAttachment:
    """Represents a file uploaded to the bot."""

    id: Optional[int]
    chat_id: int
    user_id: int
    file_id: str
    file_unique_id: str
    file_name: str
    file_type: str
    file_size: int
    file_path: str
    caption: Optional[str]
    created_at: Optional[datetime]

    @classmethod
    def from_row(cls, row: tuple) -> FileAttachment:
        """Create FileAttachment from database row.

        Args:
            row: Tuple from database query.

        Returns:
            FileAttachment instance.
        """
        return cls(
            id=row[0],
            chat_id=row[1],
            user_id=row[2],
            file_id=row[3],
            file_unique_id=row[4],
            file_name=row[5],
            file_type=row[6],
            file_size=row[7],
            file_path=row[8],
            caption=row[9] if len(row) > 9 else None,
            created_at=datetime.fromisoformat(row[10]) if len(row) > 10 and row[10] else None,
        )
