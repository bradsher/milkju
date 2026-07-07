"""Service for managing global system configuration."""

from __future__ import annotations

from typing import Optional

from src.repositories.config_repository import ConfigRepository
from src.core.constants import Defaults


class ConfigService:
    """Service for managing global system configuration."""

    # Default configuration values
    DEFAULTS = {
        "history_limit": "20",
        "group_history_limit": "20",
        "max_tokens": "",
        "summary_language": "Simplified Chinese",
        "summary_permission_required": "true",  # "true" = Admin only, "false" = Everyone
        "strategy": "single",  # "single" or "round_robin"
        "model": Defaults.DEFAULT_MODEL,
        "active_provider_id": None,
        "polling_provider_ids": None,
        "polling_config_json": "[]",  # Store as list of dicts: [{"provider_id": 1, "model": "gpt-4"}]
        "file_max_size_mb": "20",  # Max file upload size in MB

        "file_retention_days": "30",  # File retention period in days
        "auto_cleanup_enabled": "false",  # Auto cleanup messages
        "auto_cleanup_days": "30",  # Number of days to keep messages
        "auto_cleanup_last_run": "",  # Last run date (YYYY-MM-DD)
        "concurrent_updates": "false",  # Enable concurrent update processing
        "public_chat_enabled": "false", # Allow non-admins to use private chat
        "public_chat_rate_limit": "20", # Rate limit per hour for normal users
        "search_model": "",  # Default model for /s command (empty = use global default)
        "search_provider_id": "",  # Default provider for /s command
        "summary_default_model": "",  # Default model for /summary and auto-summary (empty = use global default)
        "summary_default_provider_id": "",  # Default provider for /summary and auto-summary
    }


    def __init__(self, config_repo: Optional[ConfigRepository] = None):
        """Initialize config service.

        Args:
            config_repo: Config repository.
        """
        self.repo = config_repo or ConfigRepository()

    async def get(self, key: str, default: Optional[str] = None) -> Optional[str]:
        """Get a config value.

        Args:
            key: Configuration key.
            default: Default value if not found.

        Returns:
            Config value or default.
        """
        value = await self.repo.get(key)
        if value is not None:
            return value
        if default is not None:
            return default
        return self.DEFAULTS.get(key)

    async def set(self, key: str, value: Optional[str]) -> None:
        """Set a config value.

        Args:
            key: Configuration key.
            value: Configuration value.
        """
        await self.repo.set(key, value)

    async def get_all(self) -> dict[str, str]:
        """Get all configuration values with defaults.

        Returns:
            Dictionary of all config values.
        """
        stored = await self.repo.get_all()
        result = {**self.DEFAULTS}
        result.update(stored)
        return result

    # Specific configuration getters

    async def get_history_limit(self) -> int:
        """Get private chat history limit.

        Returns:
            Number of messages to keep in history.
        """
        value = await self.get("history_limit")
        try:
            return int(value) if value else 20
        except (ValueError, TypeError):
            return 20

    async def get_group_history_limit(self) -> int:
        """Get group chat history limit.

        Returns:
            Number of messages to keep in group history.
        """
        value = await self.get("group_history_limit")
        try:
            return int(value) if value else 20
        except (ValueError, TypeError):
            return 20

    async def get_public_chat_enabled(self) -> bool:
        """Check if public private chat is enabled.

        Returns:
            True if enabled, False otherwise.
        """
        value = await self.get("public_chat_enabled")
        return value.lower() == "true" if value else False

    async def set_public_chat_enabled(self, enabled: bool) -> None:
        """Set public private chat state.

        Args:
            enabled: True to enable, False to disable.
        """
        await self.set("public_chat_enabled", "true" if enabled else "false")

    async def get_public_chat_rate_limit(self) -> int:
        """Get rate limit for normal users in public chat.

        Returns:
            Number of messages allowed per hour.
        """
        value = await self.get("public_chat_rate_limit")
        try:
            return int(value) if value else 20
        except (ValueError, TypeError):
            return 20

    async def set_public_chat_rate_limit(self, limit: int) -> None:
        """Set rate limit for normal users.

        Args:
            limit: Number of messages allowed per hour.
        """
        await self.set("public_chat_rate_limit", str(limit))

    async def get_max_tokens(self) -> Optional[int]:
        """Get max tokens limit.

        Returns:
            Max tokens or None for unlimited.
        """
        value = await self.get("max_tokens")
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def get_summary_language(self) -> str:
        """Get default summary language.

        Returns:
            Language name.
        """
        value = await self.get("summary_language")
        return value or "Simplified Chinese"

    async def is_summary_permission_required(self) -> bool:
        """Check if summary requires admin permission.

        Returns:
            True if restricted to admins, False if everyone can use.
        """
        value = await self.get("summary_permission_required")
        return value != "false"

    async def get_strategy(self) -> str:
        """Get AI provider strategy.

        Returns:
            "single" or "round_robin".
        """
        value = await self.get("strategy")
        return value or "single"

    async def get_model(self) -> str:
        """Get default model name.

        Returns:
            Model name.
        """
        value = await self.get("model")
        return value or Defaults.DEFAULT_MODEL

    async def get_active_provider_id(self) -> Optional[int]:
        """Get active provider ID (for single strategy).

        Returns:
            Provider ID or None.
        """
        value = await self.get("active_provider_id")
        if not value:
            return None
        try:
            return int(value)
        except ValueError:
            return None

    async def get_polling_provider_ids(self) -> list[int]:
        """Get polling provider IDs (for round-robin strategy).

        Returns:
            List of provider IDs.
        """
        value = await self.get("polling_provider_ids")
        if not value:
            return []
        try:
            return [int(p_id) for p_id in value.split(",") if p_id.strip()]
        except ValueError:
            return []

    # Specific configuration setters

    async def set_history_limit(self, limit: int) -> None:
        """Set private chat history limit.

        Args:
            limit: Number of messages.
        """
        await self.set("history_limit", str(limit))

    async def set_group_history_limit(self, limit: int) -> None:
        """Set group chat history limit.

        Args:
            limit: Number of messages.
        """
        await self.set("group_history_limit", str(limit))

    async def set_max_tokens(self, tokens: Optional[int]) -> None:
        """Set max tokens limit.

        Args:
            tokens: Max tokens or None for unlimited.
        """
        await self.set("max_tokens", str(tokens) if tokens else "")

    async def set_summary_language(self, language: str) -> None:
        """Set default summary language.

        Args:
            language: Language name.
        """
        await self.set("summary_language", language)

    async def set_summary_permission_required(self, required: bool) -> None:
        """Set summary permission requirement.

        Args:
            required: True for admin only, False for everyone.
        """
        await self.set("summary_permission_required", "true" if required else "false")

    async def set_strategy(self, strategy: str) -> None:
        """Set AI provider strategy.

        Args:
            strategy: "single" or "round_robin".
        """
        await self.set("strategy", strategy)

    async def set_model(self, model: str) -> None:
        """Set default model name.

        Args:
            model: Model name.
        """
        await self.set("model", model)

    async def set_active_provider_id(self, provider_id: Optional[int]) -> None:
        """Set active provider ID (for single strategy).

        Args:
            provider_id: Provider ID or None.
        """
        await self.set("active_provider_id", str(provider_id) if provider_id else None)

    async def set_polling_provider_ids(self, provider_ids: list[int]) -> None:
        """Set polling provider IDs (for round-robin strategy).

        Args:
            provider_ids: List of provider IDs.
        """
        if provider_ids:
            await self.set("polling_provider_ids", ",".join(str(p_id) for p_id in provider_ids))
        else:
            await self.set("polling_provider_ids", None)

    async def get_polling_config(self) -> list[dict]:
        """Get complex polling configuration (pairs of provider_id and model).

        Returns:
            List of dicts: [{"provider_id": int, "model": str}]
        """
        import json
        value = await self.get("polling_config_json")
        if not value:
            return []
        try:
            return json.loads(value)
        except (ValueError, json.JSONDecodeError):
            return []

    async def set_polling_config(self, config: list[dict]) -> None:
        """Set complex polling configuration.

        Args:
            config: List of dicts: [{"provider_id": int, "model": str}]
        """
        import json
        await self.set("polling_config_json", json.dumps(config))

    async def get_fallback_rules(self) -> dict:
        """Get fallback rules configuration.
        
        Returns:
            Dictionary of fallback rules.
            Format: {'audio': {'model': 'gemini-3-flash-preview', 'provider_id': 1}, ...}
        """
        import json
        value = await self.get("fallback_rules")
        if not value:
            return {}
        try:
            return json.loads(value)
        except json.JSONDecodeError:
            return {}

    async def set_fallback_rule(self, media_type: str, model: str, provider_id: int) -> None:
        """Set a fallback rule for a media type.
        
        Args:
            media_type: 'audio', 'video', 'image', 'document', etc.
            model: Target model name.
            provider_id: Target provider ID.
        """
        import json
        rules = await self.get_fallback_rules()
        rules[media_type] = {"model": model, "provider_id": int(provider_id)}
        await self.set("fallback_rules", json.dumps(rules))

    async def clear_fallback_rule(self, media_type: str) -> None:
        """Clear a fallback rule.
        
        Args:
            media_type: Media type to clear.
        """
        import json
        rules = await self.get_fallback_rules()
        if media_type in rules:
            del rules[media_type]
            await self.set("fallback_rules", json.dumps(rules))
            
    # System Overrides
    
    async def get_system_override(self, key: str, default: any = None) -> any:
        """Get a system override value (e.g. timeout, file size)."""
        value = await self.get(f"sys_{key}")
        if value is None:
            return default
        # Try to convert to int/float if compatible
        if str(value).isdigit():
            return int(value)
        try:
            return float(value)
        except ValueError:
            return value
            
    async def set_system_override(self, key: str, value: any) -> None:
        """Set a system override value."""
        await self.set(f"sys_{key}", str(value))

    # Message Auto-Cleanup Configuration

    async def get_auto_cleanup_enabled(self) -> bool:
        """Get auto cleanup enabled status.
        
        Returns:
            True if auto cleanup is enabled, False otherwise.
        """
        value = await self.get("auto_cleanup_enabled")
        return value == "true"

    async def set_auto_cleanup_enabled(self, enabled: bool) -> None:
        """Set auto cleanup enabled status.
        
        Args:
            enabled: True to enable, False to disable.
        """
        await self.set("auto_cleanup_enabled", "true" if enabled else "false")

    async def get_auto_cleanup_days(self) -> int:
        """Get number of days to keep messages before cleanup.
        
        Returns:
            Number of days (default: 30).
        """
        value = await self.get("auto_cleanup_days")
        try:
            return int(value) if value else 30
        except (ValueError, TypeError):
            return 30

    async def set_auto_cleanup_days(self, days: int) -> None:
        """Set number of days to keep messages before cleanup.
        
        Args:
            days: Number of days.
        """
        await self.set("auto_cleanup_days", str(days))

    async def get_auto_cleanup_last_run(self) -> Optional[str]:
        """Get last auto cleanup run date.
        
        Returns:
            Date string in YYYY-MM-DD format or None.
        """
        return await self.get("auto_cleanup_last_run")

    async def set_auto_cleanup_last_run(self, date: str) -> None:
        """Set last auto cleanup run date.

        Args:
            date: Date string in YYYY-MM-DD format.
        """
        await self.set("auto_cleanup_last_run", date)

    # Concurrent Updates Configuration

    async def get_concurrent_updates(self) -> bool:
        """Get whether concurrent update processing is enabled.

        Returns:
            True if concurrent updates is enabled, False otherwise.
        """
        value = await self.get("concurrent_updates")
        return value == "true"

    async def set_concurrent_updates(self, enabled: bool) -> None:
        """Set concurrent update processing.

        Args:
            enabled: True to enable, False to disable.
        """
        await self.set("concurrent_updates", "true" if enabled else "false")

    # Search Model Configuration

    async def get_search_model(self) -> tuple[Optional[str], Optional[int]]:
        """Get default model and provider for /s (search) command.

        Returns:
            Tuple of (model_name, provider_id). Both None if not configured.
        """
        model = await self.get("search_model")
        provider_id = await self.get("search_provider_id")
        if not model:
            return None, None
        try:
            return model, int(provider_id) if provider_id else None
        except (ValueError, TypeError):
            return model, None

    async def set_search_model(self, model: Optional[str], provider_id: Optional[int]) -> None:
        """Set default model and provider for /s (search) command.

        Args:
            model: Model name (None to clear).
            provider_id: Provider ID (None to clear).
        """
        await self.set("search_model", model or "")
        await self.set("search_provider_id", str(provider_id) if provider_id else "")

    # Summary Model Configuration

    async def get_summary_default_model(self) -> tuple[Optional[str], Optional[int]]:
        """Get default model and provider for /summary and auto-summary.

        Returns:
            Tuple of (model_name, provider_id). Both None if not configured.
        """
        model = await self.get("summary_default_model")
        provider_id = await self.get("summary_default_provider_id")
        if not model:
            return None, None
        try:
            return model, int(provider_id) if provider_id else None
        except (ValueError, TypeError):
            return model, None

    async def set_summary_default_model(self, model: Optional[str], provider_id: Optional[int]) -> None:
        """Set default model and provider for /summary and auto-summary.

        Args:
            model: Model name (None to clear).
            provider_id: Provider ID (None to clear).
        """
        await self.set("summary_default_model", model or "")
        await self.set("summary_default_provider_id", str(provider_id) if provider_id else "")

    # Recommend Model Configuration

    async def get_recommend_model(self) -> tuple[Optional[str], Optional[int]]:
        """Get default model and provider for /recommend command.

        Returns:
            Tuple of (model_name, provider_id). Both None if not configured.
        """
        model = await self.get("recommend_model")
        provider_id = await self.get("recommend_provider_id")
        if not model:
            return None, None
        try:
            return model, int(provider_id) if provider_id else None
        except (ValueError, TypeError):
            return model, None

    async def set_recommend_model(self, model: Optional[str], provider_id: Optional[int]) -> None:
        """Set default model and provider for /recommend command.

        Args:
            model: Model name (None to clear).
            provider_id: Provider ID (None to clear).
        """
        await self.set("recommend_model", model or "")
        await self.set("recommend_provider_id", str(provider_id) if provider_id else "")
