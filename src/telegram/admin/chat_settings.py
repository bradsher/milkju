"""Chat Settings module for admin panel.

Handles:
- History limits (Private/Group)
- Max tokens configuration
- Summary language
- Summary permission settings
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.core.infrastructure import ConfigService


async def handle_chat_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route chat settings callbacks."""
    query = update.callback_query
    data = query.data
    config_service = ConfigService()
    
    if data == "admin_chat_menu":
        await render_chat_menu(query, config_service)
    elif data == "set_history_private":
        context.user_data['awaiting_config'] = 'history_private'
        await query.message.reply_text(
            "📝 **Set Private Chat History Limit**\
\
Enter the number of messages (e.g., 20):",
            parse_mode="Markdown"
        )
    elif data == "set_history_group":
        context.user_data['awaiting_config'] = 'history_group'
        await query.message.reply_text(
            "📝 **Set Group Chat History Limit**\
\
Enter the number of messages (e.g., 20):",
            parse_mode="Markdown"
        )
    elif data == "set_max_tokens":
        context.user_data['awaiting_config'] = 'max_tokens'
        await query.message.reply_text(
            "🔢 **Set Max Tokens**\
\
Enter max tokens (e.g., 2000, or leave empty for unlimited):",
            parse_mode="Markdown"
        )
    elif data == "set_summary_lang":
        context.user_data['awaiting_config'] = 'summary_lang'
        await query.message.reply_text(
            "🌐 **Set Summary Language**\
\
Enter language (e.g., 'English', 'Simplified Chinese'):",
            parse_mode="Markdown"
        )
    elif data == "toggle_summary_perm":
        await toggle_summary_permission(query, config_service)


async def render_chat_menu(query, config_service):
    """Render chat settings menu."""
    history_limit = await config_service.get_history_limit()
    group_limit = await config_service.get_group_history_limit()
    max_tokens = await config_service.get_max_tokens()
    summary_lang = await config_service.get_summary_language()
    summary_perm = await config_service.is_summary_permission_required()
    
    perm_str = "🔒 Restricted (Admins Only)" if summary_perm else "🔓 Unrestricted (Everyone)"
    tokens_str = f"`{max_tokens}`" if max_tokens else "Unlimited"
    
    text = (
        "💬 **Chat Settings**\
\
"
        f"📝 **Private History**: {history_limit} messages\
"
        f"📝 **Group History**: {group_limit} messages\
"
        f"🔢 **Max Tokens**: {tokens_str}\
"
        f"🌐 **Summary Language**: {summary_lang}\
"
        f"🔐 **Summary Permission**: {perm_str}\
"
    )
    
    keyboard = [
        [InlineKeyboardButton("Set Private History", callback_data="set_history_private")],
        [InlineKeyboardButton("Set Group History", callback_data="set_history_group")],
        [InlineKeyboardButton("Set Max Tokens", callback_data="set_max_tokens")],
        [InlineKeyboardButton("Set Summary Language", callback_data="set_summary_lang")],
        [InlineKeyboardButton("Toggle Summary Permission", callback_data="toggle_summary_perm")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def toggle_summary_permission(query, config_service):
    """Toggle summary permission requirement."""
    current = await config_service.is_summary_permission_required()
    await config_service.set_summary_permission_required(not current)
    
    new_status = "Restricted (Admins Only)" if not current else "Unrestricted (Everyone)"
    await query.answer(f"✅ Summary access: {new_status}")
    
    await render_chat_menu(query, config_service)
