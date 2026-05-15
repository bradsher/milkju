"""Chat message handlers using service layer."""

from __future__ import annotations

from telegram import Update, constants
from telegram.ext import ContextTypes
import logging
import base64
import time
import re
import html

from src.services import ConversationService, PermissionService
# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ConfigService
from src.core.constants import MessageRole
from src.telegram.utils.message_utils import edit_message_safe, reply_message_safe, send_long_message, _chunk_message

logger = logging.getLogger(__name__)



def telegram_escape(text: str) -> str:
    """Escape text for Telegram HTML parse mode.
    
    Only escapes &, <, and >. Other characters like ' and " are allowed.
    """
    if not text:
        return text
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def markdown_to_html(text: str) -> str:
    """Convert basic markdown formatting to Telegram HTML.
    
    Supports:
    - **bold** or __bold__ -> <b>bold</b>
    - *italic* or _italic_ -> <i>italic</i>
    - `code` -> <code>code</code>
    - ```code block``` -> <pre>code block</pre>
    - [link](url) -> <a href="url">link</a>
    
    Uses placeholder mechanism to avoid nested formatting issues.
    Only converts complete, properly closed markers to handle streaming.
    
    Args:
        text: Markdown text.
    
    Returns:
        HTML formatted text.
    """
    if not text:
        return text
    
    # Escape HTML entities first (Safe for Telegram)
    text = telegram_escape(text)
    
    # Store code blocks and inline code with placeholders to protect them
    code_blocks = []
    inline_codes = []
    
    # Replace code blocks with placeholders (must have both ``` markers)
    # Use format without any markdown special chars: XCODEBLOCK0X, XCODEBLOCK1X, etc.
    def save_code_block(match):
        code_blocks.append(f'<pre>{match.group(1)}</pre>')
        return f'XCODEBLOCK{len(code_blocks)-1}X'
    
    text = re.sub(r'```([^`]+)```', save_code_block, text)
    
    # Replace inline code with placeholders (must have both ` markers)
    def save_inline_code(match):
        inline_codes.append(f'<code>{match.group(1)}</code>')
        return f'XINLINECODE{len(inline_codes)-1}X'
    
    text = re.sub(r'`([^`]+)`', save_inline_code, text)
    
    # Now process other formatting (they won't interfere with code)
    # Use more restrictive patterns that require both opening and closing markers
    # and don't match across the same marker type
    
    # Headers (# to ######) - convert to bold text since Telegram doesn't support <h1>-<h6>
    # Must process before other formatting to avoid conflicts
    # Match headers at start of line: ^\s*#{1,6}\s+(.+?)$
    text = re.sub(r'^(\s*)#{1,6}\s+(.+?)$', r'\1<b>\2</b>', text, flags=re.MULTILINE)
    
    # Bold (**text** - non-greedy, no ** inside)
    # Pattern: \*\*([^*]+?)\*\* matches ** followed by non-* chars, then **
    text = re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', text)
    
    # Bold (__text__ - non-greedy, no __ inside)
    text = re.sub(r'__([^_]+?)__', r'<b>\1</b>', text)
    
    # Italic (*text* - must not be ** and no * inside)
    # Use negative lookahead/lookbehind to avoid matching ** as *
    text = re.sub(r'(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # Italic (_text_ - must not be __ and no _ inside)  
    text = re.sub(r'(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
    
    # Links [text](url) - must have complete brackets and parentheses
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', r'<a href="\2">\1</a>', text)
    
    # Restore code blocks
    for i, code_block in enumerate(code_blocks):
        text = text.replace(f'XCODEBLOCK{i}X', code_block)
    
    # Restore inline codes
    for i, inline_code in enumerate(inline_codes):
        text = text.replace(f'XINLINECODE{i}X', inline_code)
    
    return text

async def start_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /start command."""
    user = update.effective_user
    await update.message.reply_html(
        rf"Hi {user.mention_html()}! I am your AI assistant. Send me a message to start chatting."
    )
    logger.info(f"User {user.id} started the bot.")


async def help_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /help command - shows different help based on user role."""
    permission_service = PermissionService()
    user_id = update.effective_user.id
    
    # Check if user is a bot admin
    is_bot_admin = await permission_service.is_admin(user_id)
    
    if is_bot_admin:
        # Help text for bot administrators
        help_text = """
📚 <b>TeleChat 管理员命令参考</b>
📚 <b>TeleChat Admin Command Reference</b>

━━━━━━━━━━━━━━━━━━━━

<b>👤 基础命令 / Basic Commands</b>

• /start - 启动机器人 / Start the bot
• /help - 显示此帮助信息 / Show this help message
• /cancel - 取消当前操作 / Cancel current operation
• /p - 发送消息但不触发AI回复 / Send without AI reply
  <i>仅记录消息到对话历史 / Only logs message to history</i>

━━━━━━━━━━━━━━━━━━━━

<b>🔍 搜索与推荐 / Search &amp; Recommendations</b>

• /s &lt;关键词&gt; - 联网搜索并获取AI总结 / Web search with AI summary
  <i>示例 / Example: /s 最新 AI 新闻</i>

• /recommend &lt;电影1,电影2&gt; - 基于喜好推荐电影 / Movie recommendations
  <i>示例 / Example: /recommend 肖申克的救赎,楚门的世界</i>
  <i>支持1-5部电影 / Supports 1-5 movies</i>

━━━━━━━━━━━━━━━━━━━━

<b>🛡️ 对话管理 / Conversation Management</b>

• /new - 开始新对话 / Start fresh conversation
  <i>私聊可用 / Private chat only</i>

• /clear - 清空对话历史 / Clear conversation history
  <i>群组需管理员权限 / Requires admin in groups</i>

━━━━━━━━━━━━━━━━━━━━

<b>📊 总结功能 / Summary Features</b>

• /summary &lt;时间&gt; [语言] - 生成聊天总结 / Generate chat summary
  <i>示例 / Example: /summary 6h 或 /summary 1d English</i>
  <i>格式 / Format: d(天/days), h(小时/hours), m(分钟/minutes)</i>
  <i>权限 / Permissions: 群组管理员或Bot管理员</i>

• /auto_summary &lt;时间1&gt; [时间2] [pin:0/1] - 设置自动总结 / Auto-summary
  <i>单时间: /auto_summary 18:00 → 每天总结前24h</i>
  <i>双时间: /auto_summary 10:00 22:00 → 每天总结两次，各12h</i>
  <i>置顶: /auto_summary 10:00 22:00 1 → 总结后自动置顶</i>
  <i>/auto_summary off - 关闭 / Disable</i>
  <i>/auto_summary - 查看状态 / Check status</i>
  <i>仅群组管理员 / Group admins only</i>

━━━━━━━━━━━━━━━━━━━━

<b>⚙️ 聊天设置 / Chat Settings</b>

• /system - 查看当前系统提示词 / View system prompt
• /set_system &lt;提示词&gt; - 设置系统提示词 / Set system prompt
  <i>示例 / Example: /set_system 你是一个编程助手</i>
  <i>/set_system default - 恢复默认 / Reset to default</i>
  <i>需要群组管理员权限 / Requires group admin</i>

• /set_model - 选择AI模型 / Select AI model
  <i>打开模型选择菜单 / Opens model selection menu</i>
  <i>需要Bot管理员+群组管理员双重权限 / Requires both bot &amp; group admin</i>

━━━━━━━━━━━━━━━━━━━━

<b>🔧 管理员功能 / Admin Features</b>

• /admin - 系统配置面板 / System configuration panel
  <i>私聊可用 / Private chat only</i>
  <i>管理提供商、模型、API密钥等 / Manage providers, models, API keys, etc.</i>
  
  <b>管理面板功能 / Admin Panel Features:</b>
  • 🤖 AI设置 / AI Settings - 配置提供商、模型、API密钥
  • 💬 聊天设置 / Chat Settings - 历史记录限制、摘要设置
  • 📁 文件与存储 / File &amp; Storage - 文件管理、存储配额
  • 👥 管理员管理 / Admin Management - 添加/删除管理员 <i>(仅超级管理员)</i>
  • 🔧 系统配置 / System Config - 消息自动清理等 <i>(仅超级管理员)</i>

• /claim &lt;密钥&gt; - 获取管理员权限 / Claim admin privileges
  <i>一次性设置命令 / One-time setup command</i>

━━━━━━━━━━━━━━━━━━━━

<b>ℹ️ 系统信息 / System Info</b>

• 支持 OpenAI 兼容和 Google Gemini 原生接口
  Supports OpenAI-compatible and Google Gemini native APIs
  
• 群组中需@机器人或回复消息触发响应
  In groups, mention bot or reply to get a response
  
• 私聊仅限管理员使用
  Private chat is restricted to admins only
  
• 自动总结按UTC+8时区运行
  Auto-summary runs in UTC+8 timezone
  
• 支持图片、音频、视频和文档分析
  Supports image, audio, video and document analysis
  
• 完整分层架构，支持多提供商负载均衡
  Full layered architecture with multi-provider load balancing

━━━━━━━━━━━━━━━━━━━━

💡 <i>您拥有管理员权限，可访问所有功能和配置面板</i>
💡 <i>You have admin privileges with full access to all features</i>
        """
    else:
        # Help text for regular users
        help_text = """
📚 <b>TeleChat 命令参考</b>
📚 <b>TeleChat Command Reference</b>

━━━━━━━━━━━━━━━━━━━━

<b>👤 基础命令 / Basic Commands</b>

• /start - 启动机器人 / Start the bot
• /help - 显示此帮助信息 / Show this help message
• /cancel - 取消当前操作 / Cancel current operation
• /p - 发送消息但不触发AI回复 / Send without AI reply
  <i>仅记录消息到对话历史 / Only logs message to history</i>

━━━━━━━━━━━━━━━━━━━━

<b>🔍 搜索与推荐 / Search &amp; Recommendations</b>

• /s &lt;关键词&gt; - 联网搜索并获取AI总结 / Web search with AI summary
  <i>示例 / Example: /s 最新 AI 新闻</i>
  <i>所有用户可用 / Available to all users</i>

• /recommend &lt;电影1,电影2&gt; - 基于喜好推荐电影 / Movie recommendations
  <i>示例 / Example: /recommend 肖申克的救赎,楚门的世界</i>
  <i>支持1-5部电影 / Supports 1-5 movies</i>
  <i>所有用户可用 / Available to all users</i>

━━━━━━━━━━━━━━━━━━━━

<b>🛡️ 对话管理 / Conversation Management</b>

• /clear - 清空对话历史 / Clear conversation history
  <i>群组中需要管理员权限 / Requires admin in groups</i>

━━━━━━━━━━━━━━━━━━━━

<b>📊 总结功能 / Summary Features</b>

• /summary &lt;时间&gt; [语言] - 生成聊天总结 / Generate chat summary
  <i>示例 / Example: /summary 6h 或 /summary 1d English</i>
  <i>格式 / Format: d(天/days), h(小时/hours), m(分钟/minutes)</i>
  <i>需要管理员权限 / Requires admin permissions</i>

• /auto_summary - 查看自动总结状态 / Check auto-summary status
  <i>单时间: /auto_summary 18:00 → 每天总结前24h</i>
  <i>双时间: /auto_summary 10:00 22:00 → 每天总结两次，各12h</i>
  <i>配置功能仅限群组管理员 / Configuration for group admins only</i>

━━━━━━━━━━━━━━━━━━━━

<b>⚙️ 聊天设置 / Chat Settings</b>

• /system - 查看当前系统提示词 / View system prompt
  <i>需要群组管理员权限 / Requires group admin</i>

• /set_system &lt;提示词&gt; - 设置系统提示词 / Set system prompt
  <i>需要群组管理员权限 / Requires group admin</i>

━━━━━━━━━━━━━━━━━━━━

<b>ℹ️ 使用提示 / Usage Tips</b>

• 群组中需@机器人或回复消息触发响应
  In groups, mention bot or reply to get a response
  
• 支持发送图片、音频、视频和文档进行分析
  Supports image, audio, video and document analysis
  
• 使用 /p 命令可以发送消息而不触发AI回复
  Use /p to send messages without triggering AI response
  
• 电影推荐和网络搜索功能无需特殊权限
  Movie recommendations and web search are available to all

━━━━━━━━━━━━━━━━━━━━

💡 <i>如需更多管理功能，请联系管理员</i>
💡 <i>For admin features, please contact an administrator</i>
        """
    
    await reply_message_safe(update.message, help_text.strip(), parse_mode="HTML")


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing conversation or input wait."""
    if context.user_data.get('awaiting_config'):
        context.user_data['awaiting_config'] = None
        await reply_message_safe(update.message, "🚫 Operation cancelled.")
    else:
        await reply_message_safe(update.message, "🚫 Nothing to cancel.")


async def p_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /p command to log message but skip AI response."""
    context.user_data['skip_ai_once'] = True
    await chat_message(update, context)


async def chat_message(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle incoming chat messages and generate AI responses.

    Uses ConversationService and AIManager for clean business logic.
    
    Layer 4 (Handlers) - depends on Layer 3 (Services) and Layer 2 (AI Manager).
    """
    # Import AI Manager (Layer 2)
    from src.ai import AIManager, MultimodalInput
    # Import from infrastructure layer (Layer 1)
    from src.core.infrastructure import ConfigService
    
    # Initialize services
    conversation_service = ConversationService()
    ai_manager = AIManager()
    permission_service = PermissionService()

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name

    message = update.effective_message
    user_message = message.text or message.caption or ""
    chat_type = message.chat.type
    bot_username = context.bot.username

    # --- 1. Access Control (Private Chat) ---
    if chat_type == constants.ChatType.PRIVATE:
        if not await permission_service.is_admin(user_id):
            await reply_message_safe(message, "⛔ 抱歉，目前仅允许管理员使用私聊。")
            return

    # --- 2. Group Chat Logic ---
    if chat_type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        # Log ALL text messages for summary
        if user_message:
            try:
                # Extract metadata
                sender = message.from_user
                chat = message.chat
                
                # Check if this is a forwarded message (python-telegram-bot v20+)
                # Use forward_origin instead of deprecated forward_from/forward_from_chat
                is_forwarded = message.forward_origin is not None
                forward_metadata = {}
                
                if is_forwarded and message.forward_origin:
                    from telegram import MessageOriginUser, MessageOriginHiddenUser, MessageOriginChat, MessageOriginChannel
                    
                    origin = message.forward_origin
                    if isinstance(origin, MessageOriginUser):
                        # User allowed showing forward source
                        forward_metadata = {
                            'forward_from_id': origin.sender_user.id,
                            'forward_from_username': origin.sender_user.username,
                            'forward_from_name': origin.sender_user.first_name,
                            'forward_date': origin.date,
                        }
                    elif isinstance(origin, MessageOriginHiddenUser):
                        # User hid forward source, only name available
                        forward_metadata = {
                            'forward_from_name': origin.sender_user_name,
                            'forward_date': origin.date,
                        }
                    elif isinstance(origin, MessageOriginChat):
                        # Forwarded from a chat (uses sender_chat)
                        forward_metadata = {
                            'forward_from_id': origin.sender_chat.id,
                            'forward_from_username': origin.sender_chat.username,
                            'forward_from_name': origin.sender_chat.title,
                            'forward_date': origin.date,
                        }
                    elif isinstance(origin, MessageOriginChannel):
                        # Forwarded from a channel (uses chat)
                        forward_metadata = {
                            'forward_from_id': origin.chat.id,
                            'forward_from_username': origin.chat.username,
                            'forward_from_name': origin.chat.title,
                            'forward_date': origin.date,
                        }
                
                # Check reply message
                reply_metadata = {}
                log_context = ""
                if message.reply_to_message:
                    r_user = message.reply_to_message.from_user.first_name
                    r_text = message.reply_to_message.text or "[Media]"
                    log_context = f" (Replying to {r_user}: {r_text})"
                    
                    reply_metadata = {
                        'reply_to_message_id': message.reply_to_message.message_id,
                        'reply_to_user_id': message.reply_to_message.from_user.id,
                    }
                
                # Preserve original log format
                full_log_message = f"[{user_name}]: {user_message}"
                
                # Save message with complete metadata
                await conversation_service.add_user_message(
                    chat_id,
                    full_log_message + log_context,
                    message_id=message.message_id,
                    # New metadata
                    sender_id=sender.id,
                    sender_username=sender.username,
                    sender_first_name=sender.first_name,
                    sender_full_name=f"{sender.first_name} {sender.last_name or ''}".strip(),
                    chat_id=chat.id,
                    chat_type=chat.type,
                    chat_username=chat.username,
                    is_forwarded=is_forwarded,
                    **forward_metadata,
                    **reply_metadata,
                )
            except Exception as e:
                # Log error but don't crash - just save basic message without metadata
                logger.error(f"Error extracting message metadata: {e}", exc_info=True)
                try:
                    # Fallback: save message with minimal metadata
                    await conversation_service.add_user_message(
                        chat_id,
                        f"[{user_name}]: {user_message}",
                        message_id=message.message_id,
                    )
                except Exception as fallback_error:
                    logger.error(f"Fallback save also failed: {fallback_error}")
                # CRITICAL: Don't return here - let the bot continue to check if it should respond

        # Check if bot should respond
        is_mentioned = f"@{bot_username}" in user_message
        is_reply_to_bot = (
            message.reply_to_message
            and message.reply_to_message.from_user.id == context.bot.id
        )

        if not (is_mentioned or is_reply_to_bot):
            return

    # --- 3. Multimodal (Image/Audio/Video) & Reply Handling ---

    async def extract_all_media(msg) -> list[tuple]:
        """Extract all media from message."""
        extracted = []
        
        # 1. Photo
        if msg.photo:
            file_obj = msg.photo[-1]
            extracted.append((file_obj, "image/jpeg", "image"))
            
        # 2. Audio
        if msg.audio:
            extracted.append((msg.audio, msg.audio.mime_type or "audio/mpeg", "audio"))
            
        # 3. Voice
        if msg.voice:
            extracted.append((msg.voice, msg.voice.mime_type or "audio/ogg", "audio"))
            
        # 4. Video
        if msg.video:
            extracted.append((msg.video, msg.video.mime_type or "video/mp4", "video"))
            
        # 5. Video Note
        if msg.video_note:
            extracted.append((msg.video_note, "video/mp4", "video"))
            
        # Initialize results list
        results = []
        
        # 6. Document (for non-current-message documents, like in replies)
        # Main document processing block (line 540+) handles current message documents
        # and replied documents for text extraction. Here we only handle non-text
        # documents in replies that need to be sent as media.
        # 
        # However, since main document block now handles ALL documents (current + replied),
        # we should skip document processing here entirely to avoid:
        # - Duplicate downloads  
        # - Text files being sent as base64 instead of having content extracted
        #
        # The main block will handle text extraction for text files,
        # and add PDF/other docs to all_media_items

        # Process other media types (images, audio, video)
        for file_obj, mime, m_type in extracted:
            # Check file size (20MB limit for bot api download)
            if hasattr(file_obj, 'file_size') and file_obj.file_size and file_obj.file_size > 20 * 1024 * 1024:
                continue
                
            try:
                f = await context.bot.get_file(file_obj.file_id)
                byte_array = await f.download_as_bytearray()
                b64_data = base64.b64encode(byte_array).decode("utf-8")
                results.append((b64_data, mime, m_type, getattr(file_obj, 'file_name', None)))
            except Exception as e:
                logger.error(f"Media download failed: {e}")
        
        return results

    # Media storage
    all_media_items = [] # List of (data, mime, type, filename)

    # Check for reply context and media
    reply_context = ""
    if message.reply_to_message:
        replied_msg = message.reply_to_message
        replied_user = replied_msg.from_user.first_name
        replied_text = replied_msg.text or replied_msg.caption or "[Media]"
        reply_context = f"\n\n[Context] Replying to {replied_user}: {replied_text}"

        # Extract media from replied message
        replied_media = await extract_all_media(replied_msg)
        all_media_items.extend(replied_media)

    # Extract media from current message
    current_media = await extract_all_media(message)
    all_media_items.extend(current_media)

    full_user_message = f"[{user_name}]: {user_message}{reply_context}"

    # --- Handle Document Files ---
    # Check both current message and replied message for documents
    target_document = message.document or (message.reply_to_message.document if message.reply_to_message else None)
    
    if target_document:
        from src.services.file_service import FileService
        file_service = FileService()
        
        # Check storage quota
        can_upload, quota_msg = await file_service.check_storage_quota()
        if not can_upload:
            await reply_message_safe(message, f"❌ {quota_msg}")
            return
        
        # Initialize processing message
        processing_msg = await reply_message_safe(message, "📂 Processing file...")
        
        try:
            # Process file (Download & Store)
            file_path, file_record = await file_service.process_file(
                bot=context.bot,
                file_id=target_document.file_id,
                chat_id=chat_id,
                user_id=message.from_user.id,
                file_name=target_document.file_name,
                file_unique_id=target_document.file_unique_id,
                file_size=target_document.file_size,
                caption=message.caption or ""
            )
            
            # Determine how to handle the file content
            mime_type = file_record.file_type
            
            # 1. Text Files: Read content and append to prompt
            text_mimes = [
                'text/plain', 'application/json', 'text/csv', 'text/markdown', 
                'text/x-python', 'text/javascript', 'text/html', 'text/xml'
            ]
            
            if mime_type in text_mimes or mime_type.startswith('text/'):
                try:
                    with open(file_path, 'r', encoding='utf-8') as f:
                        content = f.read()
                    
                    # Append content to user message
                    context_info = f"\n\n[File Content: {target_document.file_name}]\n```\n{content}\n```\n"
                    user_message = (user_message or "Analyze this file.") + context_info
                    
                    # Recalculate full_user_message
                    full_user_message = f"[{user_name}]: {user_message}{reply_context}"
                    
                except Exception as e:
                    logger.error(f"Failed to read text file: {e}")
                    await edit_message_safe(processing_msg, f"⚠️ Failed to read text file: {e}")
                    return

            # 2. PDF/Other Documents: Treat as generic media (base64)
            elif mime_type == 'application/pdf':
                try:
                    with open(file_path, 'rb') as f:
                        file_bytes = f.read()
                    
                    # Add PDF to media items
                    all_media_items.append((
                        base64.b64encode(file_bytes).decode('utf-8'),
                        mime_type,
                        'file',
                        target_document.file_name
                    ))
                    
                    if not user_message:
                        user_message = "Analyze this PDF document."
                        full_user_message = f"[{user_name}]: {user_message}{reply_context}"
                        
                except Exception as e:
                     logger.error(f"Failed to read PDF file: {e}")
                     await edit_message_safe(processing_msg, f"⚠️ Failed to read PDF file: {e}")
                     return
            
            else:
                await edit_message_safe(processing_msg, f"⚠️ Unsupported file type for AI analysis: {mime_type}. File stored successfully.")
                return

            # Cleanup processing message
            await processing_msg.delete()

        except Exception as e:
            logger.error(f"File processing error: {e}")
            await edit_message_safe(processing_msg, f"❌ File processing failed: {str(e)}")
            return
        

    # Validate message
    if not user_message and not all_media_items:
        await reply_message_safe(message, "⚠️ I can only understand text, photos, audio, and video.")
        return

    # Check if we should skip AI (for /p command)
    if context.user_data.get("skip_ai_once"):
        context.user_data["skip_ai_once"] = False
        # Message already logged above for groups
        if chat_type == constants.ChatType.PRIVATE:
            # Extract metadata for private chat
            sender = message.from_user
            chat = message.chat
            
            await conversation_service.add_user_message(
                chat_id, 
                full_user_message, 
                message_id=message.message_id,
                sender_id=sender.id,
                sender_username=sender.username,
                sender_first_name=sender.first_name,
                sender_full_name=f"{sender.first_name} {sender.last_name or ''}".strip(),
                chat_id=chat.id,
                chat_type=chat.type,
                chat_username=chat.username,
            )
        return

    # Add message to conversation history (for private chats)
    if chat_type == constants.ChatType.PRIVATE:
        # Extract metadata
        sender = message.from_user
        chat = message.chat
        
        await conversation_service.add_user_message(
            chat_id, 
            full_user_message, 
            message_id=message.message_id,
            sender_id=sender.id,
            sender_username=sender.username,
            sender_first_name=sender.first_name,
            sender_full_name=f"{sender.first_name} {sender.last_name or ''}".strip(),
            chat_id=chat.id,
            chat_type=chat.type,
            chat_username=chat.username,
        )

    # Send thinking indicator
    status_msg = await reply_message_safe(message, "Thinking... 💭")

    # --- 4. Get history limit from config ---
    config_service = ConfigService()
    if chat_type == constants.ChatType.PRIVATE:
        history_limit = await config_service.get_history_limit()
    else:
        history_limit = await config_service.get_group_history_limit()

    # --- 5. Prepare input and call AI Manager ---
    try:
        # 构建多模态输入
        input_data = MultimodalInput(text=user_message)
        
        for m_data, m_mime, m_type, m_filename in all_media_items:
            if m_type == 'image':
                input_data.add_image(m_data, mime_type=m_mime)
            elif m_type == 'audio':
                input_data.add_audio(m_data, mime_type=m_mime)
            elif m_type == 'video':
                input_data.add_video(m_data, mime_type=m_mime)
            elif m_type == 'file':
                input_data.add_file_base64(m_data, mime_type=m_mime, filename=m_filename or "document")
        
        # 获取对话历史
        history = await conversation_service.get_messages_for_api(
            chat_id, 
            limit=history_limit
        )
        
        # 调用AI Manager（流式）
        response_parts = {"thinking": "", "answer": ""}
        last_update_time = time.time()
        # 从配置获取更新间隔（默认 3.5 秒，符合 Telegram 官方建议）
        update_interval = await config_service.get_streaming_update_interval()

        async for response in ai_manager.get_response(
            input_data=input_data,
            chat_id=chat_id,
            stream=True,
            conversation_history=history
        ):
            # 累积响应
            response_parts["thinking"] = response.thinking
            response_parts["answer"] = response.answer
            
            # 构建纯文本显示 (流式更新时不转换Markdown，避免不完整标记问题)
            if response.has_thinking:
                # 显示纯文本，不做格式转换
                plain_display = f'💭 Thinking Process:\n{response.thinking}\n\n{response.answer}'
            else:
                plain_display = response.display_answer

            # 定期更新消息（使用纯文本，无parse_mode）
            current_time = time.time()
            if current_time - last_update_time >= update_interval:
                try:
                    await edit_message_safe(
                        status_msg, plain_display[:4096], parse_mode=None
                    )
                    last_update_time = current_time
                except Exception as e:
                    logger.warning(f"Failed to update message: {e}")

        # 最终更新：转换为HTML格式显示
        try:
            # 只在最终响应时转换Markdown为HTML
            if response_parts["thinking"] or response_parts["answer"]:
                if response_parts["thinking"]:
                    thinking_html = markdown_to_html(response_parts["thinking"])
                    answer_html = markdown_to_html(response_parts["answer"])
                    final_display = f'<blockquote expandable>💭 <b>Thinking Process:</b>\n{thinking_html}</blockquote>\n\n{answer_html}'
                else:
                    final_display = markdown_to_html(response_parts["answer"] or response_parts["thinking"])
            else:
                final_display = "No response received."
            
            if len(final_display) <= 4096:
                await edit_message_safe(status_msg, final_display, parse_mode="HTML")
            else:
                # Split into chunks
                chunks = _chunk_message(final_display, 4096)
                
                # Edit first chunk into status_msg
                if chunks:
                    await edit_message_safe(status_msg, chunks[0], parse_mode="HTML")
                
                # Send remaining chunks
                for chunk in chunks[1:]:
                    await reply_message_safe(message, chunk, parse_mode="HTML")
                    
        except Exception as e:
            logger.warning(f"Failed to final update message: {e}")

        # Store assistant response
        plain_response = response_parts["answer"] if response_parts["answer"] else response_parts["thinking"]
        await conversation_service.add_assistant_message(
            chat_id, plain_response, message_id=status_msg.message_id
        )

    except Exception as e:
        logger.error(f"Error in chat_message: {e}", exc_info=True)
        await status_msg.edit_text(f"❌ Error: {str(e)}")




async def clear_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Clear conversation history."""
    conversation_service = ConversationService()
    permission_service = PermissionService()

    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type

    # Permission check for groups - only Telegram group admins can use /clear
    if chat_type in [constants.ChatType.GROUP, constants.ChatType.SUPERGROUP]:
        try:
            member = await context.bot.get_chat_member(chat_id, user_id)
            if member.status not in ["administrator", "creator"]:
                await reply_message_safe(
                    update.message,
                    "⛔ Sorry, only group administrators can clear conversation history."
                )
                return
        except Exception as e:
            logger.error(f"Error checking group admin status: {e}")
            # Don't expose detailed error to user
            await reply_message_safe(
                update.message,
                "⛔ Permission check failed. Please ensure bot has proper permissions."
            )
            return

    # Clear conversation
    deleted_count = await conversation_service.clear_conversation(chat_id)

    await reply_message_safe(
        update.message,
        f"✅ Conversation history cleared ({deleted_count} messages deleted)."
    )


async def new_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new conversation (private chat only)."""
    conversation_service = ConversationService()

    chat_type = update.effective_chat.type

    if chat_type != constants.ChatType.PRIVATE:
        await reply_message_safe(
            update.message,
            "⚠️ The /new command is only available in private chats. Use /clear to clear history in groups."
        )
        return

    chat_id = update.effective_chat.id
    deleted_count = await conversation_service.clear_conversation(chat_id)

    await reply_message_safe(
        update.message,
        f"🆕 Started a fresh conversation! ({deleted_count} messages cleared)"
    )


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /s command for web search."""
    from src.services.search_service import SearchService
    
    chat_id = update.effective_chat.id
    message = update.effective_message
    
    # Parse search query from command arguments
    query = " ".join(context.args) if context.args else ""
    
    if not query:
        await reply_message_safe(
            message,
            "⚠️ 请提供搜索关键词\n\n使用方法: /s <关键词>\n例如: /s 最新 AI 新闻"
        )
        return
    
    # Show searching status
    status_msg = await reply_message_safe(message, "🔍 Searching...")
    
    try:
        # Execute search
        search_service = SearchService()
        result = await search_service.search(query, chat_id)
        
        # Display results
        await edit_message_safe(status_msg, result, parse_mode="HTML")
        
        logger.info(f"Search completed for query: {query}")
        
    except ValueError as e:
        # Validation errors
        await edit_message_safe(status_msg, f"⚠️ {str(e)}")
    except Exception as e:
        # Network or other errors
        logger.error(f"Search error: {e}", exc_info=True)
        await edit_message_safe(
            status_msg,
            "❌ 搜索失败，请稍后重试。\n\n可能的原因：网络问题或服务暂时不可用。"
        )

