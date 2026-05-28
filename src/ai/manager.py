"""AI Manager - 统一的AI调用管理器

职责：
1. 统一AI调用接口
2. 多模态输入处理
3. Provider/Model选择
4. 响应格式标准化

分层架构位置：
- Layer 2: AI Manager (当前层)
- 依赖：Layer 1 (core/infrastructure)
- 被依赖：Layer 3 (services)

通过清晰分层，彻底消除循环依赖。
"""

from __future__ import annotations

from typing import Optional, AsyncGenerator
import logging

from src.ai.multimodal_input import MultimodalInput
from src.ai.ai_response import AIResponse
from src.ai.factory import AIClientFactory

# 只依赖基础设施层（Layer 1）
from src.core.infrastructure import ProviderService, ChatSettingsService, ConfigService

logger = logging.getLogger(__name__)


class AIManager:
    """AI管理器 - 统一的AI调用接口
    
    设计原则：
    - 只依赖基础设施层（向下依赖）
    - 提供简洁的API给业务层使用
    - 自动处理provider选择和响应格式化
    
    Example:
        >>> manager = AIManager()
        >>> input_data = MultimodalInput(text="分析这张图")
        >>> input_data.add_image(image_base64)
        >>> 
        >>> async for response in manager.get_response(input_data, chat_id=123):
        >>>     print(response.thinking)
        >>>     print(response.answer)
    """
    
    def __init__(
        self,
        provider_service: Optional[ProviderService] = None,
        settings_service: Optional[ChatSettingsService] = None,
        config_service: Optional[ConfigService] = None,
    ):
        """初始化AI管理器
        
        Args:
            provider_service: Provider服务
            settings_service: 聊天设置服务
            config_service: 配置服务
        """
        self.provider_service = provider_service or ProviderService()
        self.settings_service = settings_service or ChatSettingsService()
        self.config_service = config_service or ConfigService()
    
    async def get_response(
        self,
        input_data: MultimodalInput,
        chat_id: Optional[int] = None,
        stream: bool = True,
        conversation_history: Optional[list[dict]] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
        provider_id: Optional[int] = None,
    ) -> AsyncGenerator[AIResponse, None]:
        """获取AI响应（流式） - 支持 Reactive Fallback"""
        from src.core.exceptions import UnsupportedMediaError
        
        try:
            # 1. Select provider and model
            if not model:
                model, provider_id = await self._select_provider_and_model(chat_id)
            logger.info(f"Selected primary: provider_id={provider_id}, model={model}")

            try:
                # 2. Try primary call
                async for response in self._execute_ai_call(input_data, provider_id, model, stream, conversation_history, system_prompt, max_tokens):
                    yield response

            except UnsupportedMediaError as e:
                logger.warning(f"Primary model {model} does not support media type. Attempting fallback...")
                
                # 3. Reactive Fallback Logic
                # Determine media type for fallback check
                media_type = "file"
                if input_data.has_video: media_type = "video"
                elif input_data.has_audio: media_type = "audio"
                elif input_data.has_image: media_type = "image"
                
                # Check config for fallback rules
                fallback = await self.config_service.get_fallback_rules()
                rule = fallback.get(media_type)
                
                if rule:
                    f_model = rule["model"]
                    f_provider_id = rule["provider_id"]
                    logger.info(f"Using rule-based fallback: {f_model} (Provider {f_provider_id})")
                    async for response in self._execute_ai_call(input_data, f_provider_id, f_model, stream, conversation_history, system_prompt, max_tokens):
                        yield response
                else:
                    # No rule, try ultimate insurance models
                    logger.info("No fallback rule found. Trying ultimate insurance models.")
                    f_model, f_provider_id = await self._get_ultimate_fallback(media_type)
                    if f_model:
                        async for response in self._execute_ai_call(input_data, f_provider_id, f_model, stream, conversation_history, system_prompt, max_tokens):
                            yield response
                    else:
                        raise e # Re-raise if no insurance either

        except Exception as e:
            logger.error(f"Unified AI interface error: {e}", exc_info=True)
            error_response = AIResponse()
            error_response.answer = f"❌ Error: {str(e)}"
            yield error_response

    async def _execute_ai_call(self, input_data, provider_id, model, stream, conversation_history, system_prompt, max_tokens):
        """Helper to get config, create client, and run request."""
        # 1. Get config
        base_url, api_key, client_type = await self.provider_service.get_active_config(model, provider_id)
        
        # 2. Create client via factory
        from src.ai.factory import AIClientFactory
        client = AIClientFactory.create_client(client_type, base_url, api_key)
        
        # 3. Build messages
        messages = self._build_messages(input_data, conversation_history, system_prompt)
        
        # 4. Handle Media (Collect all)
        media_list = []
        if input_data.has_media:
            for item in input_data.media:
                media_list.append({
                    "data": item.data,
                    "mime_type": item.mime_type or "application/octet-stream"
                })
            
        # 5. Execute
        current_response = AIResponse()
        async for msg_type, chunk in client.get_response(
            messages=messages,
            model=model,
            max_tokens=max_tokens,
            stream=stream,
            media_list=media_list
        ):
            if msg_type == 0:
                current_response.thinking += chunk
            else:
                current_response.answer += chunk
            yield current_response

    async def _get_ultimate_fallback(self, media_type: str) -> tuple[str, Optional[int]]:
        """Last resort insurance models if no user fallback rules are set."""
        # If it's a multimodal request that failed, we likely need Gemini/Google
        # since OpenAI-compatible providers are the ones usually raising UnsupportedMediaError
        
        # Try to find a Google provider
        providers = await self.provider_service.get_active_providers()
        google_provider = next((p for p in providers if p.client_type == "google"), None)
        
        if google_provider:
            # Use specified insurance model
            return Defaults.INSURANCE_MULTIMODAL_MODEL, google_provider.id
            
        return Defaults.DEFAULT_MODEL, None # Global insurance
    
    async def get_simple_response(
        self,
        input_data: MultimodalInput,
        chat_id: Optional[int] = None,
        system_prompt: Optional[str] = None,
        max_tokens: Optional[int] = None,
        model: Optional[str] = None,
    ) -> AIResponse:
        """获取简单AI响应（非流式，等待完整响应）
        
        Args:
            input_data: 多模态输入
            chat_id: 聊天ID
            system_prompt: 系统提示词
            max_tokens: 最大token数
            model: 强制指定的模型
        
        Returns:
            完整的AIResponse对象
        
        Example:
            >>> input_data = MultimodalInput(text="什么是Python?")
            >>> response = await interface.get_simple_response(input_data, chat_id=123)
            >>> print(response.answer)
        """
        final_response = AIResponse()
        
        async for response in self.get_response(
            input_data=input_data,
            chat_id=chat_id,
            stream=False,
            system_prompt=system_prompt,
            max_tokens=max_tokens,
            model=model
        ):
            final_response = response
        
        return final_response
    
    async def _select_provider_and_model(
        self,
        chat_id: Optional[int]
    ) -> tuple[str, Optional[int]]:
        """选择provider和model
        
        优先级:
        1. Chat-specific override (chat_id settings) - 用户通过 /set_model 设置的
        2. Global strategy:
           - round_robin: 从配置的 (provider_id, model) pairs 中随机选择
           - single: 使用配置的 model 和 provider_id
        
        Returns:
            (model, provider_id) tuple
        """
        # 1. Chat-specific override (highest priority)
        if chat_id:
            model, provider_id = await self.settings_service.get_model_and_provider(chat_id)
            if model:
                logger.info(f"Using chat-specific setting: model={model}, provider_id={provider_id}")
                return model, provider_id
        
        # 2. Global strategy
        strategy = await self.config_service.get_strategy()
        
        if strategy == "round_robin":
            # Try to use configured pairs
            import random
            pairs = await self.config_service.get_polling_config()
            if pairs:
                pair = random.choice(pairs)
                p_id = pair.get("provider_id")
                m_name = pair.get("model")
                logger.info(f"Round Robin: selected {m_name} from provider {p_id}")
                return m_name, p_id
            # If no pairs configured, log warning and fall through to single mode
            logger.warning("Round Robin strategy selected but no pairs configured, using single mode")
        
        # 3. Single mode (default and fallback)
        model = await self.config_service.get_model()
        provider_id = await self.config_service.get_active_provider_id()
        
        if not model:
            model = Defaults.DEFAULT_MODEL  # Final fallback
        
        logger.info(f"Single mode: model={model}, provider_id={provider_id}")
        return model, provider_id
    
    def _build_messages(
        self,
        input_data: MultimodalInput,
        conversation_history: Optional[list[dict]],
        system_prompt: Optional[str]
    ) -> list[dict]:
        """构建消息列表
        
        Args:
            input_data: 多模态输入
            conversation_history: 对话历史
            system_prompt: 系统提示词
        
        Returns:
            标准格式的消息列表
        """
        messages = []
        
        # 1. 添加系统提示词
        if system_prompt:
            messages.append({"role": "system", "content": system_prompt})
        
        # 2. 添加对话历史
        if conversation_history:
            messages.extend(conversation_history)
        
        # 3. 添加当前用户输入
        # 注意：图片等多模态内容已在input_data中，这里只添加文字
        messages.append({"role": "user", "content": input_data.text})
        
        return messages
