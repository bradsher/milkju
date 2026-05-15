"""AI client factory for creating appropriate client instances."""

from __future__ import annotations

from typing import Optional

from src.ai.base_client import BaseAIClient, AIClientConfig
from src.ai.openai_client import OpenAIClient
from src.ai.google_client import GoogleGeminiClient
from src.core.constants import ClientType
from src.core.exceptions import InvalidConfigError


class AIClientFactory:
    """Factory for creating AI client instances."""

    @staticmethod
    def create_client(
        client_type: str,
        base_url: str,
        api_key: str,
        timeout: float = 300.0,
        connect_timeout: float = 10.0,
    ) -> BaseAIClient:
        """Create an AI client instance based on type.

        Args:
            client_type: Type of client ('openai' or 'google').
            base_url: Base URL for the API.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            connect_timeout: Connection timeout in seconds.

        Returns:
            AI client instance.

        Raises:
            InvalidConfigError: If client_type is invalid or config is invalid.
        """
        # Create config
        config = AIClientConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            connect_timeout=connect_timeout,
        )

        # Create appropriate client
        if client_type == ClientType.OPENAI.value:
            return OpenAIClient(config)
        elif client_type == ClientType.GOOGLE.value:
            return GoogleGeminiClient(config)
        else:
            raise InvalidConfigError(
                f"Unknown client type: {client_type}. Must be 'openai' or 'google'."
            )

    @staticmethod
    def create_openai_client(
        base_url: str,
        api_key: str,
        timeout: float = 300.0,
        connect_timeout: float = 10.0,
    ) -> OpenAIClient:
        """Create an OpenAI client instance.

        Args:
            base_url: Base URL for the API.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            connect_timeout: Connection timeout in seconds.

        Returns:
            OpenAI client instance.
        """
        config = AIClientConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            connect_timeout=connect_timeout,
        )
        return OpenAIClient(config)

    @staticmethod
    def create_google_client(
        base_url: str,
        api_key: str,
        timeout: float = 300.0,
        connect_timeout: float = 10.0,
    ) -> GoogleGeminiClient:
        """Create a Google Gemini client instance.

        Args:
            base_url: Base URL for the API.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            connect_timeout: Connection timeout in seconds.

        Returns:
            Google Gemini client instance.
        """
        config = AIClientConfig(
            base_url=base_url,
            api_key=api_key,
            timeout=timeout,
            connect_timeout=connect_timeout,
        )
        return GoogleGeminiClient(config)
