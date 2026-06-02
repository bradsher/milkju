"""Telegram handlers for NovelAI image generation commands."""

from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.services.image_service import ImageService
from src.services.author_preset_service import AuthorPresetService
from src.telegram.utils.message_sender import MessageSender, telegram_escape

logger = logging.getLogger(__name__)

# Bilingual messages
MESSAGES = {
    "generating": "🎨 正在生成图片，请稍候... / Generating image, please wait...\n\n⏱️ 这可能需要 10-30 秒 / This may take 10-30 seconds",
    "disabled": "⚠️ NovelAI 功能已被管理员禁用 / NovelAI feature is currently disabled by admin",
    "no_token": "❌ NovelAI API 未配置 / NovelAI API not configured\n\n请联系管理员设置 NAI_API_TOKEN / Please contact admin to set NAI_API_TOKEN",
    "rate_limit": "⏳ 生成次数已达限制 ({used}/{limit} 每小时) / Generation limit reached ({used}/{limit} per hour)\n\n请稍后再试 / Please try again later",
    "no_credits": "💳 Anlas 余额不足 / Insufficient Anlas credits\n\n请充值或启用 Anlas-Free 模式 / Please top up or enable Anlas-Free mode",
    "timeout": "⏱️ 生成超时，请重试 / Generation timeout, please try again",
    "server_error": "🔄 NovelAI 服务器错误，请稍后重试 / Server error, please try again in a moment",
    "sdk_not_installed": "❌ NovelAI SDK 未安装 / SDK not installed\n\n请运行 pip install novelai-python",
    "invalid_token": "🔑 NovelAI API Token 无效 / Invalid NovelAI API token\n\n请联系管理员检查配置 / Please contact admin to check configuration",
    "prompt_too_long": "⚠️ 提示词过长已截断至 500 字符 / Prompt truncated to 500 characters",
    "usage": (
        "📝 <b>NovelAI 图片生成 / Image Generation</b>\n\n"
        "<b>用法 / Usage:</b>\n"
        "<code>/nai &lt;prompt&gt;</code>\n\n"
        "<b>示例 / Example:</b>\n"
        "<code>/nai 1girl, sitting in cafe, looking out window, warm lighting</code>\n\n"
        "💡 <b>提示 / Tips:</b>\n"
        "• 使用英文提示词效果更好 / English prompts work better\n"
        "• 用逗号分隔不同元素 / Separate elements with commas\n"
        "• 指定风格、构图、光线 / Specify style, composition, lighting"
    ),
    "success": "✅ 图片生成成功 / Image generated successfully",
    "error": "❌ 生成失败 / Generation failed: {error}",
    "naia_usage": (
        "📝 <b>NovelAI with Author Preset / 使用作者预设</b>\n\n"
        "<b>用法 / Usage:</b>\n"
        "<code>/naia &lt;preset_name&gt; &lt;prompt&gt;</code>\n\n"
        "<b>示例 / Example:</b>\n"
        "<code>/naia mystyle 1girl, sitting in cafe</code>\n\n"
        "💡 <b>说明 / Info:</b>\n"
        "• 预设名称由管理员配置 / Preset names are configured by admins\n"
        "• 作者串会自动添加到提示词前 / Author string is prepended to prompt"
    ),
    "preset_not_found": "❌ 预设 <code>{name}</code> 不存在 / Preset <code>{name}</code> not found",
    "preset_disabled": "⚠️ 预设 <code>{name}</code> 已被禁用 / Preset <code>{name}</code> is disabled",
}


async def nai_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /nai command for NovelAI image generation.
    
    Usage: /nai <prompt>
    Example: /nai 1girl, cafe, window, warm lighting
    
    Args:
        update: Telegram update object.
        context: Telegram context object.
    """
    from src.services.permission_service import PermissionService
    permission_service = PermissionService()
    chat = update.effective_chat
    user_id = update.effective_user.id
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
    
    if chat.type == "private":
        if not await permission_service.is_admin(user_id):
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ 权限不足：仅管理员可以生图。", reply_to_message_id=update.message.message_id)
            return

    # Check if user provided prompt
    if not context.args:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["usage"], reply_to_message_id=update.message.message_id)
        return

    # Get prompt from arguments
    prompt = ' '.join(context.args)
    
    # Validate and truncate prompt length (500 chars ≈ 225 tokens safe limit)
    MAX_PROMPT_LENGTH = 500
    prompt_truncated = False
    if len(prompt) > MAX_PROMPT_LENGTH:
        prompt = prompt[:MAX_PROMPT_LENGTH]
        prompt_truncated = True
        logger.info(f"Truncated prompt to {MAX_PROMPT_LENGTH} characters")

    user_id = update.effective_user.id
    
    # Initialize service
    image_service = ImageService()
    
    # Check if feature is enabled
    try:
        if not await image_service.is_enabled():
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["disabled"], reply_to_message_id=update.message.message_id)
            return
    except Exception as e:
        logger.error(f"Error checking if NovelAI is enabled: {e}")
        # Continue anyway, will fail later if needed

    # Check rate limit
    try:
        allowed, used_count, limit = await image_service.check_rate_limit(user_id)
        if not allowed:
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["rate_limit"].format(used=used_count, limit=limit), reply_to_message_id=update.message.message_id)
            return
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")
        # Continue anyway

    # Send processing message
    processing_msg_ids = await MessageSender(bot=context.bot, chat_id=update.effective_chat.id, parse_mode="HTML").send_static(
        text=MESSAGES["generating"],
        reply_to_message_id=update.message.message_id
    )

    # Acquire per-chat lock for image generation
    from src.telegram.middlewares.chat_lock import get_chat_lock
    async with get_chat_lock(update.effective_chat.id):

        try:
            # Generate image
            image_bytes = await image_service.generate_image(
                prompt=prompt,
                user_id=user_id
            )
            
            # Record generation for rate limiting
            await image_service.record_generation(user_id)
            
            # Delete processing message
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg_ids[0])
            except Exception as e:
                logger.warning(f"Failed to delete processing message: {e}")
            
            # Build caption - escape Markdown special characters in prompt
            safe_prompt = telegram_escape(prompt[:200])
            caption = f"🎨 <b>NovelAI</b>\n\n"
            if prompt_truncated:
                caption += f"⚠️ {MESSAGES['prompt_too_long']}\n\n"
            caption += f"<b>Prompt:</b> {safe_prompt}{'...' if len(prompt) > 200 else ''}"
            
            # Send image
            await update.message.reply_photo(
                photo=image_bytes,
                caption=caption,
                parse_mode="HTML"
            )
            
            logger.info(f"Successfully sent generated image to user {user_id}")
            
        except ValueError as e:
            # User input validation errors or API configuration errors
            error_message = str(e)
            
            # Map to appropriate message
            if "not configured" in error_message.lower():
                message = MESSAGES["no_token"]
            elif "sdk not installed" in error_message.lower():
                message = MESSAGES["sdk_not_installed"]
            elif "disabled" in error_message.lower():
                message = MESSAGES["disabled"]
            elif "invalid" in error_message.lower() and "token" in error_message.lower():
                message = MESSAGES["invalid_token"]
            elif "insufficient" in error_message.lower() or "anlas" in error_message.lower():
                message = MESSAGES["no_credits"]
            elif "server error" in error_message.lower():
                message = MESSAGES["server_error"]
            else:
                message = MESSAGES["error"].format(error=telegram_escape(str(e)))
            
            await context.bot.edit_message_text(text=message, chat_id=update.effective_chat.id, message_id=processing_msg_ids[0], parse_mode="HTML")
            
        except TimeoutError as e:
            # Generation timeout
            logger.error(f"NovelAI generation timeout: {e}")
            await context.bot.edit_message_text(text=MESSAGES["timeout"], chat_id=update.effective_chat.id, message_id=processing_msg_ids[0], parse_mode="HTML")
            
        except Exception as e:
            # General errors
            logger.error(f"NovelAI generation error: {e}", exc_info=True)
            
            error_msg = MESSAGES["error"].format(error="Internal error. Please try again or contact admin.")
            
            try:
                await context.bot.edit_message_text(text=error_msg, chat_id=update.effective_chat.id, message_id=processing_msg_ids[0], parse_mode="HTML")
            except:
                await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=error_msg, reply_to_message_id=update.message.message_id)


async def naia_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /naia command for NovelAI with author preset.
    
    Usage: /naia <preset_name> <prompt>
    Example: /naia mystyle 1girl, cafe, window, warm lighting
    
    The preset's author string is prepended to the user's prompt.
    
    Args:
        update: Telegram update object.
        context: Telegram context object.
    """
    from src.services.permission_service import PermissionService
    permission_service = PermissionService()
    chat = update.effective_chat
    user_id = update.effective_user.id
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
    
    if chat.type == "private":
        if not await permission_service.is_admin(user_id):
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ 权限不足：仅管理员可以生图。", reply_to_message_id=update.message.message_id)
            return

    # Check if user provided enough args
    if len(context.args) < 2:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["naia_usage"], reply_to_message_id=update.message.message_id)
        return

    preset_name = context.args[0]
    prompt = ' '.join(context.args[1:])
    
    # Lookup preset
    preset_service = AuthorPresetService()
    preset = await preset_service.get_preset_by_name(preset_name)
    
    if not preset:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["preset_not_found"].format(name=preset_name), reply_to_message_id=update.message.message_id)
        return
    
    if not preset.is_active:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["preset_disabled"].format(name=preset_name), reply_to_message_id=update.message.message_id)
        return
    
    # Combine: author_string, user_prompt
    full_prompt = f"{preset.content}, {prompt}"
    
    # Validate and truncate combined prompt length
    MAX_PROMPT_LENGTH = 500
    prompt_truncated = False
    if len(full_prompt) > MAX_PROMPT_LENGTH:
        # Try to keep as much of user prompt as possible
        available_for_user = MAX_PROMPT_LENGTH - len(preset.content) - 2  # -2 for ", "
        if available_for_user > 50:
            prompt = prompt[:available_for_user]
            full_prompt = f"{preset.content}, {prompt}"
        else:
            full_prompt = full_prompt[:MAX_PROMPT_LENGTH]
        prompt_truncated = True
        logger.info(f"Truncated combined prompt to {MAX_PROMPT_LENGTH} characters")

    user_id = update.effective_user.id
    
    # Initialize service
    image_service = ImageService()
    
    # Check if feature is enabled
    try:
        if not await image_service.is_enabled():
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["disabled"], reply_to_message_id=update.message.message_id)
            return
    except Exception as e:
        logger.error(f"Error checking if NovelAI is enabled: {e}")

    # Check rate limit
    try:
        allowed, used_count, limit = await image_service.check_rate_limit(user_id)
        if not allowed:
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=MESSAGES["rate_limit"].format(used=used_count, limit=limit), reply_to_message_id=update.message.message_id)
            return
    except Exception as e:
        logger.error(f"Error checking rate limit: {e}")

    # Send processing message
    processing_msg_ids = await MessageSender(bot=context.bot, chat_id=update.effective_chat.id, parse_mode="HTML").send_static(
        text=MESSAGES["generating"],
        reply_to_message_id=update.message.message_id
    )

    # Acquire per-chat lock for image generation
    from src.telegram.middlewares.chat_lock import get_chat_lock
    async with get_chat_lock(update.effective_chat.id):

        try:
            # Generate image with combined prompt
            image_bytes = await image_service.generate_image(
                prompt=full_prompt,
                user_id=user_id
            )
            
            # Record generation for rate limiting
            await image_service.record_generation(user_id)
            
            # Delete processing message
            try:
                await context.bot.delete_message(chat_id=update.effective_chat.id, message_id=processing_msg_ids[0])
            except Exception as e:
                logger.warning(f"Failed to delete processing message: {e}")
            
            safe_prompt = telegram_escape(prompt[:200])
            safe_preset_name = telegram_escape(preset_name)
            caption = f"🎨 <b>NovelAI</b> (preset: <code>{safe_preset_name}</code>)\n\n"
            if prompt_truncated:
                caption += f"⚠️ {MESSAGES['prompt_too_long']}\n\n"
            caption += f"<b>Prompt:</b> {safe_prompt}{'...' if len(prompt) > 200 else ''}"
            
            # Send image
            await update.message.reply_photo(
                photo=image_bytes,
                caption=caption,
                parse_mode="HTML"
            )
            
            logger.info(f"Successfully sent generated image with preset '{preset_name}' to user {user_id}")
            
        except ValueError as e:
            error_message = str(e)
            
            if "not configured" in error_message.lower():
                message = MESSAGES["no_token"]
            elif "sdk not installed" in error_message.lower():
                message = MESSAGES["sdk_not_installed"]
            elif "disabled" in error_message.lower():
                message = MESSAGES["disabled"]
            elif "invalid" in error_message.lower() and "token" in error_message.lower():
                message = MESSAGES["invalid_token"]
            elif "insufficient" in error_message.lower() or "anlas" in error_message.lower():
                message = MESSAGES["no_credits"]
            elif "server error" in error_message.lower():
                message = MESSAGES["server_error"]
            else:
                message = MESSAGES["error"].format(error=telegram_escape(str(e)))
            
            await context.bot.edit_message_text(text=message, chat_id=update.effective_chat.id, message_id=processing_msg_ids[0], parse_mode="HTML")
            
        except TimeoutError as e:
            logger.error(f"NovelAI generation timeout: {e}")
            await context.bot.edit_message_text(text=MESSAGES["timeout"], chat_id=update.effective_chat.id, message_id=processing_msg_ids[0], parse_mode="HTML")
            
        except Exception as e:
            logger.error(f"NovelAI generation error: {e}", exc_info=True)
            
            error_msg = MESSAGES["error"].format(error="Internal error. Please try again or contact admin.")
            
            try:
                await context.bot.edit_message_text(text=error_msg, chat_id=update.effective_chat.id, message_id=processing_msg_ids[0], parse_mode="HTML")
            except:
                await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=error_msg, reply_to_message_id=update.message.message_id)
