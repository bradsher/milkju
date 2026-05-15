"""AI module exports.

Layer 2 in architecture:
- Provides unified AI interface (AIManager)
- Handles multimodal input
- Standardizes AI responses
"""

from src.ai.base_client import BaseAIClient, AIClientConfig
from src.ai.openai_client import OpenAIClient
from src.ai.google_client import GoogleGeminiClient
from src.ai.factory import AIClientFactory

# Main unified interface
from src.ai.manager import AIManager
from src.ai.multimodal_input import MultimodalInput, MediaInput
from src.ai.ai_response import AIResponse

__all__ = [
    # Core AI interface (recommended)
    "AIManager",
    "MultimodalInput",
    "MediaInput",
    "AIResponse",
    # Low-level clients (advanced usage)
    "BaseAIClient",
    "AIClientConfig",
    "OpenAIClient",
    "GoogleGeminiClient",
    "AIClientFactory",
]
