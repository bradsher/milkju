"""Settings handlers for chat-specific configuration."""

from __future__ import annotations

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
import logging

# Import from infrastructure layer (Layer 1)
from src.core.infrastructure import ChatSettingsService, ProviderService
# Import from services (Layer 3)
from src.services import PermissionService
from src.telegram.utils.message_utils import reply_message_safe

logger = logging.getLogger(__name__)


async def set_system_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Set a custom system prompt for the current chat.

    Usage: /set_system You are a helpful assistant.
    Permissions: Group Admin or Private Chat User
    """
    settings_service = ChatSettingsService()
    permission_service = PermissionService()

    # Permission Check
    if not await permission_service.is_group_admin(update):
        await reply_message_safe(
            update.message,
            "⛔ You must be a Group Admin to use this command."
        )
        return

    chat = update.effective_chat
    if not context.args:
        await reply_message_safe(
            update.message,
            "⚠️ Usage: `/set_system <prompt>`\nTo clear, use `/set_system default`",
            parse_mode="Markdown"
        )
        return

    prompt = " ".join(context.args)

    if prompt.lower() in ["default", "clear", "reset"]:
        await settings_service.set_system_prompt(chat.id, None)
        await reply_message_safe(update.message, "✅ System prompt reset to default.")
    else:
        await settings_service.set_system_prompt(chat.id, prompt)
        await reply_message_safe(
            update.message,
            f"✅ System prompt updated.\n\nNew Prompt:\n`{prompt}`",
            parse_mode="Markdown"
        )


async def get_system_prompt_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """View the current system prompt for this chat."""
    settings_service = ChatSettingsService()
    permission_service = PermissionService()

    # Permission Check
    if not await permission_service.is_group_admin(update):
        await reply_message_safe(
            update.message,
            "⛔ You must be a Group Admin to use this command."
        )
        return

    chat = update.effective_chat
    prompt = await settings_service.get_system_prompt(chat.id)

    if prompt:
        await reply_message_safe(
            update.message,
            f"📝 **Current System Prompt**:\n\n`{prompt}`",
            parse_mode="Markdown"
        )
    else:
        await reply_message_safe(
            update.message,
            "📝 **Current System Prompt**:\n\n`Default` (No custom prompt set).",
            parse_mode="Markdown"
        )


async def set_model_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Open provider/model selection menu for this chat."""
    provider_service = ProviderService()
    permission_service = PermissionService()

    # ✅ P1: Dual permission verification - requires BOTH Bot Admin AND Group Admin
    user_id = update.effective_user.id
    is_bot_admin = await permission_service.is_admin(user_id)
    is_group_admin_or_private = await permission_service.is_group_admin(update)

    if not (is_bot_admin and is_group_admin_or_private):
        await reply_message_safe(
            update.message, 
            "❌ This command requires both Bot Admin and Group Admin privileges.\n"
            "只有同时拥有Bot管理员和群组管理员权限的用户才能设置模型。"
        )
        return

    # Get active providers
    providers = await provider_service.get_active_providers()
    if not providers:
        await reply_message_safe(
            update.message,
            "⚠️ No providers configured. Please ask the Bot Admin to add providers."
        )
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

    await reply_message_safe(
        update.message,
        "🔧 Select a Provider:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


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
            f"✅ Model set to **{selected_model.model}** from **{provider.name}**.",
            parse_mode="Markdown",
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
