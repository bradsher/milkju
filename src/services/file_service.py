"""File processing service for handling file uploads and storage management."""

from __future__ import annotations

from typing import Optional, Tuple
from pathlib import Path
from datetime import datetime
import logging
import os
import asyncio
import magic  # python-magic

from telegram import Bot

from src.repositories.file_repository import FileRepository
from src.core.constants import Defaults
from src.services.permission_service import PermissionService
from src.core.infrastructure import ProviderService
from src.ai.factory import AIClientFactory
from src.models.file_attachment import FileAttachment
from src.core.exceptions import NoActiveProviderError, NoActiveAPIKeyError

logger = logging.getLogger(__name__)

# Hard-coded security constraints
MAX_FILE_SIZE = 50 * 1024 * 1024  # 50 MB

# Gemini 2.0 Flash supported file types
ALLOWED_MIME_TYPES = {
    # Documents
    'application/pdf',
    'text/plain',           # .txt files
    'application/json',     # .json files
    # Script files
    'text/x-python',        # .py files
    'text/x-sh',            # .sh files
    'text/x-shellscript',   # shell scripts
    'text/x-msdos-batch',   # .bat files
    'text/x-powershell',    # .ps1 files
    'application/x-sh',     # alternative for shell scripts
    # Code files
    'text/html',            # .html files
    'text/css',             # .css files
    'text/javascript',      # .js files
    'application/javascript', # alternative for .js
    'text/xml',             # .xml files
    'text/csv',             # .csv files
    'text/markdown',        # .md files
    # Images
    'image/png', 'image/jpeg', 'image/webp', 'image/heic', 'image/heif',
    # Audio
    'audio/aac', 'audio/flac', 'audio/mp3', 'audio/m4a', 'audio/mpeg',
    'audio/mp4', 'audio/ogg', 'audio/opus', 'audio/pcm', 'audio/wav', 'audio/webm',
    # Video
    'video/3gpp', 'video/x-flv', 'video/quicktime', 'video/mpeg',
    'video/mp4', 'video/webm', 'video/wmv'
}


class FileService:
    """Service for file processing and storage management."""

    def __init__(
        self,
        file_repo: Optional[FileRepository] = None,
        permission_service: Optional[PermissionService] = None,
        provider_service: Optional[ProviderService] = None,
    ):
        """Initialize file service.

        Args:
            file_repo: File repository.
            permission_service: Permission service.
            provider_service: Provider service.
        """
        self.file_repo = file_repo or FileRepository()
        self.permission_service = permission_service or PermissionService()
        self.provider_service = provider_service or ProviderService()
        
        # Ensure storage directory exists
        self._storage_dir = Path("file_storage")
        self._storage_dir.mkdir(exist_ok=True)

    def _get_file_path(self, file_unique_id: str, file_name: str) -> Path:
        """Generate storage path for a file.

        Args:
            file_unique_id: Telegram's unique file ID.
            file_name: Original file name.

        Returns:
            Path to store the file.
        """
        # Use unique_id as prefix to avoid collisions
        safe_name = f"{file_unique_id}_{file_name}"
        return self._storage_dir / safe_name

    def _validate_file_type(self, file_path: Path) -> Tuple[bool, str, str]:
        """Validate file type against whitelist.

        Args:
            file_path: Path to the file.

        Returns:
            Tuple of (is_valid, mime_type, error_message).
        """
        try:
            mime = magic.Magic(mime=True)
            mime_type = mime.from_file(str(file_path))
            
            if mime_type not in ALLOWED_MIME_TYPES:
                return False, mime_type, f"Unsupported file type: {mime_type}"
            
            return True, mime_type, ""
        except Exception as e:
            logger.error(f"Error detecting file type: {e}")
            return False, "unknown", "Failed to detect file type"

    def _validate_file_size(self, file_size: int) -> Tuple[bool, str]:
        """Validate file size against hard limit.

        Args:
            file_size: File size in bytes.

        Returns:
            Tuple of (is_valid, error_message).
        """
        if file_size > MAX_FILE_SIZE:
            size_mb = file_size / (1024 * 1024)
            limit_mb = MAX_FILE_SIZE / (1024 * 1024)
            return False, f"File too large: {size_mb:.1f}MB (limit: {limit_mb}MB)"
        return True, ""

    async def check_storage_quota(self) -> Tuple[bool, str]:
        """Check if storage quota allows new uploads.

        Returns:
            Tuple of (can_upload, message).
        """
        from src.core.infrastructure import ConfigService
        config = ConfigService()
        quota_mb = int(await config.get("file_max_size_mb") or "20") * 10
        quota_bytes = quota_mb * 1024 * 1024
        
        total_size = await self.file_repo.get_total_size()
        
        if total_size >= quota_bytes:
            # Try auto-cleanup by quota
            await self.cleanup_by_quota()
            # Check again
            total_size = await self.file_repo.get_total_size()
            
            if total_size >= quota_bytes:
                used_mb = total_size / (1024 * 1024)
                return False, f"Storage quota exceeded: {used_mb:.1f}MB / {quota_mb}MB. Old files have been cleaned, but still at capacity."
        
        return True, ""

    async def process_file(
        self,
        bot: Bot,
        file_id: str,
        chat_id: int,
        user_id: int,
        file_name: str,
        file_unique_id: str,
        file_size: int,
        caption: str = ""
    ) -> Tuple[Path, FileAttachment]:
        """Process an uploaded file.

        Args:
            bot: Telegram bot instance.
            file_id: Telegram file_id.
            chat_id: Chat ID.
            user_id: User ID.
            file_name: Original file name.
            file_unique_id: Telegram file_unique_id.
            file_size: File size in bytes.
            caption: User's caption/question.

        Returns:
            Tuple of (result_message, file_record).

        Raises:
            Exception: If processing fails.
        """
        # Validate file size
        size_valid, size_error = self._validate_file_size(file_size)
        if not size_valid:
            raise ValueError(size_error)

        # Download file
        file_path = self._get_file_path(file_unique_id, file_name)
        telegram_file = await bot.get_file(file_id)
        await telegram_file.download_to_drive(str(file_path))
        
        logger.info(f"Downloaded file: {file_name} ({file_size} bytes)")

        try:
            # Validate file type
            type_valid, mime_type, type_error = self._validate_file_type(file_path)
            if not type_valid:
                # Clean up downloaded file
                file_path.unlink(missing_ok=True)
                raise ValueError(type_error)

            # Store file record in database
            file_record = await self.file_repo.create(
                chat_id=chat_id,
                user_id=user_id,
                file_id=file_id,
                file_unique_id=file_unique_id,
                file_name=file_name,
                file_type=mime_type,
                file_size=file_size,
                file_path=str(file_path),
                caption=caption,
            )

            logger.info(f"File record created: ID={file_record.id}")

            return file_path, file_record

        except Exception as e:
            # Clean up on error
            file_path.unlink(missing_ok=True)
            raise

    async def get_storage_stats(self) -> dict:
        """
        Get storage statistics.
        
        Returns:
            Dictionary with storage stats
        """
        files = await self.file_repo.get_all_files()
        total_files = len(files)
        total_size = sum(f.file_size for f in files)
        total_size_mb = total_size / (1024 * 1024)
        
        # Get quota from ConfigService instead
        from src.core.infrastructure import ConfigService
        config = ConfigService()
        quota_mb = int(await config.get("file_max_size_mb") or "20") * 10  # Approximate total quota
        
        usage_percent = (total_size_mb / quota_mb * 100) if quota_mb > 0 else 0
        
        oldest_file_date = "N/A"
        newest_file_date = "N/A"
        
        if files:
            oldest_file = min(files, key=lambda f: f.created_at)
            newest_file = max(files, key=lambda f: f.created_at)
            oldest_file_date = oldest_file.created_at.strftime("%Y-%m-%d")
            newest_file_date = newest_file.created_at.strftime("%Y-%m-%d")
        
        return {
            "total_files": total_files,
            "total_size_mb": total_size_mb,
            "quota_mb": quota_mb,
            "usage_percent": usage_percent,
            "oldest_file_date": oldest_file_date,
            "newest_file_date": newest_file_date
        }

    async def cleanup_old_files(self, days: Optional[int] = None) -> int:
        """Clean up files older than specified days.

        Args:
            days: Age threshold. If None, uses config value.

        Returns:
            Number of files deleted.
        """
        if days is None:
            from src.core.infrastructure import ConfigService
            config = ConfigService()
            days = int(await config.get("file_retention_days") or "30")

        # Get files to delete
        # For simplicity, delete from database first
        deleted_count = await self.file_repo.delete_older_than(days)
        
        # Clean up orphaned files from disk
        await self._cleanup_orphaned_files()
        
        logger.info(f"Cleaned up {deleted_count} files older than {days} days")
        return deleted_count

    async def cleanup_by_quota(self) -> int:
        """Delete oldest files until under quota.

        Returns:
            Number of files deleted.
        """
        from src.core.infrastructure import ConfigService
        config = ConfigService()
        quota_mb = int(await config.get("file_max_size_mb") or "20") * 10
        quota_bytes = quota_mb * 1024 * 1024
        
        deleted_count = 0
        while True:
            total_size = await self.file_repo.get_total_size()
            if total_size < quota_bytes:
                break
            
            # Delete oldest file
            oldest_files = await self.file_repo.get_oldest_files(limit=1)
            if not oldest_files:
                break
            
            oldest = oldest_files[0]
            await self.delete_file(oldest.id)
            deleted_count += 1
            
            # Safety limit
            if deleted_count >= 100:
                logger.warning("Deleted 100 files, stopping quota cleanup")
                break

        logger.info(f"Quota cleanup: deleted {deleted_count} files")
        return deleted_count

    async def delete_file(self, file_id: int) -> bool:
        """Delete a single file.

        Args:
            file_id: File attachment ID.

        Returns:
            True if deleted.
        """
        # Get file info first
        files = await self.file_repo.get_oldest_files(limit=1000)
        target_file = next((f for f in files if f.id == file_id), None)
        
        if target_file:
            # Delete from disk
            file_path = Path(target_file.file_path)
            file_path.unlink(missing_ok=True)
        
        # Delete from database
        return await self.file_repo.delete_by_id(file_id)

    async def delete_all_files(self) -> int:
        """Delete all files.

        Returns:
            Number of files deleted.
        """
        # Get all file paths
        file_paths = await self.file_repo.get_all_file_paths()
        
        # Delete from database
        deleted_count = await self.file_repo.delete_all()
        
        # Delete from disk
        for path_str in file_paths:
            Path(path_str).unlink(missing_ok=True)
        
        logger.info(f"Deleted all {deleted_count} files")
        return deleted_count

    async def _cleanup_orphaned_files(self) -> None:
        """Clean up files on disk that are not in database."""
        if not self._storage_dir.exists():
            return
        
        # Get all file paths from database
        db_paths = set(await self.file_repo.get_all_file_paths())
        
        # Check all files in storage directory
        for file_path in self._storage_dir.iterdir():
            if file_path.is_file() and str(file_path) not in db_paths:
                file_path.unlink(missing_ok=True)
                logger.info(f"Deleted orphaned file: {file_path.name}")
