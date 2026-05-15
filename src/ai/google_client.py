"""Google Gemini AI client implementation."""

from __future__ import annotations

from typing import AsyncGenerator, Optional, Tuple
import logging
import json

import httpx

from src.ai.base_client import BaseAIClient, AIClientConfig
from src.core.exceptions import AIClientError

logger = logging.getLogger(__name__)


class GoogleGeminiClient(BaseAIClient):
    """Google Gemini API client.

    Supports Google's Gemini models via the generativeai API.
    """

    def __init__(self, config: AIClientConfig):
        """Initialize Google Gemini client.

        Args:
            config: Client configuration.
        """
        self.config = config
        self.config.validate()

        # Normalize base_url for Google API
        self.base_url = self._normalize_base_url(config.base_url)

    def validate_config(self) -> None:
        """Validate client configuration.

        Raises:
            InvalidConfigError: If configuration is invalid.
        """
        self.config.validate()

    def _normalize_base_url(self, base_url: str) -> str:
        """Normalize Google API base URL.

        Args:
            base_url: Original base URL.

        Returns:
            Normalized base URL with v1beta path.
        """
        # Remove trailing slash
        if base_url.endswith("/"):
            base_url = base_url[:-1]

        # Add v1beta if not present
        if "v1beta" not in base_url:
            base_url = f"{base_url}/v1beta"

        return base_url

    async def get_response(
        self,
        messages: list[dict],
        model: str,
        max_tokens: Optional[int] = None,
        stream: bool = True,
        media_list: Optional[list[dict]] = None,
    ) -> AsyncGenerator[Tuple[int, str], None]:
        """Get AI response from Google Gemini API.

        Args:
            messages: List of message dicts with 'role' and 'content'.
            model: Model name to use.
            max_tokens: Maximum tokens to generate.
            stream: Whether to stream the response.
            media_list: Optional list of dicts with 'data' (base64) and 'mime_type'.

        Yields:
            Tuples of (message_type, content) where:
            - message_type 0 = thinking content
            - message_type 1 = answer content

        Raises:
            AIClientError: If the request fails.
        """
        try:
            # Build request URL
            url = f"{self.base_url}/models/{model}:streamGenerateContent"
            params = {"key": self.config.api_key, "alt": "sse"}

            # Convert messages to Google format
            google_contents, system_instruction = self._convert_messages_to_google_format(
                messages, media_list
            )

            # Build request payload
            payload = self._build_payload(
                google_contents, system_instruction, max_tokens
            )

            # Make streaming request
            timeout = httpx.Timeout(self.config.timeout, connect=self.config.connect_timeout)

            async with httpx.AsyncClient(timeout=timeout) as client:
                async with client.stream("POST", url, params=params, json=payload) as response:
                    # Handle errors
                    if response.status_code != 200:
                        error_message = await self._parse_error_response(response)
                        yield (0, error_message)
                        return

                    # Parse SSE stream
                    async for message_type, content in self._parse_sse_stream(response):
                        yield (message_type, content)

        except Exception as e:
            logger.error(f"Google Gemini client error: {e}")
            raise AIClientError(f"Google Gemini request failed: {str(e)}") from e

    def _convert_messages_to_google_format(
        self, messages: list[dict], media_list: Optional[list[dict]]
    ) -> Tuple[list[dict], Optional[dict]]:
        """Convert standard messages to Google format.

        Args:
            messages: List of standard messages.
            media_list: Optional list of dicts with 'data' (base64) and 'mime_type'.

        Returns:
            Tuple of (google_contents, system_instruction).
        """
        google_contents = []
        system_instruction = None

        for msg in messages:
            role = msg["role"]
            content = msg["content"]

            # Handle system prompt
            if role == "system":
                system_instruction = {"parts": [{"text": content}]}
                continue

            # Map roles
            if role == "user":
                role = "user"
            elif role == "assistant":
                role = "model"

            # Create parts
            parts = []
            if isinstance(content, str):
                parts.append({"text": content})
            elif isinstance(content, list):
                for part in content:
                    if part.get("type") == "text":
                        parts.append({"text": part["text"]})
                    elif part.get("type") == "image_url":
                        # Legacy OpenAI format support in messages logic
                        # But Gemini prefers inline_data in the parts list
                        pass 

            google_contents.append({"role": role, "parts": parts})

        # Add media to last user message if provided
        if media_list and google_contents:
            last_msg = google_contents[-1]
            if last_msg["role"] == "user":
                for media in media_list:
                    last_msg["parts"].append(
                        {
                            "inline_data": {
                                "mime_type": media.get("mime_type", "application/octet-stream"),
                                "data": media["data"],
                            }
                        }
                    )

        return google_contents, system_instruction

    def _build_payload(
        self,
        google_contents: list[dict],
        system_instruction: Optional[dict],
        max_tokens: Optional[int],
    ) -> dict:
        """Build request payload for Google API.

        Args:
            google_contents: Converted message contents.
            system_instruction: System instruction if any.
            max_tokens: Maximum output tokens.

        Returns:
            Request payload dict.
        """
        safety_settings = [
            {"category": "HARM_CATEGORY_HARASSMENT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_HATE_SPEECH", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_SEXUALLY_EXPLICIT", "threshold": "BLOCK_NONE"},
            {"category": "HARM_CATEGORY_DANGEROUS_CONTENT", "threshold": "BLOCK_NONE"},
        ]

        generation_config = {}
        if max_tokens:
            generation_config["maxOutputTokens"] = max_tokens

        payload = {
            "contents": google_contents,
            "safetySettings": safety_settings,
            "generationConfig": generation_config,
        }

        if system_instruction:
            payload["systemInstruction"] = system_instruction

        return payload

    async def _parse_error_response(self, response: httpx.Response) -> str:
        """Parse error response from Google API.

        Args:
            response: HTTP response object.

        Returns:
            Formatted error message.
        """
        error_text = await response.aread()
        try:
            error_json = json.loads(error_text)
            if "error" in error_json and "message" in error_json["error"]:
                return f"❌ Error {response.status_code}: {error_json['error']['message']}"
            else:
                return f"❌ Error {response.status_code}: {error_text.decode('utf-8', errors='replace')}"
        except Exception:
            return f"❌ Error {response.status_code}: {error_text.decode('utf-8', errors='replace')}"

    async def _parse_sse_stream(
        self, response: httpx.Response
    ) -> AsyncGenerator[Tuple[int, str], None]:
        """Parse Server-Sent Events stream from Google API.

        Args:
            response: HTTP response object with SSE stream.

        Yields:
            Tuples of (message_type, content).
        """
        async for line in response.aiter_lines():
            if not line.startswith("data:"):
                continue

            line = line[5:].strip()
            if not line:
                continue

            try:
                data = json.loads(line)

                # Extract text from candidates
                if "candidates" not in data:
                    continue

                for candidate in data["candidates"]:
                    if "content" not in candidate or "parts" not in candidate["content"]:
                        continue

                    for part in candidate["content"]["parts"]:
                        if "text" not in part:
                            continue

                        # Check for "thought" field to identify thinking process
                        is_thinking = part.get("thought", False)

                        if is_thinking:
                            yield (0, part["text"])  # Index 0 = Thinking
                        else:
                            # Skip empty text (e.g., thoughtSignature-only parts)
                            if part["text"]:
                                yield (1, part["text"])  # Index 1 = Answer

            except json.JSONDecodeError:
                continue
