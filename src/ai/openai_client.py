"""OpenAI-compatible AI client implementation."""

from __future__ import annotations

from typing import AsyncGenerator, Optional, Tuple
import logging

from openai import AsyncOpenAI

from src.ai.base_client import BaseAIClient, AIClientConfig
from src.core.exceptions import AIClientError, InvalidConfigError, UnsupportedMediaError

logger = logging.getLogger(__name__)


class OpenAIClient(BaseAIClient):
    """OpenAI-compatible API client.

    Supports OpenAI and any OpenAI-compatible APIs (DeepSeek, etc.).
    """

    def __init__(self, config: AIClientConfig):
        """Initialize OpenAI client.

        Args:
            config: Client configuration.
        """
        self.config = config
        self.config.validate()

        self.client = AsyncOpenAI(
            base_url=config.base_url,
            api_key=config.api_key,
            timeout=config.timeout,
        )

    def validate_config(self) -> None:
        """Validate client configuration.

        Raises:
            InvalidConfigError: If configuration is invalid.
        """
        self.config.validate()

    async def get_response(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        media_list: Optional[list[dict]] = None,
    ) -> AsyncGenerator[Tuple[int, str], None]:
        """Get AI response from OpenAI-compatible API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name to use.
            max_tokens: Maximum tokens to generate (None for unlimited/default).
            stream: Whether to stream the response.
            media_list: Optional list of dicts with 'data' (base64) and 'mime_type'.

        Yields:
            Tuples of (0, content) for all responses (no thinking/answer distinction).

        Raises:
            AIClientError: If the request fails.
        """
        try:
            # Handle max_tokens=0 as unlimited (None)
            if max_tokens == 0:
                max_tokens = None

            # DeepSeek-specific fix: max_tokens must be <= 8192
            if "deepseek" in model.lower():
                if max_tokens is None or max_tokens > 8192:
                    logger.info(
                        f"DeepSeek model detected ({model}). Clamping max_tokens to 8192 (was {max_tokens})."
                    )
                    max_tokens = 8192

            # Add images if provided
            if media_list:
                for media in media_list:
                    mime_type = media.get("mime_type", "")
                    if mime_type.startswith("image/"):
                        messages = self._add_image_to_messages(messages, media["data"])
                    else:
                        raise UnsupportedMediaError(f"Media type {mime_type} not supported by OpenAI client.")

            # Make API request
            response = await self.client.chat.completions.create(
                model=model,
                messages=messages, # Use 'messages' directly after potential modification
                max_tokens=max_tokens,
                stream=stream,
            )

            # Handle streaming vs non-streaming
            if stream:
                async for chunk in response:
                    if not chunk.choices:
                        continue
                    
                    delta = chunk.choices[0].delta
                    
                    # Check for reasoning content (thinking process)
                    # DeepSeek Reasoner and similar reasoning models will have this field
                    if hasattr(delta, 'reasoning_content') and delta.reasoning_content is not None:
                        yield (0, delta.reasoning_content)  # Type 0: Thinking
                    
                    # Check for regular content (final answer)
                    # Both reasoning and regular models have this, but:
                    # - Reasoning models: content comes AFTER reasoning_content
                    # - Regular models: content is the only output
                    if delta.content is not None:
                        yield (1, delta.content)  # Type 1: Answer
            else:
                # Non-streaming response
                message = response.choices[0].message
                
                # Check for reasoning content first
                if hasattr(message, 'reasoning_content') and message.reasoning_content:
                    yield (0, message.reasoning_content)  # Type 0: Thinking
                
                # Always emit content as answer (if exists)
                if message.content:
                    yield (1, message.content)  # Type 1: Answer

        except Exception as e:
            logger.error(f"OpenAI client error: {e}")
            raise AIClientError(f"OpenAI request failed: {str(e)}") from e

    def _add_image_to_messages(
        self, messages: list[dict], image_data: Optional[str]
    ) -> list[dict]:
        """Add image data to the last user message if provided.

        Args:
            messages: Original messages.
            image_data: Base64-encoded image data.

        Returns:
            Messages with image added (or original if no image).
        """
        if not image_data:
            return messages

        # Make a copy to avoid modifying original
        messages_copy = [msg.copy() for msg in messages]

        # Find the last user message and add image
        for i in range(len(messages_copy) - 1, -1, -1):
            if messages_copy[i]["role"] == "user":
                content = messages_copy[i]["content"]
                
                # If content is already a list, append the image part
                if isinstance(content, list):
                    content.append({
                        "type": "image_url",
                        "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                    })
                # If content is a string, convert to list and add image
                else:
                    messages_copy[i]["content"] = [
                        {"type": "text", "text": content},
                        {
                            "type": "image_url",
                            "image_url": {"url": f"data:image/jpeg;base64,{image_data}"},
                        },
                    ]
                break

        return messages_copy
