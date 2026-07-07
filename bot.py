
"""TeleChat Bot - Refactored version using service layer."""

import logging
import os
from telegram import Update, BotCommand
from telegram.ext import (
    ApplicationBuilder,
    CommandHandler,
    MessageHandler,
    filters,
    CallbackQueryHandler,
    ContextTypes,
)
from telegram.request import HTTPXRequest
from dotenv import load_dotenv
from datetime import datetime, timezone, timedelta

from src.database import migration_runner
# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ChatSettingsService
from src.telegram.handlers import (
    start_command,
    help_command,
    cancel_command,
    p_command,
    clear_conversation_command,
    new_conversation_command,
    search_command,
    recommend_command,
    get_system_prompt_command,
    set_system_prompt_command,
    set_model_command,
    summary_command,
    auto_summary_command,
    set_model_callback,
    summary_model_command,
    summary_model_callback,
    chat_message,
    execute_auto_summary,
    claim_admin,
    nai_command,
    naia_command,
    # New Admin Panel handlers are also exposed via handlers init
    admin_panel,
    admin_callback,
    admin_input_handler,
)


load_dotenv()

# Logging setup
log_level_str = os.getenv("LOG_LEVEL", "INFO").upper()
log_level = getattr(logging, log_level_str, logging.INFO)

logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s", level=log_level
)

TOKEN = os.getenv("BOT_TOKEN")
ADMIN_SECRET = os.getenv("ADMIN_SECRET", "your_secret_here")

# UTC+8 timezone
UTC8 = timezone(timedelta(hours=8))


async def check_auto_summaries(context: ContextTypes.DEFAULT_TYPE):
    """Check and execute scheduled auto-summaries using service layer."""
    settings_service = ChatSettingsService()

    try:
        now_utc8 = datetime.now(UTC8)
        current_hour = now_utc8.hour
        current_minute = now_utc8.minute
        current_date = now_utc8.strftime("%Y-%m-%d")

        # Get all enabled auto-summaries
        summaries = await settings_service.get_all_enabled_auto_summaries()

        for summary_config in summaries:
            chat_id = summary_config.chat_id
            language = summary_config.language
            pin_enabled = summary_config.pin_enabled
            has_two_times = summary_config.has_two_times
            hours = summary_config.summary_hours  # 12 or 24
            last_run_slot = summary_config.last_run_slot
            last_run_date = summary_config.last_run_date  # legacy fallback

            # Build list of (hour, minute) slots to check
            slots = [(summary_config.hour, summary_config.minute)]
            if has_two_times:
                slots.append((summary_config.time2_hour, summary_config.time2_minute))

            for slot_hour, slot_minute in slots:
                if slot_hour is None or slot_minute is None:
                    continue

                # Use a tolerance window (±2 minutes) instead of exact match,
                # because APScheduler jobs can be delayed by network issues or
                # slow API calls blocking the event loop.
                slot_time_minutes = slot_hour * 60 + slot_minute
                current_time_minutes = current_hour * 60 + current_minute
                diff = abs(current_time_minutes - slot_time_minutes)
                # Handle midnight wraparound (e.g. slot=23:59, now=00:01)
                if diff > 720:  # more than 12 hours means we wrapped
                    diff = 1440 - diff
                if diff > 2:
                    continue

                # Build the slot key using the CONFIGURED time (not current time)
                # so dedup is stable regardless of when the job actually fires
                current_slot = f"{current_date}_{slot_hour}:{slot_minute}"

                # Check deduplication:
                # New mode: compare against last_run_slot
                # Legacy mode (single-time old config): compare date against last_run_date
                already_ran = False
                if last_run_slot is not None:
                    already_ran = (last_run_slot == current_slot)
                else:
                    # Legacy fallback: single-time mode uses date-level dedup
                    already_ran = (last_run_date == current_date)

                if already_ran:
                    continue

                logging.info(
                    f"Executing auto-summary for chat {chat_id} at {slot_hour:02d}:{slot_minute:02d} "
                    f"(hours={hours}, pin={pin_enabled})"
                )
                new_pinned_id = await execute_auto_summary(
                    context, chat_id, language,
                    hours=hours,
                    pin_enabled=pin_enabled,
                    last_pinned_message_id=summary_config.last_pinned_message_id,
                )

                # Unpack the (success, pinned_id) tuple
                success, pinned_id = new_pinned_id

                if success:
                    # Only mark slot as "done" if summary succeeded or was
                    # legitimately skipped (no messages). API failures should
                    # NOT be marked so the system retries next minute.
                    await settings_service.update_auto_summary_last_run_slot(chat_id, current_slot)
                    await settings_service.update_auto_summary_last_run(chat_id, current_date)

                    # Persist the new pinned message ID (only if pin succeeded)
                    if pinned_id is not None:
                        await settings_service.update_auto_summary_last_pinned_message_id(
                            chat_id, pinned_id
                        )
                else:
                    logging.warning(
                        f"Auto-summary failed for chat {chat_id} at {slot_hour:02d}:{slot_minute:02d}, "
                        f"will retry on next check"
                    )

    except Exception as e:
        logging.error(f"Error in check_auto_summaries: {e}", exc_info=True)



async def check_message_cleanup(context: ContextTypes.DEFAULT_TYPE):
    """Check and execute scheduled message cleanup."""
    from src.core.infrastructure import ConfigService
    from src.services import ConversationService
    
    config_service = ConfigService()

    try:
        # Check if auto cleanup is enabled
        enabled = await config_service.get_auto_cleanup_enabled()
        if not enabled:
            return

        now_utc8 = datetime.now(UTC8)
        current_hour = now_utc8.hour
        current_minute = now_utc8.minute
        current_date = now_utc8.strftime("%Y-%m-%d")

        # Check if it's midnight (00:00)
        if current_hour != 0 or current_minute != 0:
            return

        # Check if already run today
        last_run = await config_service.get_auto_cleanup_last_run()
        if last_run == current_date:
            return

        # Execute cleanup
        days = await config_service.get_auto_cleanup_days()
        conversation_service = ConversationService()
        deleted_count = await conversation_service.cleanup_old_messages(days)

        # Update last run date
        await config_service.set_auto_cleanup_last_run(current_date)

        logging.info(
            f"Auto cleanup executed: deleted {deleted_count} messages older than {days} days"
        )

    except Exception as e:
        logging.error(f"Error in check_message_cleanup: {e}", exc_info=True)


async def post_init(application):
    """Initialize database and start scheduled tasks."""
    # Run migrations
    await migration_runner.init_database()

    # Register bot commands for autocomplete
    commands = [
        BotCommand("help", "显示帮助信息 / Show help message"),
        BotCommand("s", "网络搜索 / Web search"),
        BotCommand("p", "发送消息不回复 / Send without reply"),
        BotCommand("summary", "生成聊天总结 / Chat summary"),
        BotCommand("recommend", "电影推荐 / Movie recommendations"),
    ]
    await application.bot.set_my_commands(commands)

    # Schedule auto-summary checker to run every minute
    job_queue = application.job_queue
    job_queue.run_repeating(check_auto_summaries, interval=60, first=10)
    
    # Schedule message cleanup checker to run every minute
    job_queue.run_repeating(check_message_cleanup, interval=60, first=15)

    print(f"✅ Bot is running!")
    print(f"📝 Admin Secret to claim access: /claim {ADMIN_SECRET}")
    print(f"⏰ Auto-summary scheduler started (checking every 60 seconds)")
    print(f"🗑️ Message cleanup scheduler started (checking every 60 seconds)")
    print(f"🎬 Registered {len(commands)} bot commands for autocomplete")
    print(f"🎉 Using refactored service layer architecture!")


def main():
    """Main entry point for the bot."""
    import asyncio

    if not TOKEN:
        print("❌ Error: BOT_TOKEN not found in .env")
        return

    # Ensure database is initialized before reading config
    asyncio.run(migration_runner.init_database())

    # Read concurrent_updates setting from DB before building Application
    async def _read_concurrent_setting():
        from src.core.infrastructure import ConfigService
        config_service = ConfigService()
        return await config_service.get_concurrent_updates()

    concurrent_enabled = asyncio.run(_read_concurrent_setting())
    print(f"⚡ Concurrent updates: {'Enabled' if concurrent_enabled else 'Disabled'}")

    # Configure HTTP request with increased timeouts to prevent timeout errors
    pool_size = 100 if concurrent_enabled else 8
    request = HTTPXRequest(
        connection_pool_size=pool_size,
        read_timeout=30.0,      # Increased from default ~5s to 30s
        write_timeout=30.0,     # Increased from default ~5s to 30s
        connect_timeout=10.0,   # Connection timeout
        pool_timeout=10.0,      # Pool acquisition timeout
    )

    application = (
        ApplicationBuilder()
        .token(TOKEN)
        .request(request)
        .concurrent_updates(concurrent_enabled)
        .post_init(post_init)
        .build()
    )

    # Command handlers - Chat
    application.add_handler(CommandHandler("start", start_command))
    application.add_handler(CommandHandler("help", help_command))
    application.add_handler(CommandHandler("cancel", cancel_command))
    application.add_handler(CommandHandler("p", p_command))
    application.add_handler(
        CommandHandler("clear", clear_conversation_command)
    )
    application.add_handler(CommandHandler("new", new_conversation_command))

    # Command handlers - Search
    application.add_handler(CommandHandler("s", search_command))

    # Command handlers - Movie Recommendations
    application.add_handler(CommandHandler("recommend", recommend_command))
    
    # Command handlers - NovelAI Image Generation
    application.add_handler(CommandHandler("nai", nai_command))
    application.add_handler(CommandHandler("naia", naia_command))

    # Command handlers - Settings
    application.add_handler(
        CommandHandler("system", get_system_prompt_command)
    )
    application.add_handler(
        CommandHandler("set_system", set_system_prompt_command)
    )
    application.add_handler(CommandHandler("set_model", set_model_command))
    application.add_handler(CommandHandler("summary_model", summary_model_command))

    # Command handlers - Summary
    application.add_handler(CommandHandler("summary", summary_command))
    application.add_handler(
        CommandHandler("auto_summary", auto_summary_command)
    )

    # Command handlers - Admin
    application.add_handler(CommandHandler("claim", claim_admin))
    application.add_handler(CommandHandler("admin", admin_panel))

    # Callback query handlers
    application.add_handler(
        CallbackQueryHandler(set_model_callback, pattern="^set_model_")
    )
    application.add_handler(
        CallbackQueryHandler(summary_model_callback, pattern="^sum_model_")
    )
    application.add_handler(CallbackQueryHandler(admin_callback))

    # Message handler (combined: admin input + chat)
    async def combined_message_handler(
        update: Update, context: ContextTypes.DEFAULT_TYPE
    ):
        """Handle text/photo messages - try admin input first, then chat."""
        # Check if awaiting admin input
        if context.user_data.get("awaiting_config"):
            await admin_input_handler(update, context)
            return

        # Otherwise, handle as chat message
        await chat_message(update, context)

    application.add_handler(
        MessageHandler(
            (filters.TEXT | filters.PHOTO | filters.Document.ALL) & (~filters.COMMAND),
            combined_message_handler,
        )
    )

    # Error handler
    async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE) -> None:
        logging.error(msg="Exception while handling an update:", exc_info=context.error)
        
        # Only send error message to user in specific cases
        if isinstance(update, Update) and update.effective_message:
            message = update.effective_message
            chat_type = message.chat.type
            
            # Determine if we should send error message
            should_send_error = False
            
            if chat_type == "private":
                # Always send error in private chats
                should_send_error = True
            elif chat_type in ["group", "supergroup"]:
                # In groups, only send error if bot was explicitly mentioned or replied to
                bot_username = context.bot.username
                user_message = message.text or message.caption or ""
                
                is_mentioned = f"@{bot_username}" in user_message
                is_reply_to_bot = (
                    message.reply_to_message
                    and message.reply_to_message.from_user.id == context.bot.id
                )
                
                should_send_error = is_mentioned or is_reply_to_bot
            
            if should_send_error:
                try:
                    await update.effective_message.reply_text(
                        f"❌ An error occurred: {context.error}"
                    )
                except Exception:
                    pass  # Silently fail if we can't send error message

    application.add_error_handler(error_handler)

    # Start polling
    print("🚀 Starting bot polling...")
    application.run_polling()


if __name__ == "__main__":
    main()
