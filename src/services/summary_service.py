"""Summary service"""

from __future__ import annotations

from typing import Optional
from datetime import datetime, timezone, timedelta
import time
import logging
import json

# UTC+8 timezone
UTC8 = timezone(timedelta(hours=8))

# Clean import from Layer 2 (AI Manager)
from src.ai import AIManager, MultimodalInput

from src.services.conversation_service import ConversationService
# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ChatSettingsService, ConfigService

logger = logging.getLogger(__name__)


class SummaryService:
    """对话总结服务
    
    Layer 3 service that depends on Layer 2 (AI Manager).
    """

    def __init__(
        self,
        ai_manager: Optional[AIManager] = None,
        conversation_service: Optional[ConversationService] = None,
        settings_service: Optional[ChatSettingsService] = None,
        config_service: Optional[ConfigService] = None,
    ):
        """初始化总结服务
        
        Args:
            ai_manager: AI管理器
            conversation_service: 对话服务
            settings_service: 设置服务
            config_service: 配置服务
        """
        self.ai_manager = ai_manager or AIManager()
        self.conversation_service = conversation_service or ConversationService()
        self.settings_service = settings_service or ChatSettingsService()
        self.config_service = config_service or ConfigService()

    def _build_summary_prompt(
        self, chat_log: str, time_str: str, language: Optional[str] = None
    ) -> str:
        """构建总结提示词"""
        if not language:
            language = "中文"
        
        return f"""你是一个聊天群里的“吃瓜群众”，现在需要把你写一份吃瓜日报。

你的任务是阅读最近{time_str}的聊天记录，写一份给群友看的总结，风格就像私下给朋友转述群里好玩的事。

【语气要求】
- 用吃瓜群众转述群内乐子的口吻来写：可以带着“看热闹不嫌事大”的心态，适当损一损当事人，但必须是朋友之间那种亲密调侃，不是恶意攻击。必要时可以替当事人“翻译”他没好意思说的大实话。
- 让笑点自己从事实里漏出来。
- 标题要有料，像朋友之间甩过来的八卦链接标题，直接点出最离谱/最搞笑的爆点，但严禁营销号式夸张。
- 严禁使用以下俗套表达：“家人们谁懂啊”“笑不活了”“他真的，我哭死”“这波操作我直接给出满分”“建议入选年度xx”或其他俗套文案。
- 网络流行语可以用，但必须贴合当下语境，不能为用梗而用梗。

【内容要求】
- 使用{language}输出。
- 找出聊天里真正有信息量或好玩的话题，概括事件原委、关键人物发言和群友的反应。
- 如果某句话是引发爆笑或转折的关键，直接引用原话（或适当精简），并点明是谁说的。
- 尽可能全面地提取不同的讨论话题。只要是有趣的、有信息量的或引发了讨论的独立事件，都可以单列成一条，不要过度合并话题（活跃的群聊通常能总结出 5 到 10 条）。
- 但如果聊天记录确实较少，或者大家只集中聊了一两件事，请实事求是地总结，不要为了凑数而生编硬造。

【转发消息处理】
- 聊天记录中可能出现形如 “[Alice 转发了 Bob 的消息] (ID: xxx): 消息内容” 的格式。
- 这种情况下，Bob 是消息的原创者，Alice 只是转发者。**总结时必须理解这个关系。**

【JSON 输出格式要求（必须严格遵守）】
- 最终只输出一个纯净的 JSON 对象，不要有任何额外的文字、标记或解释。
- 每个话题对象中的 `message_ids` 是一个整数，代表该话题里最具代表性的一条消息的 ID（通常是最核心的发言或笑点所在的位置，不一定是时间最早的那条）。
- 消息ID可在聊天记录中找到，格式为 "(ID: xxx)"。
- 输出结构如下（必须是有效的JSON）：
{{
  "topics": [
    {{
      "title": "有趣的标题",
      "description": "这里写具体发生了什么，语气要自然随意",
      "message_ids": [123]
    }}
  ]
}}

【聊天记录】
{chat_log}
"""
    def _format_summary_with_links(
        self, json_data: dict, messages: list, language: Optional[str] = None
    ) -> str:
        """格式化总结并添加超链接
        
        Args:
            json_data: AI返回的JSON数据
            messages: 消息列表（用于查找message对象生成链接）
            language: 语言
        
        Returns:
            带超链接的HTML格式总结
        """
        # 创建 message_id -> Message 映射
        msg_dict = {msg.message_id: msg for msg in messages if msg.message_id}
        
        # 开始构建输出
        if not language:
            language = "Simplified Chinese"
        
        if language == "Simplified Chinese" or language.startswith("Chinese"):
            header = "<b>🍉 群聊吃瓜日报 (Daily Gossip)</b>\n\n"
        else:
            header = "<b>🍉 Daily Gossip Report</b>\n\n"
        
        topics = json_data.get("topics", [])
        if not topics:
            return header + "No interesting topics found. 😴"
        
        result = header
        
        for topic in topics:
            title = topic.get("title", "Unknown Topic")
            description = topic.get("description", "")
            message_ids = topic.get("message_ids", [])
            
            # 生成超链接（使用第一个message_id作为起始消息）
            if message_ids and message_ids[0] in msg_dict:
                first_msg = msg_dict[message_ids[0]]
                url = first_msg.generate_message_url()
                
                if url:
                    # 带超链接的标题
                    result += f'<b><a href="{url}">{title}</a></b> 👉 {description}\n\n'
                else:
                    # 无法生成链接（如私聊），使用纯文本
                    result += f"<b>{title}</b> 👉 {description}\n\n"
            else:
                # 没有message_id，使用纯文本
                result += f"<b>{title}</b> 👉 {description}\n\n"
        
        return result.strip()


    async def generate_summary(
        self,
        chat_id: int,
        hours: int = 24,
        language: Optional[str] = None,
        time_str: Optional[str] = None,
    ) -> str:
        """生成对话总结
        
        Args:
            chat_id: 聊天ID
            hours: 总结的小时数
            language: 总结语言
            time_str: 时间字符串（如"24h", "1d 2h"）
        
        Returns:
            生成的总结文本
        """
        try:
            # 1. 获取消息
            start_time = time.time() - (hours * 3600)
            messages = await self.conversation_service.get_messages_since(
                chat_id, start_time
            )

            if not messages:
                return f"No messages found in the last {hours} hours."

            # 2. 构建chat log
            chat_log = ""
            for msg in messages:
                msg_id_str = f" (ID: {msg.message_id})" if msg.message_id else ""
                
                # 提取纯消息内容（去掉 content 中的 "[名字]: " 前缀）
                content_text = msg.content
                import re
                match = re.match(r'^\[.+?\]:\s*(.*)$', content_text, re.DOTALL)
                if match:
                    content_text = match.group(1)
                
                # 构建发送者信息 - 新格式明确区分转发者和原始发送者
                if msg.is_forwarded:
                    # 转发消息：显示 "[转发者 forwarded 原始发送者's message]"
                    
                    # 获取转发者名字（实际执行转发操作的人）
                    forwarder_name = (
                        msg.sender_full_name or 
                        msg.sender_first_name or 
                        (f"@{msg.sender_username}" if msg.sender_username else "Someone")
                    )
                    
                    # 获取原始发送者名字（消息的真正作者）
                    original_sender = (
                        msg.forward_from_name or 
                        (f"@{msg.forward_from_username}" if msg.forward_from_username else "Unknown")
                    )
                    
                    log_prefix = f"[{forwarder_name} 转发了 {original_sender} 的消息]"
                else:
                    # 普通消息：只显示发送者
                    sender_name = (
                        msg.sender_full_name or 
                        msg.sender_first_name or 
                        (f"@{msg.sender_username}" if msg.sender_username else msg.role)
                    )
                    log_prefix = f"[{sender_name}]"
                
                # 构建最终的chat log条目
                chat_log += f"{log_prefix}{msg_id_str}: {content_text}\n"


            # 3. 构建时间字符串
            if not time_str:
                if hours >= 24:
                    days = hours // 24
                    remaining_hours = hours % 24
                    if remaining_hours > 0:
                        time_str = f"{days}d {remaining_hours}h"
                    else:
                        time_str = f"{days}d"
                else:
                    time_str = f"{hours}h"

            # 4. 构建提示词
            prompt_text = self._build_summary_prompt(chat_log, time_str, language)

            # 5. 获取模型设置（优先使用summary特定模型，fallback到群聊模型）
            model, provider_id = await self.settings_service.get_summary_model_and_provider(chat_id)
            if not model:
                # Fallback to chat model
                model, provider_id = await self.settings_service.get_model_and_provider(chat_id)

            # 6. 使用AI Manager获取总结（流式）
            input_data = MultimodalInput(text=prompt_text)
            
            response_thinking = ""
            response_answer = ""
            
            async for response in self.ai_manager.get_response(
                input_data=input_data,
                chat_id=chat_id,
                stream=True,
                model=model,
                provider_id=provider_id
            ):
                # 优先使用answer，没有answer时使用thinking
                if response.answer:
                    response_answer = response.answer
                elif response.thinking:
                    response_thinking = response.thinking

            # 最终响应
            full_response = response_answer if response_answer else response_thinking
            
            if not full_response:
                return "❌ Failed to generate summary."

            # 6. 解析JSON并生成带超链接的总结
            try:
                # 尝试解析JSON
                # 清理可能的markdown代码块标记
                if "```json" in full_response:
                    json_start = full_response.find("```json") + 7
                    json_end = full_response.find("```", json_start)
                    if json_end != -1:
                        json_text = full_response[json_start:json_end].strip()
                    else:
                        json_text = full_response[json_start:].strip()
                elif "{" in full_response:
                    json_start = full_response.find("{")
                    json_end = full_response.rfind("}") + 1
                    json_text = full_response[json_start:json_end]
                else:
                    json_text = full_response.strip()
                
                json_data = json.loads(json_text)
                
                # 格式化带超链接的总结
                formatted_summary = self._format_summary_with_links(
                    json_data, messages, language
                )
                
                logger.info(f"Generated summary with hyperlinks for chat {chat_id}: {len(formatted_summary)} chars")
                return formatted_summary
                
            except json.JSONDecodeError as je:
                # JSON解析失败，降级为纯文本显示
                logger.warning(f"Failed to parse JSON from AI response: {je}. Falling back to plain text.")
                logger.debug(f"AI response was: {full_response[:500]}...")
                # 返回原始响应（可能已经是格式化的HTML）
                return full_response

        except Exception as e:
            logger.error(f"Error generating summary for chat {chat_id}: {e}")
            return f"❌ Error generating summary: {str(e)}"

    async def should_run_auto_summary(self, chat_id: int) -> bool:
        """检查是否应该运行自动总结"""
        settings = await self.settings_service.get_auto_summary_settings(chat_id)
        if not settings or not settings.enabled:
            return False

        # 检查今天是否已运行
        now_utc8 = datetime.now(UTC8)
        today = now_utc8.strftime("%Y-%m-%d")
        if settings.last_run_date == today:
            return False

        # 检查时间是否匹配
        if settings.hour is not None and settings.minute is not None:
            target_hour = settings.hour
            target_minute = settings.minute

            if now_utc8.hour == target_hour and now_utc8.minute == target_minute:
                return True

        return False

    async def run_auto_summary(self, chat_id: int) -> Optional[str]:
        """运行自动总结
        
        Args:
            chat_id: 聊天ID
        
        Returns:
            总结文本，如果不需要运行则返回None
        """
        if not await self.should_run_auto_summary(chat_id):
            return None

        # 获取设置
        settings = await self.settings_service.get_auto_summary_settings(chat_id)
        if not settings:
            return None

        # 生成总结
        summary = await self.generate_summary(
            chat_id=chat_id,
            hours=24,
            language=settings.language,
        )

        # 更新最后运行日期
        now_utc8 = datetime.now(UTC8)
        today = now_utc8.strftime("%Y-%m-%d")
        await self.settings_service.update_auto_summary_last_run(chat_id, today)

        logger.info(f"Auto-summary completed for chat {chat_id}")
        return summary

    async def get_all_pending_auto_summaries(self) -> list[int]:
        """获取所有待运行的自动总结
        
        Returns:
            待运行的chat_id列表
        """
        all_enabled = await self.settings_service.get_all_enabled_auto_summaries()

        pending = []
        for settings in all_enabled:
            if await self.should_run_auto_summary(settings.chat_id):
                pending.append(settings.chat_id)

        return pending
