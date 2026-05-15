"""Provider repository for database operations."""

from __future__ import annotations

from typing import Optional, List
import aiosqlite

from src.repositories.base import BaseRepository
from src.models.provider import Provider, APIKey, ProviderModel
from src.core.exceptions import DuplicateEntityError


class ProviderRepository(BaseRepository[Provider]):
    """Repository for provider database operations."""

    @property
    def table_name(self) -> str:
        """Return the providers table name."""
        return "providers"

    async def _row_to_model(self, row: aiosqlite.Row) -> Provider:
        """Convert database row to Provider model.

        Args:
            row: Database row.

        Returns:
            Provider instance.
        """
        return Provider(
            id=row["id"],
            name=row["name"],
            base_url=row["base_url"],
            is_active=bool(row["is_active"]),
            client_type=row["client_type"],
        )

    async def find_by_name(self, name: str) -> Optional[Provider]:
        """Find provider by name.

        Args:
            name: Provider name.

        Returns:
            Provider instance if found, None otherwise.
        """
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE name = ?", (name,)
        )
        if row:
            return await self._row_to_model(row)
        return None

    async def find_active(self) -> List[Provider]:
        """Find all active providers.

        Returns:
            List of active providers.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE is_active = 1"
        )
        return [await self._row_to_model(row) for row in rows]

    async def create(
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
            DuplicateEntityError: If provider with name already exists.
        """
        existing = await self.find_by_name(name)
        if existing:
            raise DuplicateEntityError(f"Provider with name '{name}' already exists")

        cursor = await self.execute_query(
            f"INSERT INTO {self.table_name} (name, base_url, client_type) VALUES (?, ?, ?)",
            (name, base_url, client_type),
        )
        provider_id = cursor.lastrowid
        return Provider(
            id=provider_id,
            name=name,
            base_url=base_url,
            is_active=True,
            client_type=client_type,
        )

    async def update_active_status(self, provider_id: int, is_active: bool) -> bool:
        """Update provider active status.

        Args:
            provider_id: Provider ID.
            is_active: New active status.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET is_active = ? WHERE id = ?",
            (is_active, provider_id),
        )
        return cursor.rowcount > 0

    async def find_by_model(self, model: str) -> List[Provider]:
        """Find all active providers supporting a specific model.

        Args:
            model: Model name.

        Returns:
            List of providers supporting the model.
        """
        query = """
            SELECT p.* FROM providers p
            JOIN provider_models pm ON p.id = pm.provider_id
            WHERE p.is_active = 1 AND pm.model = ?
        """
        rows = await self.fetch_all(query, (model,))
        return [await self._row_to_model(row) for row in rows]

    async def delete(self, provider_id: int) -> bool:
        """Delete a provider by ID.

        Args:
            provider_id: Provider ID.

        Returns:
            True if deleted, False if not found.
        """
        return await self.delete_by_id(provider_id)


class APIKeyRepository(BaseRepository[APIKey]):
    """Repository for API key database operations."""

    @property
    def table_name(self) -> str:
        """Return the api_keys table name."""
        return "api_keys"

    async def _row_to_model(self, row: aiosqlite.Row) -> APIKey:
        """Convert database row to APIKey model.

        Args:
            row: Database row.

        Returns:
            APIKey instance.
        """
        return APIKey(
            id=row["id"],
            provider_id=row["provider_id"],
            key=row["key"],
            is_active=bool(row["is_active"]),
        )

    async def find_by_provider(self, provider_id: int) -> List[APIKey]:
        """Find all API keys for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            List of API keys.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE provider_id = ?", (provider_id,)
        )
        return [await self._row_to_model(row) for row in rows]

    async def find_active_by_provider(self, provider_id: int) -> List[APIKey]:
        """Find active API keys for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            List of active API keys.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE provider_id = ? AND is_active = 1",
            (provider_id,),
        )
        return [await self._row_to_model(row) for row in rows]

    async def create(self, provider_id: int, key: str) -> APIKey:
        """Create a new API key.

        Args:
            provider_id: Provider ID.
            key: API key value.

        Returns:
            Created API key instance.
        """
        cursor = await self.execute_query(
            f"INSERT INTO {self.table_name} (provider_id, key) VALUES (?, ?)",
            (provider_id, key),
        )
        return APIKey(id=cursor.lastrowid, provider_id=provider_id, key=key)

    async def delete(self, key_id: int) -> bool:
        """Delete an API key by ID.

        Args:
            key_id: API key ID.

        Returns:
            True if deleted, False if not found.
        """
        return await self.delete_by_id(key_id)

    async def update_active_status(self, key_id: int, is_active: bool) -> bool:
        """Update API key active status.

        Args:
            key_id: API key ID.
            is_active: New active status.

        Returns:
            True if updated, False if not found.
        """
        cursor = await self.execute_query(
            f"UPDATE {self.table_name} SET is_active = ? WHERE id = ?",
            (is_active, key_id),
        )
        return cursor.rowcount > 0


class ProviderModelRepository(BaseRepository[ProviderModel]):
    """Repository for provider model database operations."""

    @property
    def table_name(self) -> str:
        """Return the provider_models table name."""
        return "provider_models"

    async def _row_to_model(self, row: aiosqlite.Row) -> ProviderModel:
        """Convert database row to ProviderModel model.

        Args:
            row: Database row.

        Returns:
            ProviderModel instance.
        """
        return ProviderModel(
            id=row["id"], provider_id=row["provider_id"], model=row["model"]
        )

    async def find_by_provider(self, provider_id: int) -> List[ProviderModel]:
        """Find all models for a provider.

        Args:
            provider_id: Provider ID.

        Returns:
            List of provider models.
        """
        rows = await self.fetch_all(
            f"SELECT * FROM {self.table_name} WHERE provider_id = ?", (provider_id,)
        )
        return [await self._row_to_model(row) for row in rows]

    async def find_unique_models(self) -> List[str]:
        """Find all unique model names across all providers.

        Returns:
            List of unique model names.
        """
        rows = await self.fetch_all(f"SELECT DISTINCT model FROM {self.table_name}")
        return [row["model"] for row in rows]

    async def find_by_model(self, model: str) -> Optional[ProviderModel]:
        """Find a provider model by model name.

        Args:
            model: Model name.

        Returns:
            ProviderModel instance if found, None otherwise.
        """
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE model = ? LIMIT 1", (model,)
        )
        if row:
            return await self._row_to_model(row)
        return None

    async def create(self, provider_id: int, model: str) -> Optional[ProviderModel]:
        """Create a new provider model.

        Args:
            provider_id: Provider ID.
            model: Model name.

        Returns:
            Created ProviderModel instance, or None if already exists.
        """
        # Check if exists
        row = await self.fetch_one(
            f"SELECT * FROM {self.table_name} WHERE provider_id = ? AND model = ?",
            (provider_id, model),
        )
        if row:
            return None  # Already exists

        cursor = await self.execute_query(
            f"INSERT INTO {self.table_name} (provider_id, model) VALUES (?, ?)",
            (provider_id, model),
        )
        return ProviderModel(id=cursor.lastrowid, provider_id=provider_id, model=model)

    async def delete(self, model_id: int) -> bool:
        """Delete a provider model by ID.

        Args:
            model_id: Model ID.

        Returns:
            True if deleted, False if not found.
        """
        return await self.delete_by_id(model_id)
