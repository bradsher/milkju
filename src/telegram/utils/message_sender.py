import logging
from src.telegram.utils.message_splitter import HTMLSplitter, strip_html

logger = logging.getLogger(__name__)

def telegram_escape(text: str) -> str:
    """Escape text for Telegram HTML parse mode.
    
    Only escapes &, <, and >.
    """
    if not text:
        return text
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

class MessageSender:
    """统一消息发送器。根据场景自动选择发送策略。"""
    
    def __init__(self, bot, chat_id, parse_mode="HTML"):
        self.bot = bot
        self.chat_id = chat_id
        self.parse_mode = parse_mode
        self.splitter = HTMLSplitter()
        
    async def send_static(
        self,
        text: str,
        reply_to_message_id=None,
        disable_notification=False,
        **kwargs
    ) -> list[int]:
        """
        非流式发送消息（用于 summary、search 等确定性结果）。
        
        流程：
        1. 检查长度是否需要分段
        2. 不超过 4096 → 直接 sendMessage
        3. 超过 → splitter 分段 → 逐段 sendMessage
        4. 返回所有 message_id
        
        返回: [msg1_id, msg2_id, ...]
        """
        if len(text) <= 4096:
            try:
                msg = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=text,
                    parse_mode=self.parse_mode,
                    reply_to_message_id=reply_to_message_id,
                    disable_notification=disable_notification,
                    **kwargs
                )
                return [msg.message_id]
            except Exception as e:
                if "message to be replied not found" in str(e).lower():
                    logger.warning("Original message not found, falling back to regular message.")
                    msg = await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=text,
                        parse_mode=self.parse_mode,
                        disable_notification=disable_notification
                    )
                    return [msg.message_id]
                else:
                    logger.error(f"Failed to send static message: {e}")
                    raise
                
        # 分段发送
        logger.info(f"Message exceeds limit, splitting into chunks. Length: {len(text)}")
        chunks = self.splitter.split(text)
        logger.info(f"Split completed. Created {len(chunks)} chunks.")
        message_ids = []
        for chunk in chunks:
            try:
                msg = await self.bot.send_message(
                    chat_id=self.chat_id,
                    text=chunk["text"],
                    parse_mode=self.parse_mode,
                    reply_to_message_id=reply_to_message_id,
                    disable_notification=disable_notification,
                    **kwargs
                )
                message_ids.append(msg.message_id)
            except Exception as e:
                if "message to be replied not found" in str(e).lower():
                    logger.warning("Original message not found for chunk, falling back to regular message.")
                    msg = await self.bot.send_message(
                        chat_id=self.chat_id,
                        text=chunk["text"],
                        parse_mode=self.parse_mode,
                        disable_notification=disable_notification,
                        **kwargs
                    )
                    message_ids.append(msg.message_id)
                else:
                    logger.error(f"Failed to send chunk: {e}")
                    raise
                
        return message_ids

    async def send_streaming(
        self,
        content_generator,  # AsyncGenerator[str, None] —— AI 生成 token 流
        reply_to_message_id=None
    ) -> list[int]:
        """
        流式发送消息（用于 AI 对话响应）。
        """
        from src.telegram.utils.stream_manager import StreamManager
        from telegram.error import RetryAfter
        import asyncio
        
        stream_mgr = StreamManager()
        logger.info(f"Starting streaming message for chat {self.chat_id}")
        
        try:
            async for token in content_generator:
                stream_mgr.append_content(token)
                
                # 检查是否需要分段
                chunk, remaining = stream_mgr.check_split()
                if chunk:
                    logger.info(f"Streaming buffer reached soft limit, finalize chunk. Length: {len(chunk)}")
                    # 定稿当前段
                    try:
                        msg = await self.bot.send_message(
                            chat_id=self.chat_id,
                            text=chunk,
                            parse_mode=self.parse_mode,
                            reply_to_message_id=reply_to_message_id
                        )
                        stream_mgr.message_ids.append(msg.message_id)
                        # 重置 draft_id 为下一段准备
                        stream_mgr.draft_id += 1
                        stream_mgr.fallback_message = None
                    except RetryAfter as e:
                        stream_mgr.handle_429(e.retry_after)
                        await asyncio.sleep(e.retry_after)
                    except Exception as e:
                        if "message to be replied not found" in str(e).lower():
                            logger.warning("Original message not found for chunk finalize, falling back.")
                            msg = await self.bot.send_message(
                                chat_id=self.chat_id,
                                text=chunk,
                                parse_mode=self.parse_mode
                            )
                            stream_mgr.message_ids.append(msg.message_id)
                            stream_mgr.draft_id += 1
                            stream_mgr.fallback_message = None
                        else:
                            logger.error(f"Failed to finalize chunk: {e}")
                        
                # 检查是否需要更新草稿 (sendMessageDraft)
                if stream_mgr.should_update() and stream_mgr.buffer:
                    if stream_mgr.primary_mode == "draft":
                        try:
                            await self.bot.send_message_draft(
                                chat_id=self.chat_id,
                                draft_id=stream_mgr.draft_id,
                                text=stream_mgr.buffer,
                                parse_mode=self.parse_mode
                            )
                            stream_mgr.mark_updated()
                        except RetryAfter as e:
                            stream_mgr.handle_429(e.retry_after)
                            await asyncio.sleep(e.retry_after)
                        except Exception as e:
                            if "draft_peer_invalid" in str(e).lower():
                                logger.warning(f"Draft not supported for peer {self.chat_id}, falling back to simulated streaming.")
                                stream_mgr.primary_mode = "fallback"
                                stream_mgr.update_interval = stream_mgr.fallback_interval
                            else:
                                logger.error(f"Failed to send draft: {e}")
                    
                    if stream_mgr.primary_mode == "fallback":
                        try:
                            if not stream_mgr.fallback_message:
                                # 首次进入回退模式，发送新消息
                                try:
                                    msg = await self.bot.send_message(
                                        chat_id=self.chat_id,
                                        text=stream_mgr.buffer,
                                        parse_mode=self.parse_mode,
                                        reply_to_message_id=reply_to_message_id
                                    )
                                except Exception as e:
                                    if "message to be replied not found" in str(e).lower():
                                        msg = await self.bot.send_message(
                                            chat_id=self.chat_id,
                                            text=stream_mgr.buffer,
                                            parse_mode=self.parse_mode
                                        )
                                    else:
                                        raise
                                stream_mgr.fallback_message = msg
                                stream_mgr.message_ids.append(msg.message_id)
                            else:
                                # 编辑已有消息
                                await self.bot.edit_message_text(
                                    chat_id=self.chat_id,
                                    message_id=stream_mgr.fallback_message.message_id,
                                    text=stream_mgr.buffer,
                                    parse_mode=self.parse_mode
                                )
                            stream_mgr.mark_updated()
                        except RetryAfter as e:
                            await asyncio.sleep(e.retry_after)
                        except Exception as e:
                            logger.error(f"Failed to edit message in fallback: {e}")
                            
            # 循环结束后，处理剩余的 buffer (定稿)
            if stream_mgr.buffer:
                try:
                    if stream_mgr.primary_mode == "draft":
                        try:
                            msg = await self.bot.send_message(
                                chat_id=self.chat_id,
                                text=stream_mgr.buffer,
                                parse_mode=self.parse_mode,
                                reply_to_message_id=reply_to_message_id
                            )
                        except Exception as e:
                            if "message to be replied not found" in str(e).lower():
                                msg = await self.bot.send_message(
                                    chat_id=self.chat_id,
                                    text=stream_mgr.buffer,
                                    parse_mode=self.parse_mode
                                )
                            else:
                                raise
                        stream_mgr.message_ids.append(msg.message_id)
                    elif stream_mgr.primary_mode == "fallback" and stream_mgr.fallback_message:
                        await self.bot.edit_message_text(
                            chat_id=self.chat_id,
                            message_id=stream_mgr.fallback_message.message_id,
                            text=stream_mgr.buffer,
                            parse_mode=self.parse_mode
                        )
                except Exception as e:
                    logger.error(f"Failed to finalize last chunk: {e}")
                    
        except Exception as e:
            logger.error(f"Error in send_streaming: {e}")
            
        logger.info(f"Streaming completed. Sent {len(stream_mgr.message_ids)} messages for chat {self.chat_id}.")
        return stream_mgr.message_ids


