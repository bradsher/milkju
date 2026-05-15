"""Base AI client protocol and interfaces."""

from __future__ import annotations

from typing import Protocol, AsyncGenerator, Optional, Tuple
from abc import abstractmethod


class BaseAIClient(Protocol):
    """Protocol defining the interface for AI clients.

    All AI client implementations (OpenAI, Google, etc.) must implement this interface.
    """

    async def get_response(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        media_list: Optional[list[dict]] = None,
    ) -> AsyncGenerator[Tuple[int, str], None]:
        """Get AI response for given messages.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name to use.
            max_tokens: Maximum tokens to generate (None for unlimited/default).
            stream: Whether to stream the response.
            media_list: Optional list of dicts with keys 'data' (base64) and 'mime_type'.

        Yields:
            Tuples of (message_type, content) where:
            - message_type 0 = thinking/intermediate content
            - message_type 1 = final answer content

        Raises:
            AIClientError: If the request fails.
        """
        ...

    @abstractmethod
    def validate_config(self) -> None:
        """Validate client configuration.

        Raises:
            InvalidConfigError: If configuration is invalid.
        """
        ...


class AIClientConfig:
    """Configuration for AI clients."""

    def __init__(
        self,
        base_url: str,
        api_key: str,
        timeout: float = 300.0,
        connect_timeout: float = 10.0,
    ):
        """Initialize AI client config.

        Args:
            base_url: Base URL for API.
            api_key: API key for authentication.
            timeout: Request timeout in seconds.
            connect_timeout: Connection timeout in seconds.
        """
        self.base_url = base_url
        self.api_key = api_key
        self.timeout = timeout
        self.connect_timeout = connect_timeout

    def validate(self) -> None:
        """Validate configuration.

        Raises:
            InvalidConfigError: If configuration is invalid.
        """
        from src.core.exceptions import InvalidConfigError

        if not self.base_url:
            raise InvalidConfigError("base_url is required")
        if not self.api_key:
            raise InvalidConfigError("api_key is required")
        if self.timeout <= 0:
            raise InvalidConfigError("timeout must be positive")
        if self.connect_timeout <= 0:
            raise InvalidConfigError("connect_timeout must be positive")
