"""Service for image generation using NovelAI."""

from __future__ import annotations

import logging
import time
from typing import Optional
from collections import defaultdict

from src.ai.novelai_client import NovelAIClient
from src.core.infrastructure import ConfigService

logger = logging.getLogger(__name__)


class ImageService:
    """Service for managing image generation with rate limiting and config integration."""

    def __init__(
        self, 
        config_service: Optional[ConfigService] = None,
        nai_client: Optional[NovelAIClient] = None
    ):
        """Initialize image service.
        
        Args:
            config_service: Config service instance.
            nai_client: NovelAI client instance.
        """
        self.config_service = config_service or ConfigService()
        self.nai_client = nai_client or NovelAIClient()
        
        # Rate limiting: user_id -> list of timestamps
        self._rate_limit_tracker: dict[int, list[float]] = defaultdict(list)

    async def is_enabled(self) -> bool:
        """Check if NovelAI feature is enabled.
        
        Returns:
            True if enabled, False otherwise.
        """
        enabled = await self.config_service.get("nai_enabled", default="true")
        return enabled.lower() == "true"

    async def check_rate_limit(self, user_id: int) -> tuple[bool, int, int]:
        """Check if user has exceeded rate limit.
        
        Args:
            user_id: Telegram user ID.
            
        Returns:
            Tuple of (allowed, used_count, limit).
        """
        # Get rate limit from config
        limit_str = await self.config_service.get("nai_rate_limit", default="10")
        try:
            limit = int(limit_str)
        except ValueError:
            limit = 10  # Default to 10 per hour
        
        # Clean up old timestamps (older than 1 hour)
        now = time.time()
        one_hour_ago = now - 3600
        
        timestamps = self._rate_limit_tracker[user_id]
        # Remove timestamps older than 1 hour
        timestamps[:] = [ts for ts in timestamps if ts > one_hour_ago]
        
        used_count = len(timestamps)
        allowed = used_count < limit
        
        return allowed, used_count, limit

    async def record_generation(self, user_id: int):
        """Record a generation for rate limiting.
        
        Args:
            user_id: Telegram user ID.
        """
        self._rate_limit_tracker[user_id].append(time.time())

    async def generate_image(
        self,
        prompt: str,
        user_id: Optional[int] = None,
        **kwargs
    ) -> bytes:
        """Generate an image using configured settings.
        
        Args:
            prompt: User's prompt.
            user_id: Optional user ID for custom settings.
            **kwargs: Override parameters (model, width, height, etc.)
            
        Returns:
            Image bytes.
            
        Raises:
            ValueError: If feature is disabled or parameters are invalid.
            TimeoutError: If generation times out.
        """
        # Check if feature is enabled
        if not await self.is_enabled():
            raise ValueError("NovelAI feature is currently disabled.")

        # Get default settings from config
        model = kwargs.get("model") or await self.config_service.get(
            "nai_model", default="nai-diffusion-4-5-full"
        )
        
        negative_prompt = kwargs.get("negative_prompt") or await self.config_service.get(
            "nai_negative_prompt",
            default="lowres, bad anatomy, bad hands, text, error, missing fingers, "
                    "extra digit, fewer digits, cropped, worst quality, low quality, "
                    "jpeg artifacts, signature, watermark, blurry"
        )
        
        # Check if Anlas-free mode is enabled
        anlas_free_str = await self.config_service.get("nai_anlas_free", default="true")
        anlas_free = anlas_free_str.lower() == "true"
        
        # Get resolution from config
        resolution = kwargs.get("resolution") or await self.config_service.get(
            "nai_resolution", default="square"
        )
        width, height = self._parse_resolution(resolution)
        
        # Get steps from config
        steps_str = kwargs.get("steps") or await self.config_service.get("nai_steps", default="28")
        try:
            steps = int(steps_str)
        except ValueError:
            steps = 28
        
        if anlas_free:
            # Anlas-free mode (Opus tier): 
            # - Total pixels must be <= 1024*1024 = 1,048,576
            # - Steps must be <= 28
            max_pixels = 1024 * 1024
            current_pixels = width * height
            
            if current_pixels > max_pixels:
                # Force to square 1024x1024 if exceeds limit
                logger.warning(f"Resolution {width}x{height} ({current_pixels} pixels) exceeds Anlas-free limit, using 1024x1024")
                width = 1024
                height = 1024
            
            if steps > 28:
                logger.warning(f"Steps {steps} exceeds Anlas-free limit of 28")
                steps = 28
        
        # Get other settings
        scale_str = kwargs.get("scale") or await self.config_service.get("nai_scale", default="5.0")
        try:
            scale = float(scale_str)
        except ValueError:
            scale = 5.0
        
        sampler = kwargs.get("sampler") or await self.config_service.get(
            "nai_sampler", default="k_euler_ancestral"
        )
        
        # Generate image
        logger.info(f"Generating image for user {user_id}: {width}x{height}, {steps} steps, anlas_free={anlas_free}")
        
        image_bytes = await self.nai_client.generate_image(
            prompt=prompt,
            negative_prompt=negative_prompt,
            model=model,
            width=width,
            height=height,
            steps=steps,
            scale=scale,
            sampler=sampler,
        )
        
        return image_bytes

    def _parse_resolution(self, resolution: str) -> tuple[int, int]:
        """Parse resolution string to width and height.
        
        Args:
            resolution: Resolution string like "1024x1024" or preset name.
            
        Returns:
            Tuple of (width, height).
        """
        # Preset resolutions
        presets = {
            "portrait": (832, 1216),
            "landscape": (1216, 832),
            "square": (1024, 1024),
            "large_portrait": (1024, 1536),
            "large_landscape": (1536, 1024),
        }
        
        resolution_lower = resolution.lower()
        if resolution_lower in presets:
            return presets[resolution_lower]
        
        # Parse custom resolution like "1024x1024"
        try:
            parts = resolution.split("x")
            if len(parts) == 2:
                width = int(parts[0])
                height = int(parts[1])
                return width, height
        except (ValueError, IndexError):
            pass
        
        # Default to square
        logger.warning(f"Invalid resolution '{resolution}', defaulting to 1024x1024")
        return 1024, 1024
