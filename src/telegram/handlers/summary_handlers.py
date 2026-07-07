"""Summary handlers for chat summarization."""

from __future__ import annotations

from telegram import Update, constants
from telegram.ext import ContextTypes
import logging
import re

# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ChatSettingsService, ConfigService
# Import from services (Layer 3)
from src.services import SummaryService, PermissionService
from src.telegram.utils.message_sender import MessageSender, telegram_escape

logger = logging.getLogger(__name__)


async def summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Summarize chat history for a specific time range.

    Usage: /summary 1d 2h 30m [Language]
    Permissions: Group Admin or Bot Admin (configurable)
    """
    summary_service = SummaryService()
    permission_service = PermissionService()
    config_service = ConfigService()

    user_id = update.effective_user.id
    chat = update.effective_chat
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users

    # 1. Permission Check
    perm_required = await config_service.is_summary_permission_required()

    if chat.type == constants.ChatType.PRIVATE:
        if not await permission_service.is_bot_admin(user_id):
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ Permission Denied. Only Admins can use this command.", reply_to_message_id=update.message.message_id)
            return
    elif perm_required and not await permission_service.is_group_admin(update):
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ Permission Denied. Only Admins can use this command.", reply_to_message_id=update.message.message_id)
        return

    # 2. Parse Time Range and Language
    if not context.args:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="Markdown").send_static(text="⚠️ Usage: `/summary <time> [language]` (e.g., `/summary 1d English`)", reply_to_message_id=update.message.message_id)
        return

    args = context.args
    language = None

    # Check if last arg is time format or language
    if not re.match(r"^\d+[dhm]$", args[-1].lower()):
        language = args[-1]
        time_args = args[:-1]
    else:
        time_args = args

    if not time_args:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ Please specify a time range.", reply_to_message_id=update.message.message_id)
        return

    time_str = " ".join(time_args).lower()

    # Parse time
    total_seconds = 0
    matches = re.findall(r"(\d+)\s*([dhm])", time_str)

    if not matches:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="Markdown").send_static(text="⚠️ Invalid format. Use d (days), h (hours), m (minutes). Example: `/summary 1d 2h`", reply_to_message_id=update.message.message_id)
        return

    for value, unit in matches:
        value = int(value)
        if unit == "d":
            total_seconds += value * 86400
        elif unit == "h":
            total_seconds += value * 3600
        elif unit == "m":
            total_seconds += value * 60

    if total_seconds == 0:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ Time range must be greater than 0.", reply_to_message_id=update.message.message_id)
        return

    if total_seconds > 86400:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ Summary is limited to the last 24 hours.", reply_to_message_id=update.message.message_id)
        return

    status_msg_ids = await MessageSender(bot=context.bot, chat_id=chat.id).send_static(text="🔄 Generating summary... ⏳", reply_to_message_id=update.message.message_id)

    # Acquire per-chat lock for summary generation
    from src.telegram.middlewares.chat_lock import chat_lock_with_timeout
    import asyncio
    
    try:
        async with chat_lock_with_timeout(chat.id, timeout=60.0):

            # 3. Generate summary
            try:
                hours = total_seconds / 3600
                summary = await summary_service.generate_summary(
                    chat_id=chat.id, 
                    hours=int(hours), 
                    language=language,
                    time_str=time_str  # Pass original time string to avoid recalculation
                )

                if "No messages found" in summary:
                    await context.bot.edit_message_text(
                        chat_id=chat.id,
                        message_id=status_msg_ids[0],
                        text="📭 No messages found in the specified time range."
                    )
                    return

                # Use unified sender to support splitting
                sender = MessageSender(bot=context.bot, chat_id=chat.id)
                await sender.send_static(text=summary, reply_to_message_id=update.message.message_id)
                
                # Delete status message
                try:
                    await context.bot.delete_message(chat_id=chat.id, message_id=status_msg_ids[0])
                except Exception as e:
                    logger.warning(f"Failed to delete status message: {e}")

            except Exception as e:
                logger.error(f"Error generating summary: {e}", exc_info=True)
                await context.bot.edit_message_text(
                    chat_id=chat.id,
                    message_id=status_msg_ids[0],
                    text=telegram_escape(f"❌ Error generating summary: {str(e)}"),
                    parse_mode="HTML"
                )
    except asyncio.TimeoutError:
        logger.warning(f"Summary generation timeout acquiring lock for chat {chat.id}")
        await context.bot.edit_message_text(
            chat_id=chat.id,
            message_id=status_msg_ids[0],
            text="⏳ 服务器繁忙：当前群组已有总结任务正在运行，请稍后再试。"
        )


async def auto_summary_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Configure auto-summary for this chat.

    New Usage:
    - /auto_summary <time1> [time2] [pin]
        time1: required, e.g. "10:00" or "9:30"
        time2: optional second slot. If provided, each trigger summarizes the previous 12h.
               If omitted, summarizes the previous 24h at time1.
        pin:   optional 1 or 0 (default 0). If 1, pins the message when sent successfully.
    - /auto_summary off     - Disable auto-summary
    - /auto_summary         - Check current status
    """
    settings_service = ChatSettingsService()
    
    from src.services.permission_service import PermissionService
    permission_service = PermissionService()
    
    chat = update.effective_chat
    user_id = update.effective_user.id
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users

    # Permission Check: Group Admin only
    
    if chat.type == constants.ChatType.PRIVATE:
        if not await permission_service.is_bot_admin(user_id):
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ Permission Denied. Only Admins can configure auto-summary.", reply_to_message_id=update.message.message_id)
            return
    elif not await permission_service.is_group_admin(update):
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ Only Group Admins can configure auto-summary.", reply_to_message_id=update.message.message_id)
        return

    def parse_time(s: str):
        """Parse flexible HH:MM / H:M time string. Returns (hour, minute) or None."""
        m = re.match(r'^(\d{1,2}):(\d{1,2})$', s.strip())
        if not m:
            return None
        h, mn = int(m.group(1)), int(m.group(2))
        if not (0 <= h <= 23 and 0 <= mn <= 59):
            return None
        return h, mn

    # No arguments - show status
    if not context.args:
        settings = await settings_service.get_auto_summary_settings(chat.id)

        if not settings or not settings.enabled:
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="📊 Auto-summary is currently <b>disabled</b>.", reply_to_message_id=update.message.message_id)
        else:
            mode = "双时间段 (每次12h)" if settings.has_two_times else "单时间段 (每次24h)"
            pin_status = "✅ 开启" if settings.pin_enabled else "❌ 关闭"
            time_info = f"⏰ 时间1: {settings.time_string} (UTC+8)"
            if settings.has_two_times:
                time_info += f"\n⏰ 时间2: {settings.time2_string} (UTC+8)"
            last_run = telegram_escape(settings.last_run_slot or settings.last_run_date or 'Never')
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"📊 Auto-summary is <b>enabled</b>\n"
                f"{time_info}\n"
                f"📐 模式: {mode}\n"
                f"📌 置顶: {pin_status}\n"
                f"🌐 Language: {settings.language or 'Default'}\n"
                f"🕐 Last run slot: {last_run}", reply_to_message_id=update.message.message_id)
        return

    # Disable auto-summary
    if context.args[0].lower() in ["off", "disable"]:
        await settings_service.disable_auto_summary(chat.id)
        await settings_service.clear_auto_summary_last_run(chat.id)
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="✅ Auto-summary disabled.", reply_to_message_id=update.message.message_id)
        return

    # --- Parse arguments: time1 [time2] [pin] ---
    args = list(context.args)

    # Parse time1 (required)
    t1 = parse_time(args[0])
    if t1 is None:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="Markdown").send_static(text="⚠️ 无法识别时间格式。请使用 HH:MM 格式，例如：`/auto_summary 10:00` 或 `/auto_summary 10:00 22:00`", reply_to_message_id=update.message.message_id)
        return

    hour1, minute1 = t1
    hour2, minute2 = None, None
    pin_enabled = False
    language = None

    # Remaining args: try to identify time2, pin, language
    remaining = args[1:]
    idx = 0

    # Try time2
    if idx < len(remaining):
        t2 = parse_time(remaining[idx])
        if t2 is not None:
            if t2 == t1:
                await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ 两个时间点不能相同。", reply_to_message_id=update.message.message_id)
                return
            hour2, minute2 = t2
            idx += 1

    # Try pin flag (0 or 1)
    if idx < len(remaining) and remaining[idx] in ("0", "1"):
        pin_enabled = remaining[idx] == "1"
        idx += 1

    # Try language (remaining text)
    if idx < len(remaining):
        language = " ".join(remaining[idx:])

    # Save settings
    await settings_service.enable_auto_summary(
        chat_id=chat.id,
        hour=hour1,
        minute=minute1,
        language=language,
        time2_hour=hour2,
        time2_minute=minute2,
        pin_enabled=pin_enabled,
    )

    # Build confirmation message
    if hour2 is not None:
        mode_desc = f"每天在 {hour1:02d}:{minute1:02d} 和 {hour2:02d}:{minute2:02d} 各总结前 12h"
    else:
        mode_desc = f"每天在 {hour1:02d}:{minute1:02d} 总结前 24h"

    pin_desc = "✅ 开启（成功发送后自动置顶）" if pin_enabled else "❌ 关闭"

    await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"✅ Auto-summary enabled!\n📅 {mode_desc} (UTC+8)\n📌 置顶: {pin_desc}\n🌐 Language: {language or 'Default'}", reply_to_message_id=update.message.message_id)


async def execute_auto_summary(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    language: str,
    hours: int = 24,
    pin_enabled: bool = False,
    last_pinned_message_id: int = None,
):
    """Execute auto-summary for a chat (called by scheduler).

    Args:
        context: Bot context.
        chat_id: Chat ID to summarize.
        language: Summary language.
        hours: Number of hours to summarize (12 or 24).
        pin_enabled: Whether to pin the summary message on success.
        last_pinned_message_id: Message ID of previously pinned summary (to unpin).

    Returns:
        Tuple of (success: bool, pinned_message_id: Optional[int]).
        success=True means the summary was generated and sent (or legitimately skipped
        because there were no messages). success=False means an error occurred and
        the caller should NOT mark the slot as done.
    """
    summary_service = SummaryService()

    try:
        time_str = "12h" if hours == 12 else "24h"
        summary = await summary_service.generate_summary(
            chat_id=chat_id,
            hours=hours,
            language=language,
            time_str=time_str,
        )

        if not summary or "No messages found" in summary:
            logger.info(f"Auto-summary skipped for chat {chat_id}: {summary[:80] if summary else 'empty'}")
            return (True, None)  # Legitimate skip — no messages, mark as done

        if summary.startswith("❌"):
            # AI call failed — do NOT mark as done so it can retry
            logger.warning(f"Auto-summary FAILED for chat {chat_id}: {summary[:120]}")
            return (False, None)

        # Send summary message using unified sender
        sender = MessageSender(bot=context.bot, chat_id=chat_id)
        msg_ids = await sender.send_static(text=summary)

        logger.info(f"Auto-summary sent to chat {chat_id} (hours={hours})")

        # Pin the message if enabled and sending was successful
        if pin_enabled and msg_ids:
            sent_msg_id = msg_ids[0] # Pin the first message of the split summary
            # Unpin the previous auto-summary first (if exists)
            if last_pinned_message_id is not None:
                try:
                    await context.bot.unpin_chat_message(
                        chat_id=chat_id,
                        message_id=last_pinned_message_id,
                    )
                    logger.info(f"Unpinned old auto-summary (msg_id={last_pinned_message_id}) in chat {chat_id}")
                except Exception as unpin_err:
                    # Old message might be deleted, or bot lost admin — non-fatal
                    logger.warning(f"Failed to unpin old auto-summary in chat {chat_id}: {unpin_err}")

            # Pin the new message
            try:
                await context.bot.pin_chat_message(
                    chat_id=chat_id,
                    message_id=sent_msg_id,
                    disable_notification=True,
                )
                logger.info(f"Auto-summary pinned in chat {chat_id} (msg_id={sent_msg_id})")
                return (True, sent_msg_id)
            except Exception as pin_err:
                logger.warning(f"Failed to pin auto-summary in chat {chat_id}: {pin_err}")
                # Pin failed but summary was sent — still a success
                return (True, None)

        return (True, None)

    except Exception as e:
        logger.error(f"Error executing auto-summary for chat {chat_id}: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error generating auto summary: {str(e)}",
            )
        except Exception:
            pass  # If we can't even send error message, just log it
        return (False, None)
