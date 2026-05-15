"""NovelAI API client for image generation using official SDK."""

from __future__ import annotations

import os
import logging
from typing import Optional

logger = logging.getLogger(__name__)

# Check if novelai-python is installed
try:
    from novelai_python import GenerateImageInfer, ImageGenerateResp, ApiCredential
    from novelai_python.sdk.ai.generate_image import Model, Sampler, UCPreset
    from pydantic import SecretStr
    NOVELAI_SDK_AVAILABLE = True
except ImportError:
    NOVELAI_SDK_AVAILABLE = False
    logger.warning("novelai-python not installed. Run: pip install novelai-python")


class NovelAIClient:
    """Client for NovelAI's image generation API using official SDK."""

    # Model mapping
    MODELS = {
        "nai-diffusion-4-5-full": "NAI_DIFFUSION_4_5_FULL",
        "nai-diffusion-4-5-curated": "NAI_DIFFUSION_4_5_CURATED", 
        "nai-diffusion-4-curated-preview": "NAI_DIFFUSION_4_CURATED_PREVIEW",
        "nai-diffusion-3": "NAI_DIFFUSION_3",
    }
    
    # Sampler mapping
    SAMPLERS = {
        "k_euler": "K_EULER",
        "k_euler_ancestral": "K_EULER_ANCESTRAL",
        "k_dpmpp_2s_ancestral": "K_DPMPP_2S_ANCESTRAL",
        "k_dpmpp_2m_sde": "K_DPMPP_2M_SDE",
        "k_dpmpp_sde": "K_DPMPP_SDE",
    }

    def __init__(self, api_token: Optional[str] = None):
        """Initialize NovelAI client.
        
        Args:
            api_token: NovelAI persistent API token. If None, reads from NAI_API_TOKEN env var.
        """
        self.api_token = api_token or os.getenv("NAI_API_TOKEN")
        if not self.api_token:
            logger.warning("NAI_API_TOKEN not configured. NovelAI features will not work.")
        
        self._session = None

    def _get_session(self):
        """Get or create API session."""
        if not NOVELAI_SDK_AVAILABLE:
            raise ValueError("novelai-python SDK not installed. Run: pip install novelai-python")
        
        if not self.api_token:
            raise ValueError("NovelAI API token not configured. Please set NAI_API_TOKEN in .env")
        
        if self._session is None:
            self._session = ApiCredential(api_token=SecretStr(self.api_token))
        
        return self._session

    def _get_model(self, model_name: str):
        """Convert model name string to SDK Model enum."""
        if not NOVELAI_SDK_AVAILABLE:
            raise ValueError("novelai-python SDK not installed")
        
        # Try direct lookup
        enum_name = self.MODELS.get(model_name)
        if enum_name:
            return getattr(Model, enum_name, Model.NAI_DIFFUSION_4_5_FULL)
        
        # Fallback to default
        return Model.NAI_DIFFUSION_4_5_FULL

    def _get_sampler(self, sampler_name: str):
        """Convert sampler name string to SDK Sampler enum."""
        if not NOVELAI_SDK_AVAILABLE:
            raise ValueError("novelai-python SDK not installed")
        
        enum_name = self.SAMPLERS.get(sampler_name)
        if enum_name:
            return getattr(Sampler, enum_name, Sampler.K_EULER_ANCESTRAL)
        
        return Sampler.K_EULER_ANCESTRAL

    async def generate_image(
        self,
        prompt: str,
        negative_prompt: str = "",
        model: str = "nai-diffusion-4-5-full",
        width: int = 1024,
        height: int = 1024,
        steps: int = 28,
        scale: float = 5.0,
        sampler: str = "k_euler_ancestral",
        seed: Optional[int] = None,
    ) -> bytes:
        """Generate an image using NovelAI's API.
        
        Args:
            prompt: Positive prompt describing what to generate.
            negative_prompt: Negative prompt (what to avoid).
            model: Model to use for generation.
            width: Image width in pixels.
            height: Image height in pixels.
            steps: Number of sampling steps (1-50).
            scale: Guidance scale/CFG (1.0-10.0).
            sampler: Sampler algorithm to use.
            seed: Random seed. If None, generates random seed.
            
        Returns:
            Image bytes (PNG format).
            
        Raises:
            ValueError: If API token is not configured or parameters are invalid.
            TimeoutError: If generation takes too long.
        """
        if not NOVELAI_SDK_AVAILABLE:
            raise ValueError("novelai-python SDK not installed. Run: pip install novelai-python")

        session = self._get_session()
        
        # Validate parameters
        if steps < 1 or steps > 50:
            steps = 28
        if scale < 1.0 or scale > 10.0:
            scale = 5.0

        # Generate random seed if not provided
        if seed is None:
            import random
            seed = random.randint(0, 2**32 - 1)

        try:
            # Build generation request using SDK
            model_enum = self._get_model(model)
            sampler_enum = self._get_sampler(sampler)
            
            logger.info(f"Generating image with NovelAI SDK: {width}x{height}, {steps} steps, model={model}")
            
            gen = GenerateImageInfer.build_generate(
                prompt=prompt,
                model=model_enum,
                width=width,
                height=height,
                steps=steps,
                sampler=sampler_enum,
                seed=seed,
                negative_prompt=negative_prompt if negative_prompt else None,
                ucPreset=UCPreset.TYPE0,
                qualityToggle=True,
            )
            
            # Make request
            resp: ImageGenerateResp = await gen.request(session=session)
            
            if not resp.files:
                raise ValueError("NovelAI returned empty response")
            
            # Get first image
            file_data = resp.files[0]
            image_bytes = file_data[1] if isinstance(file_data, tuple) else file_data
            
            logger.info(f"Successfully generated image ({len(image_bytes)} bytes)")
            return image_bytes
            
        except Exception as e:
            error_str = str(e).lower()
            logger.error(f"NovelAI generation error: {e}", exc_info=True)
            
            # Map common errors to user-friendly messages
            if "401" in error_str or "unauthorized" in error_str:
                raise ValueError("Invalid NovelAI API token. Please check your configuration.") from e
            elif "402" in error_str or "payment" in error_str:
                raise ValueError("Insufficient Anlas credits. Please top up your account.") from e
            elif "429" in error_str or "rate limit" in error_str:
                raise ValueError("Rate limit exceeded. Please wait a moment and try again.") from e
            elif "500" in error_str or "server error" in error_str:
                raise ValueError("NovelAI server error. Please try again in a moment.") from e
            elif "timeout" in error_str:
                raise TimeoutError("Image generation took too long. Please try again.") from e
            else:
                raise ValueError(f"NovelAI error: {e}") from e
