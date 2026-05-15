from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.core.infrastructure import ConfigService
from src.services import PermissionService, ConversationService

async def handle_sys_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    data = query.data
    config_service = ConfigService()
    permission_service = PermissionService()
    user_id = query.from_user.id
    
    # ✅ P1: System settings restricted to Super Admin only
    is_super_admin = await permission_service.is_super_admin(user_id)
    
    if not is_super_admin:
        await query.answer("⛔ Only Super Admins can access system settings.", show_alert=True)
        return
    
    if data == "admin_sys_menu":
        # Get current values
        timeout = await config_service.get_system_override("timeout", default=60)
        max_len = await config_service.get_system_override("max_msg_len", default=4096)
        streaming_interval = await config_service.get_streaming_update_interval()
        
        text = (
            "🔧 **System Configuration**\n\n"
            f"• **Request Timeout**: `{timeout}s`\n"
            f"• **Max Message Length**: `{max_len}` chars\n"
            f"• **Streaming Update Interval**: `{streaming_interval}s`\n"
            "  _Telegram limit: ≥3s for groups_\n"
        )
        
        keyboard = [
            [InlineKeyboardButton("Set Timeout", callback_data="sys_set_timeout")],
            [InlineKeyboardButton("Set Max Length", callback_data="sys_set_maxlen")],
            [InlineKeyboardButton("📊 Set Streaming Interval", callback_data="sys_set_streaming_interval")],
            [InlineKeyboardButton("🗑️ Message Cleanup", callback_data="sys_msg_cleanup_menu")],
            [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
        ]
        await query.edit_message_text(
            text,
            reply_markup=InlineKeyboardMarkup(keyboard),
            parse_mode="Markdown"
        )
        
    elif data == "sys_set_timeout":
        context.user_data['awaiting_config'] = 'sys_timeout'
        await query.message.reply_text("Please enter new **timeout** in seconds (e.g. 60):", parse_mode="Markdown")
        
    elif data == "sys_set_maxlen":
        context.user_data['awaiting_config'] = 'sys_max_msg_len'
        await query.message.reply_text("Please enter new **max message length** (e.g. 4096):", parse_mode="Markdown")
    
    elif data == "sys_set_streaming_interval":
        current_interval = await config_service.get_streaming_update_interval()
        context.user_data['awaiting_config'] = 'streaming_interval'
        await query.message.reply_text(
            f"📊 **Set Streaming Update Interval**\n\n"
            f"Current: `{current_interval}s`\n\n"
            f"Please enter new interval in seconds:\n"
            f"• Range: 2.0 - 10.0\n"
            f"• Recommended: 3.5s (Telegram limit: ≥3s for groups)\n\n"
            f"_Lower = faster updates but higher risk of rate limiting_",
            parse_mode="Markdown"
        )

    elif data == "sys_msg_cleanup_menu":
        await show_cleanup_menu(query, config_service)
    
    elif data == "sys_toggle_auto_cleanup":
        
        # Toggle auto cleanup
        current_enabled = await config_service.get_auto_cleanup_enabled()
        await config_service.set_auto_cleanup_enabled(not current_enabled)
        await show_cleanup_menu(query, config_service)
        await query.answer(f"Auto cleanup {'enabled' if not current_enabled else 'disabled'}")
    
    elif data == "sys_set_cleanup_days":
        
        context.user_data['awaiting_config'] = 'cleanup_days'
        await query.message.reply_text(
            "Please enter the number of days to keep messages (e.g. 30):",
            parse_mode="Markdown"
        )
    
    elif data == "sys_delete_all_messages":
        
        # Show confirmation
        await show_delete_all_confirmation(query)
    
    elif data == "sys_delete_all_confirm":
        
        # Execute deletion
        conversation_service = ConversationService()
        deleted_count = await conversation_service.delete_all_messages()
        
        await query.edit_message_text(
            f"✅ **Deletion Complete**\n\n"
            f"Deleted {deleted_count} messages from all chats.",
            parse_mode="Markdown"
        )
        await query.answer("All messages deleted successfully")


async def show_cleanup_menu(query, config_service: ConfigService):
    """Display message cleanup menu with permission-based buttons."""
    # Get current configuration
    enabled = await config_service.get_auto_cleanup_enabled()
    days = await config_service.get_auto_cleanup_days()
    last_run = await config_service.get_auto_cleanup_last_run()
    
    status_icon = "✅" if enabled else "❌"
    last_run_text = last_run if last_run else "Never"
    
    text = (
        "🗑️ **Message Cleanup Settings**\n\n"
        f"• **Auto Cleanup**: {status_icon} {'Enabled' if enabled else 'Disabled'}\n"
        f"• **Retention Days**: {days} days\n"
        f"• **Last Run**: {last_run_text}\n"
    )
    
    keyboard = [
        [InlineKeyboardButton(
            f"{'🔴 Disable' if enabled else '🟢 Enable'} Auto Cleanup",
            callback_data="sys_toggle_auto_cleanup"
        )],
        [InlineKeyboardButton(
            "📅 Set Retention Days",
            callback_data="sys_set_cleanup_days"
        )],
        [InlineKeyboardButton(
            "🗑️ Delete All Messages",
            callback_data="sys_delete_all_messages"
        )],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_sys_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_delete_all_confirmation(query):
    """Show confirmation dialog for deleting all messages."""
    text = (
        "⚠️ **WARNING: Destructive Operation**\n\n"
        "You are about to delete **ALL messages** from **ALL chats**.\n\n"
        "This action **CANNOT be undone**.\n\n"
        "Are you sure you want to continue?"
    )
    
    keyboard = [
        [InlineKeyboardButton("⚠️ Yes, Delete All", callback_data="sys_delete_all_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="sys_msg_cleanup_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
