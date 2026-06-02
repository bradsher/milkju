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
from src.telegram.utils.message_sender import MessageSender, telegram_escape

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
    def save_code_block(match):
        code_blocks.append(f'<pre>{match.group(1)}</pre>')
        return f'XCODEBLOCK{len(code_blocks)-1}X'
    
    text = re.sub(r'```([^`]+)```', save_code_block, text)
    
    # Replace inline code with placeholders (must have both ` markers)
    def save_inline_code(match):
        inline_codes.append(f'<code>{match.group(1)}</code>')
        return f'XINLINECODE{len(inline_codes)-1}X'
    
    text = re.sub(r'`([^`]+)`', save_inline_code, text)
    
    # Protect markdown links [text](url) to avoid formatting inside URLs or matching across links
    links = []
    def save_link(match):
        links.append((match.group(1), match.group(2)))
        return f'XLINK{len(links)-1}X'
        
    text = re.sub(r'\[([^\]]+)\]\(([^)]+)\)', save_link, text)
    
    # Protect plain URLs from being broken by underscores or asterisks
    urls = []
    def save_url(match):
        urls.append(match.group(0))
        return f'XURL{len(urls)-1}X'
        
    text = re.sub(r'https?://[^\s<>"]+', save_url, text)
    
    # Now process other formatting (they won't interfere with code, URLs, or links)
    
    # Headers (# to ######) - convert to bold text since Telegram doesn't support <h1>-<h6>
    text = re.sub(r'^(\s*)#{1,6}\s+(.+?)$', r'\1<b>\2</b>', text, flags=re.MULTILINE)
    
    # Bold Italic (***text***)
    text = re.sub(r'\*\*\*([^*]+?)\*\*\*', r'<b><i>\1</i></b>', text)
    # Bold Italic (___text___)
    text = re.sub(r'___([^_]+?)___', r'<b><i>\1</i></b>', text)
    
    # Bold (**text** - non-greedy, no ** inside)
    text = re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', text)
    
    # Bold (__text__ - non-greedy, no __ inside)
    text = re.sub(r'__([^_]+?)__', r'<b>\1</b>', text)
    
    # Italic (*text* - must not be ** and no * inside)
    text = re.sub(r'(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', text)
    
    # Italic (_text_ - must not be __ and no _ inside)  
    text = re.sub(r'(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)', r'<i>\1</i>', text)
    
    # Restore plain URLs
    for i, url in enumerate(urls):
        text = text.replace(f'XURL{i}X', url)
        
    # Restore markdown links and format their link text in isolation
    for i, (link_text, link_url) in enumerate(links):
        formatted_link_text = link_text
        formatted_link_text = re.sub(r'\*\*\*([^*]+?)\*\*\*', r'<b><i>\1</i></b>', formatted_link_text)
        formatted_link_text = re.sub(r'___([^_]+?)___', r'<b><i>\1</i></b>', formatted_link_text)
        formatted_link_text = re.sub(r'\*\*([^*]+?)\*\*', r'<b>\1</b>', formatted_link_text)
        formatted_link_text = re.sub(r'__([^_]+?)__', r'<b>\1</b>', formatted_link_text)
        formatted_link_text = re.sub(r'(?<!\*)\*(?!\*)([^*]+?)(?<!\*)\*(?!\*)', r'<i>\1</i>', formatted_link_text)
        formatted_link_text = re.sub(r'(?<!_)_(?!_)([^_]+?)(?<!_)_(?!_)', r'<i>\1</i>', formatted_link_text)
        
        # Link URL is safe because it was saved raw and not processed by bold/italic rules
        link_html = f'<a href="{link_url}">{formatted_link_text}</a>'
        text = text.replace(f'XLINK{i}X', link_html)
    
    # Restore inline codes
    for i, inline_code in enumerate(inline_codes):
        text = text.replace(f'XINLINECODE{i}X', inline_code)
    
    # Restore code blocks
    for i, code_block in enumerate(code_blocks):
        text = text.replace(f'XCODEBLOCK{i}X', code_block)
    
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

• /summary_model - 设置总结模型 / Set summary model
  <i>打开Summary模型选择菜单 / Opens summary model selection menu</i>
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
    
    await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=help_text.strip(), reply_to_message_id=update.message.message_id)


async def cancel_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Cancel any ongoing conversation or input wait."""
    if context.user_data.get('awaiting_config'):
        context.user_data['awaiting_config'] = None
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="🚫 Operation cancelled.", reply_to_message_id=update.message.message_id)
    else:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="🚫 Nothing to cancel.", reply_to_message_id=update.message.message_id)


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
    from src.core.infrastructure import ConfigService, ChatSettingsService
    
    # Initialize services
    conversation_service = ConversationService()
    ai_manager = AIManager()
    permission_service = PermissionService()
    settings_service = ChatSettingsService()

    user_id = update.effective_user.id
    chat_id = update.effective_chat.id
    user_name = update.effective_user.first_name

    message = update.effective_message
    user_message = message.text or message.caption or ""
    chat_type = message.chat.type
    bot_username = context.bot.username
    current_db_msg_id = None

    # --- 0. Pre-checks (Blacklist & Admin status) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
        
    config_service = ConfigService()
    is_admin = await permission_service.is_admin(user_id)

    # --- 1. Access Control (Private Chat) ---
    if chat_type == constants.ChatType.PRIVATE:
        if not is_admin:
            public_chat_enabled = await config_service.get_public_chat_enabled()
            if not public_chat_enabled:
                await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text="⛔ 抱歉，目前仅允许管理员使用私聊。", reply_to_message_id=message.message_id)
                return
            
            # Rate limit check for normal users
            from src.services.rate_limit_service import RateLimitService
            rate_limit_service = RateLimitService()
            limit = await config_service.get_public_chat_rate_limit()
            status = await rate_limit_service.check_and_record(user_id, limit)
            
            if status == "BANNED":
                return
            elif status == "RATE_LIMITED":
                await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text=f"🛑 频率限制：你已达到普通用户上限（{limit}次/小时），请稍后再试。", reply_to_message_id=message.message_id)
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
                user_msg = await conversation_service.add_user_message(
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
                current_db_msg_id = user_msg.id
            except Exception as e:
                # Log error but don't crash - just save basic message without metadata
                logger.error(f"Error extracting message metadata: {e}", exc_info=True)
                try:
                    # Fallback: save message with minimal metadata
                    user_msg = await conversation_service.add_user_message(
                        chat_id,
                        f"[{user_name}]: {user_message}",
                        message_id=message.message_id,
                    )
                    current_db_msg_id = user_msg.id
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
            if context.user_data.get("skip_ai_once"):
                context.user_data["skip_ai_once"] = False
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

        if "群聊吃瓜日报" in replied_text:
            context.user_data["skip_ai_once"] = True

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
            await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text=f"❌ {quota_msg}", reply_to_message_id=message.message_id)
            return
        
        # Initialize processing message
        processing_msg_ids = await MessageSender(bot=context.bot, chat_id=chat_id).send_static(text="📂 Processing file...", reply_to_message_id=message.message_id)
        
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
                    await context.bot.edit_message_text(
                        chat_id=chat_id,
                        message_id=processing_msg_ids[0],
                        text=telegram_escape(f"⚠️ Failed to read text file: {e}"),
                        parse_mode="HTML"
                    )
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
                     await context.bot.edit_message_text(
                         chat_id=chat_id,
                         message_id=processing_msg_ids[0],
                         text=telegram_escape(f"⚠️ Failed to read PDF file: {e}"),
                         parse_mode="HTML"
                     )
                     return
            
            else:
                await context.bot.edit_message_text(
                    chat_id=chat_id,
                    message_id=processing_msg_ids[0],
                    text=telegram_escape(f"⚠️ Unsupported file type for AI analysis: {mime_type}. File stored successfully."),
                    parse_mode="HTML"
                )
                return

            # Cleanup processing message
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_msg_ids[0])

        except Exception as e:
            logger.error(f"File processing error: {e}")
            await context.bot.edit_message_text(
                chat_id=chat_id,
                message_id=processing_msg_ids[0],
                text=telegram_escape(f"❌ File processing failed: {str(e)}"),
                parse_mode="HTML"
            )
            return
        

    # Validate message
    if not user_message and not all_media_items:
        await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text="⚠️ I can only understand text, photos, audio, and video.", reply_to_message_id=message.message_id)
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
        
        user_msg = await conversation_service.add_user_message(
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
        current_db_msg_id = user_msg.id

    # Acquire per-chat lock for the AI response section
    from src.telegram.middlewares.chat_lock import get_chat_lock
    async with get_chat_lock(chat_id):

        # Send thinking indicator
        status_msg_ids = await MessageSender(bot=context.bot, chat_id=chat_id).send_static(text="Thinking... 💭", reply_to_message_id=message.message_id)

        # --- 4. Get history limit from config ---
        config_service = ConfigService()
        if chat_type == constants.ChatType.PRIVATE:
            history_limit = await config_service.get_history_limit()
        else:
            history_limit = await config_service.get_group_history_limit()

        # --- 5. Prepare input and call AI Manager ---
        try:
            # 构建多模态输入
            input_data = MultimodalInput(text=full_user_message)
            
            for m_data, m_mime, m_type, m_filename in all_media_items:
                if m_type == 'image':
                    input_data.add_image(m_data, mime_type=m_mime)
                elif m_type == 'audio':
                    input_data.add_audio(m_data, mime_type=m_mime)
                elif m_type == 'video':
                    input_data.add_video(m_data, mime_type=m_mime)
                elif m_type == 'file':
                    input_data.add_file_base64(m_data, mime_type=m_mime, filename=m_filename or "document")
            
            # 获取自定义系统提示词
            sys_prompt = await settings_service.get_system_prompt(chat_id)

            # 获取对话历史
            history = await conversation_service.get_messages_for_api(
                chat_id, 
                limit=history_limit,
                max_id=current_db_msg_id,
                system_prompt=sys_prompt
            )
            
            shared_state = {"thinking": "", "answer": "", "final_display": ""}
            
            # For non-admins, force default model isolation
            forced_model = None
            if not is_admin:
                forced_model = await config_service.get("model")
            
            async def get_stream_deltas():
                last_thinking = ""
                last_answer = ""
                thinking_started = False
                
                async for response in ai_manager.get_response(
                    input_data=input_data,
                    chat_id=chat_id,
                    stream=True,
                    conversation_history=history,
                    model=forced_model
                ):
                    delta = ""
                    
                    # Handle thinking
                    if response.thinking and response.thinking != last_thinking:
                        if not thinking_started:
                            delta += "💭 Thinking Process:\n"
                            thinking_started = True
                        delta += response.thinking[len(last_thinking):]
                        last_thinking = response.thinking
                        
                    # Handle answer
                    if response.answer and response.answer != last_answer:
                        if thinking_started and not last_answer:
                            # Add spacing after thinking
                            delta += "\n\n"
                        delta += response.answer[len(last_answer):]
                        last_answer = response.answer
                        
                    # Update shared state for final update
                    shared_state["thinking"] = response.thinking
                    shared_state["answer"] = response.answer
                    shared_state["final_display"] = f'💭 Thinking Process:\n{response.thinking}\n\n{response.answer}' if response.has_thinking else response.display_answer
                    
                    if delta:
                        yield delta

            # Delete status message before starting streaming to avoid clutter
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_msg_ids[0])
            except:
                pass

            # Use MessageSender for streaming and splitting
            sender = MessageSender(bot=context.bot, chat_id=chat_id, parse_mode="HTML")
            
            # Send streaming
            msg_ids = await sender.send_streaming(content_generator=get_stream_deltas(), reply_to_message_id=message.message_id)
            
            # Final update: Convert to HTML and update messages
            if msg_ids:
                try:
                    thinking = shared_state["thinking"]
                    answer = shared_state["answer"]
                    
                    if thinking:
                        thinking_html = markdown_to_html(thinking)
                        answer_html = markdown_to_html(answer)
                        html_display = f'<blockquote expandable>💭 <b>Thinking Process:</b>\n{thinking_html}</blockquote>\n\n{answer_html}'
                    else:
                        html_display = markdown_to_html(shared_state["final_display"])
                    
                    # Use HTMLSplitter to split the full HTML to preserve formatting
                    from src.telegram.utils.message_splitter import HTMLSplitter
                    from src.core.message_config import SOFT_LIMIT, HARD_LIMIT
                    
                    splitter = HTMLSplitter(soft_limit=SOFT_LIMIT, hard_limit=HARD_LIMIT)
                    chunks = splitter.split(html_display)
                    
                    # Update existing messages or send new ones (per-message error handling)
                    for i, chunk_dict in enumerate(chunks):
                        chunk_text = chunk_dict["text"]
                        try:
                            if i < len(msg_ids):
                                # Edit existing message
                                await context.bot.edit_message_text(
                                    chat_id=chat_id,
                                    message_id=msg_ids[i],
                                    text=chunk_text,
                                    parse_mode="HTML"
                                )
                            else:
                                # Send new message if chunks exceed existing messages
                                new_msg = await context.bot.send_message(
                                    chat_id=chat_id,
                                    text=chunk_text,
                                    parse_mode="HTML"
                                )
                                msg_ids.append(new_msg.message_id)
                        except Exception as e:
                            logger.warning(f"Failed to update message chunk {i}: {e}")
                            
                    # Delete any leftover messages if HTML splitting resulted in fewer chunks
                    if len(chunks) < len(msg_ids):
                        for extra_msg_id in msg_ids[len(chunks):]:
                            try:
                                await context.bot.delete_message(chat_id=chat_id, message_id=extra_msg_id)
                            except Exception as e:
                                logger.warning(f"Failed to delete extra message {extra_msg_id}: {e}")
                        # Trim the msg_ids list to match actual chunks
                        msg_ids = msg_ids[:len(chunks)]
                            
                except Exception as e:
                    logger.warning(f"Failed to final update message to HTML: {e}")
                    
            # Store assistant response
            plain_response = shared_state["answer"] or shared_state["thinking"] or "No response received."
            msg_ids_str = ",".join(map(str, msg_ids)) if msg_ids else None
            first_msg_id = msg_ids[0] if msg_ids else status_msg.message_id
            
            await conversation_service.add_assistant_message(
                chat_id, plain_response, message_id=first_msg_id, message_ids=msg_ids_str
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
                await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ Sorry, only group administrators can clear conversation history.", reply_to_message_id=update.message.message_id)
                return
        except Exception as e:
            logger.error(f"Error checking group admin status: {e}")
            # Don't expose detailed error to user
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ Permission check failed. Please ensure bot has proper permissions.", reply_to_message_id=update.message.message_id)
            return

    # Clear conversation
    deleted_count = await conversation_service.clear_conversation(chat_id)

    await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"✅ Conversation history cleared ({deleted_count} messages deleted).", reply_to_message_id=update.message.message_id)


async def new_conversation_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Start a new conversation (private chat only)."""
    conversation_service = ConversationService()

    chat_type = update.effective_chat.type

    if chat_type != constants.ChatType.PRIVATE:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ The /new command is only available in private chats. Use /clear to clear history in groups.", reply_to_message_id=update.message.message_id)
        return

    chat_id = update.effective_chat.id
    deleted_count = await conversation_service.clear_conversation(chat_id)

    await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"🆕 Started a fresh conversation! ({deleted_count} messages cleared)", reply_to_message_id=update.message.message_id)


async def search_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /s command for web search."""
    from src.services.search_service import SearchService
    
    chat_id = update.effective_chat.id
    user_id = update.effective_user.id
    chat_type = update.effective_chat.type
    message = update.effective_message
    
    from src.services.permission_service import PermissionService
    permission_service = PermissionService()
    
    # --- 0. Pre-checks (Blacklist & Admin status) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
        
    from src.core.infrastructure.config_service import ConfigService
    config_service = ConfigService()
    is_admin = await permission_service.is_admin(user_id)

    # --- 1. Access Control (Private Chat) ---
    if chat_type == constants.ChatType.PRIVATE:
        if not is_admin:
            public_chat_enabled = await config_service.get_public_chat_enabled()
            if not public_chat_enabled:
                await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text="⛔ 抱歉，目前仅允许管理员使用私聊。", reply_to_message_id=message.message_id)
                return
            
            # Rate limit check for normal users
            from src.services.rate_limit_service import RateLimitService
            rate_limit_service = RateLimitService()
            limit = await config_service.get_public_chat_rate_limit()
            status = await rate_limit_service.check_and_record(user_id, limit)
            
            if status == "BANNED":
                return
            elif status == "RATE_LIMITED":
                await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text=f"🛑 频率限制：你已达到普通用户上限（{limit}次/小时），请稍后再试。", reply_to_message_id=message.message_id)
                return
    
    # Parse search query from command arguments
    query = " ".join(context.args) if context.args else ""
    
    if not query:
        await MessageSender(bot=message.get_bot(), chat_id=message.chat_id, parse_mode="HTML").send_static(text="⚠️ 请提供搜索关键词\n\n使用方法: /s <关键词>\n例如: /s 最新 AI 新闻", reply_to_message_id=message.message_id)
        return
    
    # Show searching status
    status_msg_ids = await MessageSender(bot=context.bot, chat_id=chat_id).send_static(text="🔍 Searching...", reply_to_message_id=message.message_id)
    
    # Acquire per-chat lock for the search + AI summary section
    from src.telegram.middlewares.chat_lock import get_chat_lock
    async with get_chat_lock(chat_id):

        try:
            # Execute search
            search_service = SearchService()
            
            # For non-admins, force default model isolation
            forced_model = None
            if not is_admin:
                forced_model = await config_service.get("model")
                
            result = await search_service.search(query, chat_id, model=forced_model)
            
            # Display results using unified sender
            sender = MessageSender(bot=context.bot, chat_id=chat_id)
            await sender.send_static(text=result, reply_to_message_id=message.message_id)
            
            # Delete status message
            try:
                await context.bot.delete_message(chat_id=chat_id, message_id=status_msg_ids[0])
            except Exception as e:
                logger.warning(f"Failed to delete status message: {e}")
            
            logger.info(f"Search completed for query: {query}")
            
        except ValueError as e:
            # Validation errors
            await context.bot.edit_message_text(text=f"⚠️ {str(e)}", chat_id=chat_id, message_id=status_msg_ids[0])
        except Exception as e:
            # Network or other errors
            logger.error(f"Search error: {e}", exc_info=True)
            await context.bot.edit_message_text(text="❌ 搜索失败，请稍后重试。\n\n可能的原因：网络问题或服务暂时不可用。", chat_id=chat_id, message_id=status_msg_ids[0])

