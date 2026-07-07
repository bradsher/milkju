"""Settings handlers for chat-specific configuration."""

from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
import logging

# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ChatSettingsService, ProviderService
# Import from services (Layer 3)
from src.services import PermissionService
from src.telegram.utils.message_sender import MessageSender, telegram_escape

logger = logging.getLogger(__name__)


async def set_system_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set a custom system prompt for the current chat.

    Usage: /set_system You are a helpful assistant.
    Permissions: Group Admin or Private Chat User
    """
    settings_service = ChatSettingsService()
    permission_service = PermissionService()

    # Permission Check
    chat = update.effective_chat
    user_id = update.effective_user.id
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
    
    if chat.type == constants.ChatType.PRIVATE:
        if not await permission_service.is_bot_admin(user_id):
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ 权限不足：仅管理员可以设置 System Prompt。", reply_to_message_id=update.message.message_id)
            return
    elif not await permission_service.is_group_admin(update):
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ You must be a Group Admin to use this command.", reply_to_message_id=update.message.message_id)
        return

    chat = update.effective_chat
    if not context.args:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ Usage: <code>/set_system &lt;prompt&gt;</code>\nTo clear, use <code>/set_system default</code>", reply_to_message_id=update.message.message_id)
        return

    prompt = " ".join(context.args)

    if prompt.lower() in ["default", "clear", "reset"]:
        await settings_service.set_system_prompt(chat.id, None)
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="✅ System prompt reset to default.", reply_to_message_id=update.message.message_id)
    else:
        await settings_service.set_system_prompt(chat.id, prompt)
        safe_prompt = telegram_escape(prompt)
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"✅ System prompt updated.\n\nNew Prompt:\n<code>{safe_prompt}</code>", reply_to_message_id=update.message.message_id)


async def get_system_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View the current system prompt for this chat."""
    settings_service = ChatSettingsService()
    permission_service = PermissionService()

    # Permission Check
    chat = update.effective_chat
    user_id = update.effective_user.id
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
    
    if chat.type == constants.ChatType.PRIVATE:
        if not await permission_service.is_bot_admin(user_id):
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ 权限不足：仅管理员可以查看 System Prompt。", reply_to_message_id=update.message.message_id)
            return
    elif not await permission_service.is_group_admin(update):
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⛔ You must be a Group Admin to use this command.", reply_to_message_id=update.message.message_id)
        return

    chat = update.effective_chat
    prompt = await settings_service.get_system_prompt(chat.id)

    if prompt:
        safe_prompt = telegram_escape(prompt)
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"📝 <b>Current System Prompt</b>:\n\n<code>{safe_prompt}</code>", reply_to_message_id=update.message.message_id)
    else:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="📝 <b>Current System Prompt</b>:\n\n<code>Default</code> (No custom prompt set)", reply_to_message_id=update.message.message_id)


async def set_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open provider/model selection menu for this chat."""
    provider_service = ProviderService()
    permission_service = PermissionService()

    # ✅ P1: Dual permission verification - requires BOTH Bot Admin AND Group Admin
    user_id = update.effective_user.id
    
    # --- 0. Pre-checks (Blacklist) ---
    if await permission_service.is_banned(user_id):
        return  # Silently drop messages from banned users
        
    is_bot_admin = await permission_service.is_bot_admin(user_id)
    is_group_admin_or_private = await permission_service.is_group_admin(update)

    if not (is_bot_admin and is_group_admin_or_private):
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="❌ This command requires both Bot Admin and Group Admin privileges.\n"
            "只有同时拥有Bot管理员和群组管理员权限的用户才能设置模型。", reply_to_message_id=update.message.message_id)
        return

    # Get active providers
    providers = await provider_service.get_active_providers()
    if not providers:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ No providers configured. Please ask the Bot Admin to add providers.", reply_to_message_id=update.message.message_id)
        return

    # Build provider selection keyboard
    keyboard = []
    for provider in providers:
        icon = "🇬" if provider.is_google else "🤖"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{icon} {provider.name}",
                    callback_data=f"set_model_prov_{provider.id}",
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("❌ Reset to Default", callback_data="set_model_reset")]
    )

    await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="🔧 Select a Provider:", reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=update.message.message_id)


async def set_model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle model selection callbacks."""
    provider_service = ProviderService()
    settings_service = ChatSettingsService()

    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id

    # Handle reset
    if data == "set_model_reset":
        await settings_service.clear_model(chat_id)
        await query.edit_message_text("✅ Model reset to default.")
        return

    # Handle provider selection
    if data.startswith("set_model_prov_"):
        provider_id = int(data.split("_")[-1])

        # Get models for this provider
        models = await provider_service.get_models_for_provider(provider_id)

        if not models:
            await query.edit_message_text(
                "⚠️ No models configured for this provider."
            )
            return

        # Store provider_id in user_data for next step
        context.user_data["selected_provider_id"] = provider_id

        # Build model selection keyboard
        keyboard = []
        for model in models:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        model.model, callback_data=f"set_model_model_{model.id}"
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("🔙 Back", callback_data="set_model_back")]
        )

        await query.edit_message_text(
            "🤖 Select a Model:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle model selection
    if data.startswith("set_model_model_"):
        model_id = int(data.split("_")[-1])
        provider_id = context.user_data.get("selected_provider_id")

        if not provider_id:
            await query.edit_message_text("❌ Session expired. Please try again.")
            return

        # Get model details
        models = await provider_service.get_models_for_provider(provider_id)
        selected_model = next((m for m in models if m.id == model_id), None)

        if not selected_model:
            await query.edit_message_text("❌ Model not found.")
            return

        # Save settings
        await settings_service.set_model(chat_id, selected_model.model, provider_id)

        # Get provider name
        provider = await provider_service.get_provider(provider_id)

        await query.edit_message_text(
            f"✅ Model set to <b>{selected_model.model}</b> from <b>{provider.name}</b>.",
            parse_mode="HTML",
        )
        return

    # Handle back button
    if data == "set_model_back":
        # Clear stored provider_id
        context.user_data.pop("selected_provider_id", None)

        # Recreate provider selection menu
        providers = await provider_service.get_active_providers()
        keyboard = []
        for provider in providers:
            icon = "🇬" if provider.is_google else "🤖"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{icon} {provider.name}",
                        callback_data=f"set_model_prov_{provider.id}",
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "❌ Reset to Default", callback_data="set_model_reset"
                )
            ]
        )

        await query.edit_message_text(
            "🔧 Select a Provider:", reply_markup=InlineKeyboardMarkup(keyboard)
        )


async def summary_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open provider/model selection menu for summary feature."""
    provider_service = ProviderService()
    permission_service = PermissionService()

    # Permission Check
    user_id = update.effective_user.id
    is_bot_admin = await permission_service.is_bot_admin(user_id)
    is_group_admin_or_private = await permission_service.is_group_admin(update)

    if not (is_bot_admin and is_group_admin_or_private):
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="❌ 权限不够。只有同时拥有Bot管理员和群组管理员权限的用户才能设置Summary模型。", reply_to_message_id=update.message.message_id)
        return

    # Get active providers
    providers = await provider_service.get_active_providers()
    if not providers:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="⚠️ No providers configured. Please ask the Bot Admin to add providers.", reply_to_message_id=update.message.message_id)
        return

    # Build provider selection keyboard
    keyboard = []
    for provider in providers:
        icon = "🇬" if provider.is_google else "🤖"
        keyboard.append(
            [
                InlineKeyboardButton(
                    f"{icon} {provider.name}",
                    callback_data=f"sum_model_prov_{provider.id}",
                )
            ]
        )

    keyboard.append(
        [InlineKeyboardButton("❌ Reset to Default", callback_data="sum_model_reset")]
    )

    await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="🔧 Select a Provider for Summary:", reply_markup=InlineKeyboardMarkup(keyboard), reply_to_message_id=update.message.message_id)


async def summary_model_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle summary model selection callbacks."""
    provider_service = ProviderService()
    settings_service = ChatSettingsService()

    query = update.callback_query
    await query.answer()

    data = query.data
    chat_id = query.message.chat_id

    # Handle reset
    if data == "sum_model_reset":
        await settings_service.set_summary_model(chat_id, None, None)
        await query.edit_message_text("✅ Summary model reset to default (falls back to chat model).")
        return

    # Handle provider selection
    if data.startswith("sum_model_prov_"):
        provider_id = int(data.split("_")[-1])

        # Get models for this provider
        models = await provider_service.get_models_for_provider(provider_id)

        if not models:
            await query.edit_message_text(
                "⚠️ No models configured for this provider."
            )
            return

        # Store provider_id in user_data for next step
        context.user_data["sum_selected_provider_id"] = provider_id

        # Build model selection keyboard
        keyboard = []
        for model in models:
            keyboard.append(
                [
                    InlineKeyboardButton(
                        model.model, callback_data=f"sum_model_model_{model.id}"
                    )
                ]
            )

        keyboard.append(
            [InlineKeyboardButton("🔙 Back", callback_data="sum_model_back")]
        )

        await query.edit_message_text(
            "🤖 Select a Model for Summary:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
        return

    # Handle model selection
    if data.startswith("sum_model_model_"):
        model_id = int(data.split("_")[-1])
        provider_id = context.user_data.get("sum_selected_provider_id")

        if not provider_id:
            await query.edit_message_text("❌ Session expired. Please try again.")
            return

        # Get model details
        models = await provider_service.get_models_for_provider(provider_id)
        selected_model = next((m for m in models if m.id == model_id), None)

        if not selected_model:
            await query.edit_message_text("❌ Model not found.")
            return

        # Save settings
        await settings_service.set_summary_model(chat_id, selected_model.model, provider_id)

        # Get provider name
        provider = await provider_service.get_provider(provider_id)

        await query.edit_message_text(
            f"✅ Summary model set to <b>{selected_model.model}</b> from <b>{provider.name}</b>.",
            parse_mode="HTML",
        )
        return

    # Handle back button
    if data == "sum_model_back":
        # Clear stored provider_id
        context.user_data.pop("sum_selected_provider_id", None)

        # Recreate provider selection menu
        providers = await provider_service.get_active_providers()
        keyboard = []
        for provider in providers:
            icon = "🇬" if provider.is_google else "🤖"
            keyboard.append(
                [
                    InlineKeyboardButton(
                        f"{icon} {provider.name}",
                        callback_data=f"sum_model_prov_{provider.id}",
                    )
                ]
            )

        keyboard.append(
            [
                InlineKeyboardButton(
                    "❌ Reset to Default", callback_data="sum_model_reset"
                )
            ]
        )

        await query.edit_message_text(
            "🔧 Select a Provider for Summary:", reply_markup=InlineKeyboardMarkup(keyboard)
        )
