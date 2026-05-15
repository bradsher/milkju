"""Provider service for managing AI providers and API keys."""

from __future__ import annotations

from typing import Optional, List, Tuple
import random

from src.repositories.provider_repository import (
    ProviderRepository,
    APIKeyRepository,
    ProviderModelRepository,
)
from src.models.provider import Provider, APIKey, ProviderModel
from src.core.exceptions import (
    ProviderNotFoundError,
    NoActiveProviderError,
    NoActiveAPIKeyError,
)


class ProviderService:
    """Service for managing AI providers, API keys, and models."""

    def __init__(
        self,
        provider_repo: Optional[ProviderRepository] = None,
        api_key_repo: Optional[APIKeyRepository] = None,
        model_repo: Optional[ProviderModelRepository] = None,
    ):
        """Initialize provider service.

        Args:
            provider_repo: Provider repository.
            api_key_repo: API key repository.
            model_repo: Provider model repository.
        """
        self.provider_repo = provider_repo or ProviderRepository()
        self.api_key_repo = api_key_repo or APIKeyRepository()
        self.model_repo = model_repo or ProviderModelRepository()

    # Provider management

    async def get_provider(self, provider_id: int) -> Optional[Provider]:
        """Get provider by ID.

        Args:
            provider_id: Provider ID.

        Returns:
            Provider instance if found, None otherwise.
        """
        return await self.provider_repo.find_by_id(provider_id)

    async def get_provider_by_name(self, name: str) -> Optional[Provider]:
        """Get provider by name.

        Args:
            name: Provider name.

        Returns:
            Provider instance if found, None otherwise.
        """
        return await self.provider_repo.find_by_name(name)

    async def get_all_providers(self) -> List[Provider]:
        """Get all providers.

        Returns:
            List of all providers.
        """
        return await self.provider_repo.find_all()

    async def get_active_providers(self) -> List[Provider]:
        """Get all active providers.

        Returns:
            List of active providers.
        """
        return await self.provider_repo.find_active()

    async def create_provider(
        self, name: str, base_url: str, client_type: str = "openai"
    ) -> Provider:
        """Create a new provider.

        Args:
            name: Provider name.
            base_url: Provider base URL.
            client_type: Client type (openai or google).

        Returns:
            Created provider instance.

        Raises:
            DuplicateEntityError: If provider already exists.
        """
        return await self.provider_repo.create(name, base_url, client_type)

    async def set_provider_active(self, provider_id: int, is_active: bool) -> bool:
        """Set provider active status.

        Args:
            provider_id: Provider ID.
            is_active: Active status.

        Returns:
            True if updated, False if not found.
        """
        return await self.provider_repo.update_active_status(provider_id, is_active)

    # API Key management

    async def get_api_keys(self, provider_id: int) -> List[APIKey]:
        """Get all API keys for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            List of API keys.
        """
        return await self.api_key_repo.find_by_provider(provider_id)

    async def get_active_api_keys(self, provider_id: int) -> List[APIKey]:
        """Get active API keys for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            List of active API keys.
        """
        return await self.api_key_repo.find_active_by_provider(provider_id)

    async def create_api_key(self, provider_id: int, key: str) -> APIKey:
        """Create a new API key.

        Args:
            provider_id: Provider ID.
            key: API key value.

        Returns:
            Created API key instance.
        """
        return await self.api_key_repo.create(provider_id, key)

    async def get_random_active_api_key(self, provider_id: int) -> Optional[APIKey]:
        """Get a random active API key for load balancing.

        Args:
            provider_id: Provider ID.

        Returns:
            Random active API key, or None if no active keys.
        """
        keys = await self.get_active_api_keys(provider_id)
        if not keys:
            return None
        return random.choice(keys)

    # Model management

    async def get_models_for_provider(self, provider_id: int) -> List[ProviderModel]:
        """Get all models for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            List of provider models.
        """
        return await self.model_repo.find_by_provider(provider_id)

    async def get_all_unique_models(self) -> List[str]:
        """Get all unique model names.

        Returns:
            List of unique model names.
        """
        return await self.model_repo.find_unique_models()

    async def delete_provider(self, provider_id: int) -> bool:
        """Delete a provider and all its models.
        
        Args:
            provider_id: Provider ID to delete.
            
        Returns:
            True if deleted successfully.
        """
        # Delete all models first
        models = await self.get_models_for_provider(provider_id)
        for model in models:
            await self.model_repo.delete(model.id)
        
        # Delete provider
        return await self.provider_repo.delete(provider_id)
    
    async def update_provider_key(self, provider_id: int, api_key: str | None) -> None:
        """Update provider API key.
        
        Args:
            provider_id: Provider ID.
            api_key: New API key or None to remove.
        """
        # This is a simple implementation - store in provider metadata
        # In production, you'd want to use the APIKey model
        pass  # TODO: Implement proper API key storage
    
    async def create_model(
        self, provider_id: int, model: str
    ) -> Optional[ProviderModel]:
        """Create a new provider model.

        Args:
            provider_id: Provider ID.
            model: Model name.

        Returns:
            Created model instance, or None if already exists.
        """
        return await self.model_repo.create(provider_id, model)

    async def find_provider_for_model(self, model: str) -> List[Provider]:
        """Find all active providers supporting a model.

        Args:
            model: Model name.

        Returns:
            List of providers supporting the model.
        """
        return await self.provider_repo.find_by_model(model)

    # High-level configuration retrieval

    async def get_active_config(
        self, model: str, provider_id: Optional[int] = None
    ) -> Tuple[Optional[str], Optional[str], Optional[str]]:
        """Get active configuration (base_url, api_key, client_type) for a model.

        This method implements the load balancing strategy:
        1. If provider_id is specified, use that provider
        2. Otherwise, find all providers supporting the model
        3. Select a random active provider
        4. Select a random active API key from that provider

        Args:
            model: Model name.
            provider_id: Optional specific provider ID.

        Returns:
            Tuple of (base_url, api_key, client_type) or (None, None, None) if not found.

        Raises:
            NoActiveProviderError: If no active provider found for model.
            NoActiveAPIKeyError: If no active API key found for provider.
        """
        # Determine which provider to use
        if provider_id:
            provider = await self.get_provider(provider_id)
            if not provider or not provider.is_active:
                raise NoActiveProviderError(
                    f"Provider {provider_id} not found or inactive"
                )
        else:
            # Find providers supporting this model
            providers = await self.find_provider_for_model(model)
            if not providers:
                raise NoActiveProviderError(f"No active provider found for model: {model}")

            # Random selection for load balancing
            provider = random.choice(providers)

        # Get a random active API key
        api_key_obj = await self.get_random_active_api_key(provider.id)
        if not api_key_obj:
            raise NoActiveAPIKeyError(
                f"No active API key found for provider: {provider.name}"
            )

        return provider.base_url, api_key_obj.key, provider.client_type

    async def validate_model_provider_combination(
        self, model: str, provider_id: int
    ) -> bool:
        """Check if a provider supports a specific model.

        Args:
            model: Model name.
            provider_id: Provider ID.

        Returns:
            True if provider supports model, False otherwise.
        """
        models = await self.get_models_for_provider(provider_id)
        return any(m.model == model for m in models)
