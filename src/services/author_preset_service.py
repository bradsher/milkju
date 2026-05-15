"""Author preset service for managing NovelAI author presets."""

from __future__ import annotations

import logging
from typing import Optional, List

from src.repositories.author_preset_repository import AuthorPresetRepository
from src.models.author_preset import AuthorPreset

logger = logging.getLogger(__name__)


class AuthorPresetService:
    """Service for managing NovelAI author string presets.
    
    Provides business logic for creating, reading, updating, and deleting
    author presets with ownership-based access control.
    """

    def __init__(
        self,
        preset_repo: Optional[AuthorPresetRepository] = None,
    ):
        """Initialize author preset service.
        
        Args:
            preset_repo: Author preset repository instance.
        """
        self.preset_repo = preset_repo or AuthorPresetRepository()

    async def get_preset_by_name(self, name: str) -> Optional[AuthorPreset]:
        """Get a preset by its name/alias.
        
        Args:
            name: Preset name (case-insensitive).
            
        Returns:
            AuthorPreset if found, None otherwise.
        """
        return await self.preset_repo.find_by_name(name)

    async def get_all_presets(self) -> List[AuthorPreset]:
        """Get all presets.
        
        Returns:
            List of all presets.
        """
        return await self.preset_repo.find_all()

    async def get_active_presets(self) -> List[AuthorPreset]:
        """Get all active presets.
        
        Returns:
            List of active presets.
        """
        return await self.preset_repo.find_active()

    async def get_presets_by_creator(self, user_id: int) -> List[AuthorPreset]:
        """Get all presets created by a specific user.
        
        Args:
            user_id: Creator's user ID.
            
        Returns:
            List of presets created by the user.
        """
        return await self.preset_repo.find_by_creator(user_id)

    async def get_preset_by_id(self, preset_id: int) -> Optional[AuthorPreset]:
        """Get a preset by its ID.
        
        Args:
            preset_id: Preset ID.
            
        Returns:
            AuthorPreset if found, None otherwise.
        """
        return await self.preset_repo.find_by_id(preset_id)

    async def create_preset(
        self, name: str, content: str, created_by: int
    ) -> AuthorPreset:
        """Create a new author preset.
        
        Args:
            name: Preset name/alias (no spaces allowed).
            content: Actual author string.
            created_by: Creator's user ID.
            
        Returns:
            Created AuthorPreset instance.
            
        Raises:
            ValueError: If name contains spaces or is invalid.
            DuplicateEntityError: If preset with name already exists.
        """
        # Validate name format
        name = name.strip()
        if not name:
            raise ValueError("Preset name cannot be empty")
        if ' ' in name:
            raise ValueError("Preset name cannot contain spaces")
        if len(name) > 50:
            raise ValueError("Preset name too long (max 50 characters)")
        
        # Validate content
        content = content.strip()
        if not content:
            raise ValueError("Preset content cannot be empty")
        if len(content) > 2000:
            raise ValueError("Preset content too long (max 2000 characters)")
        
        logger.info(f"Creating author preset '{name}' for user {created_by}")
        return await self.preset_repo.create(name, content, created_by)

    async def update_preset(
        self,
        preset_id: int,
        user_id: int,
        is_super_admin: bool = False,
        name: Optional[str] = None,
        content: Optional[str] = None,
    ) -> bool:
        """Update a preset (only owner or super admin can update).
        
        Args:
            preset_id: Preset ID.
            user_id: User attempting the update.
            is_super_admin: Whether the user is a super admin.
            name: New name (optional).
            content: New content (optional).
            
        Returns:
            True if updated, False otherwise.
            
        Raises:
            PermissionError: If user cannot manage this preset.
        """
        preset = await self.preset_repo.find_by_id(preset_id)
        if not preset:
            return False
        
        if not self.can_manage_preset(preset, user_id, is_super_admin):
            raise PermissionError("You can only update your own presets")
        
        return await self.preset_repo.update(preset_id, name, content)

    async def toggle_preset(
        self, preset_id: int, user_id: int, is_super_admin: bool = False
    ) -> Optional[bool]:
        """Toggle preset active status.
        
        Args:
            preset_id: Preset ID.
            user_id: User attempting the toggle.
            is_super_admin: Whether the user is a super admin.
            
        Returns:
            New active status, or None if preset not found.
            
        Raises:
            PermissionError: If user cannot manage this preset.
        """
        preset = await self.preset_repo.find_by_id(preset_id)
        if not preset:
            return None
        
        if not self.can_manage_preset(preset, user_id, is_super_admin):
            raise PermissionError("You can only toggle your own presets")
        
        new_status = not preset.is_active
        await self.preset_repo.update_active_status(preset_id, new_status)
        return new_status

    async def delete_preset(
        self, preset_id: int, user_id: int, is_super_admin: bool = False
    ) -> bool:
        """Delete a preset (only owner or super admin can delete).
        
        Args:
            preset_id: Preset ID.
            user_id: User attempting the deletion.
            is_super_admin: Whether the user is a super admin.
            
        Returns:
            True if deleted, False if not found.
            
        Raises:
            PermissionError: If user cannot manage this preset.
        """
        preset = await self.preset_repo.find_by_id(preset_id)
        if not preset:
            return False
        
        if not self.can_manage_preset(preset, user_id, is_super_admin):
            raise PermissionError("You can only delete your own presets")
        
        logger.info(f"Deleting author preset '{preset.name}' by user {user_id}")
        return await self.preset_repo.delete(preset_id)

    def can_view_content(
        self, preset: AuthorPreset, user_id: int, is_super_admin: bool = False
    ) -> bool:
        """Check if user can view the actual preset content.
        
        Only the creator or super admin can see the actual content.
        
        Args:
            preset: The preset to check.
            user_id: User ID.
            is_super_admin: Whether the user is a super admin.
            
        Returns:
            True if user can view content, False otherwise.
        """
        return preset.created_by == user_id or is_super_admin

    def can_manage_preset(
        self, preset: AuthorPreset, user_id: int, is_super_admin: bool = False
    ) -> bool:
        """Check if user can edit/delete this preset.
        
        Only the creator or super admin can manage a preset.
        
        Args:
            preset: The preset to check.
            user_id: User ID.
            is_super_admin: Whether the user is a super admin.
            
        Returns:
            True if user can manage preset, False otherwise.
        """
        return preset.created_by == user_id or is_super_admin

    def get_display_content(
        self, preset: AuthorPreset, user_id: int, is_super_admin: bool = False
    ) -> str:
        """Get content for display (full or masked based on permissions).
        
        Args:
            preset: The preset.
            user_id: User ID.
            is_super_admin: Whether the user is a super admin.
            
        Returns:
            Full content if user can view, masked content otherwise.
        """
        if self.can_view_content(preset, user_id, is_super_admin):
            return preset.content
        return preset.masked_content
