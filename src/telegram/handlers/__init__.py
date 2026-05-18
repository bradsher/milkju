"""Telegram handlers for bot commands and callbacks."""

from __future__ import annotations

from src.telegram.handlers.chat_handlers import (
    start_command,
    help_command,
    cancel_command,
    p_command,
    chat_message,
    clear_conversation_command,
    new_conversation_command,
    search_command,
)
from src.telegram.handlers.settings_handlers import (
    set_system_prompt_command,
    get_system_prompt_command,
    set_model_command,
    set_model_callback,
    summary_model_command,
    summary_model_callback,
)
from src.telegram.handlers.summary_handlers import (
    summary_command,
    auto_summary_command,
    execute_auto_summary,
)
from src.telegram.admin import (
    admin_panel,
    admin_callback,
    admin_input_handler,
)
from src.telegram.handlers.movie_handlers import (
    recommend_command,
)
from src.telegram.handlers.image_handlers import (
    nai_command,
    naia_command,
)


# claim_admin needs to be extracted separately
async def claim_admin(update, context):
    """Claim admin privileges using secret code."""
    import os
    from src.services import PermissionService
    from src.telegram.utils.message_sender import MessageSender, telegram_escape
    
    permission_service = PermissionService()
    
    if not context.args:
        return
    
    secret = context.args[0]
    admin_secret = os.getenv("ADMIN_SECRET", "your_secret_here")
    
    if secret == admin_secret:
        await permission_service.add_admin(update.effective_user.id)
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="🎉 You are now an admin!", reply_to_message_id=update.message.message_id)
    else:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="❌ Invalid secret.", reply_to_message_id=update.message.message_id)


__all__ = [
    # Chat handlers
    "start_command",
    "help_command",
    "cancel_command",
    "p_command",
    "chat_message",
    "clear_conversation_command",
    "new_conversation_command",
    "search_command",
    # Settings handlers
    "set_system_prompt_command",
    "get_system_prompt_command",
    "set_model_command",
    "set_model_callback",
    "summary_model_command",
    "summary_model_callback",
    # Summary handlers
    "summary_command",
    "auto_summary_command",
    "execute_auto_summary",
    # Admin handlers
    "claim_admin",
    "admin_panel",
    "admin_callback",
    "admin_input_handler",
    # Movie handlers
    "recommend_command",
    # NovelAI handlers
    "nai_command",
    "naia_command",
]
