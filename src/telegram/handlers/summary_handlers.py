"""Summary handlers for chat summarization."""

from __future__ import annotations

from telegram import Update
from telegram.ext import ContextTypes
import logging
import re

# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ChatSettingsService, ConfigService
# Import from services (Layer 3)
from src.services import SummaryService, PermissionService
from src.telegram.utils.message_utils import edit_message_safe, reply_message_safe

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

    # 1. Permission Check
    perm_required = await config_service.is_summary_permission_required()

    if perm_required and not await permission_service.is_group_admin(update):
        await reply_message_safe(
            update.message,
            "⛔ Permission Denied. Only Admins can use this command."
        )
        return

    # 2. Parse Time Range and Language
    if not context.args:
        await reply_message_safe(
            update.message,
            "⚠️ Usage: `/summary <time> [language]` (e.g., `/summary 1d English`)",
            parse_mode="Markdown"
        )
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
        await reply_message_safe(update.message, "⚠️ Please specify a time range.")
        return

    time_str = " ".join(time_args).lower()

    # Parse time
    total_seconds = 0
    matches = re.findall(r"(\d+)\s*([dhm])", time_str)

    if not matches:
        await reply_message_safe(
            update.message,
            "⚠️ Invalid format. Use d (days), h (hours), m (minutes). Example: `/summary 1d 2h`",
            parse_mode="Markdown"
        )
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
        await reply_message_safe(update.message, "⚠️ Time range must be greater than 0.")
        return

    if total_seconds > 86400:
        await reply_message_safe(
            update.message,
            "⚠️ Summary is limited to the last 24 hours."
        )
        return

    status_msg = await reply_message_safe(update.message, "🔄 Generating summary... ⏳")

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
            await edit_message_safe(status_msg, "📭 No messages found in the specified time range.")
            return

        # Use safe message editing with auto-fallback
        await edit_message_safe(status_msg, summary, parse_mode="HTML")

    except Exception as e:
        logger.error(f"Error generating summary: {e}", exc_info=True)
        await edit_message_safe(status_msg, f"❌ Error generating summary: {str(e)}")


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

    chat = update.effective_chat

    # Permission Check: Group Admin only
    permission_service = PermissionService()
    if not await permission_service.is_group_admin(update):
        await reply_message_safe(
            update.message,
            "⛔ Only Group Admins can configure auto-summary."
        )
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
            await reply_message_safe(update.message, "📊 Auto-summary is currently **disabled**.", parse_mode="Markdown")
        else:
            mode = "双时间段 (每次12h)" if settings.has_two_times else "单时间段 (每次24h)"
            pin_status = "✅ 开启" if settings.pin_enabled else "❌ 关闭"
            time_info = f"⏰ 时间1: {settings.time_string} (UTC+8)"
            if settings.has_two_times:
                time_info += f"\n⏰ 时间2: {settings.time2_string} (UTC+8)"
            await reply_message_safe(
                update.message,
                f"📊 Auto-summary is **enabled**\n"
                f"{time_info}\n"
                f"📐 模式: {mode}\n"
                f"📌 置顶: {pin_status}\n"
                f"🌐 Language: {settings.language or 'Default'}\n"
                f"🕐 Last run slot: {settings.last_run_slot or settings.last_run_date or 'Never'}",
                parse_mode="Markdown"
            )
        return

    # Disable auto-summary
    if context.args[0].lower() in ["off", "disable"]:
        await settings_service.disable_auto_summary(chat.id)
        await settings_service.clear_auto_summary_last_run(chat.id)
        await reply_message_safe(update.message, "✅ Auto-summary disabled.")
        return

    # --- Parse arguments: time1 [time2] [pin] ---
    args = list(context.args)

    # Parse time1 (required)
    t1 = parse_time(args[0])
    if t1 is None:
        await reply_message_safe(
            update.message,
            "⚠️ 无法识别时间格式。请使用 HH:MM 格式，例如：`/auto_summary 10:00` 或 `/auto_summary 10:00 22:00`",
            parse_mode="Markdown"
        )
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
                await reply_message_safe(update.message, "⚠️ 两个时间点不能相同。")
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

    await reply_message_safe(
        update.message,
        f"✅ Auto-summary enabled!\n"
        f"📅 {mode_desc} (UTC+8)\n"
        f"📌 置顶: {pin_desc}\n"
        f"🌐 Language: {language or 'Default'}",
        parse_mode="HTML"
    )


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
        The message_id of the newly pinned message, or None if not pinned.
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

        if not summary or "No messages found" in summary or summary.startswith("❌"):
            logger.info(f"Auto-summary skipped for chat {chat_id}: {summary[:80] if summary else 'empty'}")
            return None

        # Send summary message
        sent_msg = await context.bot.send_message(
            chat_id=chat_id,
            text=summary,
            parse_mode="HTML",
        )

        logger.info(f"Auto-summary sent to chat {chat_id} (hours={hours})")

        # Pin the message if enabled and sending was successful
        if pin_enabled and sent_msg:
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
                    message_id=sent_msg.message_id,
                    disable_notification=True,
                )
                logger.info(f"Auto-summary pinned in chat {chat_id} (msg_id={sent_msg.message_id})")
                return sent_msg.message_id
            except Exception as pin_err:
                logger.warning(f"Failed to pin auto-summary in chat {chat_id}: {pin_err}")
                # Pin failed — don't return a message_id so we don't overwrite the old one
                return None

        return None

    except Exception as e:
        logger.error(f"Error executing auto-summary for chat {chat_id}: {e}", exc_info=True)
        try:
            await context.bot.send_message(
                chat_id=chat_id,
                text=f"❌ Error generating auto summary: {str(e)}",
            )
        except Exception:
            pass  # If we can't even send error message, just log it
        return None
