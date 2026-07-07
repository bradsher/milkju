"""AI Settings module for admin panel.

Handles:
- Models & Providers management (CRUD)
- API Key management for providers
- AI Strategy configuration (Single/Round Robin)
- Fallback Rules for media types
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.core.infrastructure import ConfigService, ProviderService


async def handle_ai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route AI settings callbacks."""
    query = update.callback_query
    data = query.data
    config_service = ConfigService()
    provider_service = ProviderService()
    
    if data == "admin_ai_menu":
        await render_ai_menu(query)
    elif data == "admin_ai_models":
        await render_models_providers(query, provider_service)
    elif data == "admin_ai_strategy":
        await render_strategy_menu(query, config_service)
    elif data == "admin_ai_fallback":
        await render_fallback_menu(query, config_service, provider_service)
    
    # Provider management
    elif data == "add_provider":
        await prompt_add_provider(query, context)
    elif data.startswith("toggle_prov_"):
        await toggle_provider(query, data, provider_service)
    elif data.startswith("view_prov_details_"):
        await view_provider_details(query, data, provider_service)
    elif data.startswith("view_prov_models_"):
        await view_provider_models(query, data, provider_service)
    elif data.startswith("del_prov_confirm_"):
        await delete_provider_confirm(query, data, provider_service)
    elif data.startswith("del_prov_"):
        await prompt_delete_provider(query, data)
    elif data.startswith("add_model_"):
        await prompt_add_model(query, context, data)
    elif data.startswith("del_model_"):
        await delete_model(query, data, provider_service)
    
    # API Key management
    elif data.startswith("prov_keys_"):
        await manage_provider_keys(query, data, provider_service)
    elif data.startswith("add_key_"):
        await prompt_add_key(query, context, data)
    elif data.startswith("toggle_key_"):
        await toggle_api_key(query, data, provider_service)
    elif data.startswith("del_key_confirm_"):
        await delete_api_key_confirm(query, data, provider_service)
    elif data.startswith("del_key_"):
        await delete_api_key(query, data, provider_service)
    

    # Strategy
    elif data == "set_strategy_single":
        await select_single_provider(query, provider_service)
    elif data.startswith("single_prov_"):
        await select_single_model(query, data, provider_service)
    elif data.startswith("single_final_"):
        await save_single_strategy(query, data, config_service)
    elif data == "set_strategy_rr":
        await manage_rr_strategy(query, config_service, provider_service)
    elif data == "add_rr_pair":
        await select_rr_provider(query, provider_service)
    elif data.startswith("rr_prov_"):
        await select_rr_model(query, data, provider_service)
    elif data.startswith("rr_final_"):
        await save_rr_pair(query, data, config_service)
    elif data.startswith("remove_rr_"):
        await remove_rr_pair(query, data, config_service)
    
    # Fallback
    elif data.startswith("set_fb_"):
        await select_fallback_provider(query, context, data, provider_service)
    elif data.startswith("fb_prov_"):
        await select_fallback_model(query, context, data, provider_service)
    elif data.startswith("fb_final_"):
        await save_fallback(query, data, config_service)
    elif data == "clear_fb_all":
        await config_service.set("fallback_rules", "{}")
        await query.answer("✅ All fallback rules cleared.")
        await render_fallback_menu(query, config_service, provider_service)
    
    # Default Models
    elif data == "admin_ai_defaults":
        await render_defaults_menu(query, config_service, provider_service)
    elif data.startswith("set_def_"):
        await select_default_provider(query, data, provider_service)
    elif data.startswith("defprov_"):
        await select_default_model(query, data, provider_service)
    elif data.startswith("deffinal_"):
        await save_default_model(query, data, config_service)
    elif data.startswith("clear_def_"):
        await clear_default_model(query, data, config_service, provider_service)


async def render_ai_menu(query):
    """Render AI settings main menu."""
    keyboard = [
        [InlineKeyboardButton("🤖 Models & Providers", callback_data="admin_ai_models")],
        [InlineKeyboardButton("⚙️ Strategy Settings", callback_data="admin_ai_strategy")],
        [InlineKeyboardButton("🎯 Default Models", callback_data="admin_ai_defaults")],
        [InlineKeyboardButton("🔄 Fallback Rules", callback_data="admin_ai_fallback")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
    ]
    await query.edit_message_text(
        "🤖 **AI Settings**\
\
Configure models, providers, and fallback strategies.",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def render_models_providers(query, provider_service):
    """Render models and providers list."""
    providers = await provider_service.get_all_providers()
    all_models = await provider_service.get_all_unique_models()
    
    text = "🤖 **Models & Providers**\
\
"
    
    # Show all unique models
    text += f"**All Models** ({len(all_models)}):\
"
    for model in all_models[:10]:  # Show first 10
        text += f"• `{model}`\
"
    if len(all_models) > 10:
        text += f"_...and {len(all_models) - 10} more_\
"
    
    text += "\
**Providers**:\
"
    keyboard = []
    for p in providers:
        status = "✅" if p.is_active else "❌"
        text += f"{status} **{p.name}** - {p.client_type}\
"
        keyboard.append([
            InlineKeyboardButton(f"{status} {p.name}", callback_data=f"toggle_prov_{p.id}"),
            InlineKeyboardButton("📄 Details", callback_data=f"view_prov_details_{p.id}")
        ])
    
    keyboard.append([InlineKeyboardButton("➕ Add Provider", callback_data="add_provider")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_ai_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def prompt_add_provider(query, context):
    """Prompt user to add a provider."""
    context.user_data['awaiting_config'] = "add_provider"
    await query.message.reply_text(
        "➕ **Add Provider**\
\
"
        "Send provider details in format:\
"
        "`name base_url client_type`\
\
"
        "Example: `OpenAI https://api.openai.com/v1 openai`\
"
        "Client types: `openai` or `google`",
        parse_mode="Markdown"
    )


async def toggle_provider(query, data, provider_service):
    """Toggle provider active status."""
    provider_id = int(data.split("_")[-1])
    provider = await provider_service.get_provider(provider_id)
    
    if provider:
        new_status = not provider.is_active
        await provider_service.set_provider_active(provider_id, new_status)
        status_text = "enabled" if new_status else "disabled"
        await query.answer(f"✅ Provider {status_text}!")
        await render_models_providers(query, provider_service)


async def view_provider_details(query, data, provider_service):
    """View provider details with management options."""
    provider_id = int(data.split("_")[-1])
    provider = await provider_service.get_provider(provider_id)
    models = await provider_service.get_models_for_provider(provider_id)
    
    if not provider:
        await query.answer("⚠️ Provider not found!", show_alert=True)
        return
    
    status = "✅ Active" if provider.is_active else "❌ Inactive"
    
    text = (
        f"📄 **Provider Details**\
\
"
        f"**Name**: {provider.name}\
"
        f"**Type**: {provider.client_type}\
"
        f"**Status**: {status}\
"
        f"**Base URL**: `{provider.base_url}`\
"
        f"**Models**: {len(models)} configured\
"
    )
    
    keyboard = [
        [InlineKeyboardButton("📝 View Models", callback_data=f"view_prov_models_{provider_id}")],
        [InlineKeyboardButton("🔑 Manage API Keys", callback_data=f"prov_keys_{provider_id}")],
        [InlineKeyboardButton("🗑️ Delete Provider", callback_data=f"del_prov_{provider_id}")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_ai_models")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def view_provider_models(query, data, provider_service):
    """View models for a specific provider."""
    provider_id = int(data.split("_")[-1])
    provider = await provider_service.get_provider(provider_id)
    models = await provider_service.get_models_for_provider(provider_id)
    
    text = f"🤖 **Models for {provider.name}**\
\
"
    
    keyboard = []
    if models:
        for model in models:
            text += f"• `{model.model}`\
"
            keyboard.append([
                InlineKeyboardButton(f"🗑️ Delete: {model.model}", callback_data=f"del_model_{model.id}")
            ])
    else:
        text += "_No models configured_\
"
    
    keyboard.append([InlineKeyboardButton("➕ Add Model", callback_data=f"add_model_{provider_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"view_prov_details_{provider_id}")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def prompt_add_model(query, context, data):
    """Prompt user to add a model."""
    provider_id = data.split("_")[-1]
    context.user_data['awaiting_config'] = f"add_model_{provider_id}"
    await query.message.reply_text(
        "🤖 **Add Model**\
\
Send the model name (e.g., `gpt-4`, `gemini-pro`):",
        parse_mode="Markdown"
    )


async def delete_model(query, data, provider_service):
    """Delete a model."""
    model_id = int(data.split("_")[-1])
    
    # Get model info before deletion
    model = await provider_service.model_repo.find_by_id(model_id)
    if model:
        await provider_service.model_repo.delete(model_id)
        await query.answer("✅ Model deleted!")
        # Refresh the models list
        await view_provider_models(query, f"view_prov_models_{model.provider_id}", provider_service)


async def prompt_delete_provider(query, data):
    """Prompt confirmation for provider deletion."""
    provider_id = data.split("_")[-1]
    
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirm Delete", callback_data=f"del_prov_confirm_{provider_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"view_prov_details_{provider_id}")]
    ]
    
    await query.edit_message_text(
        "⚠️ **WARNING**\
\
This will delete the provider and all its models permanently!\
\
Are you sure?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def delete_provider_confirm(query, data, provider_service):
    """Delete provider after confirmation."""
    provider_id = int(data.split("_")[-1])
    
    await provider_service.delete_provider(provider_id)
    await query.answer("✅ Provider deleted!")
    await render_models_providers(query, provider_service)


async def manage_provider_keys(query, data, provider_service):
    """Manage API keys for a provider."""
    provider_id = int(data.split("_")[-1])
    provider = await provider_service.get_provider(provider_id)
    
    if not provider:
        await query.answer("⚠️ Provider not found!", show_alert=True)
        return
    
    # Get all API keys for this provider
    api_keys = await provider_service.get_api_keys(provider_id)
    
    text = f"🔑 **API Keys for {provider.name}**\n\n"
    
    keyboard = []
    
    if api_keys:
        text += f"**Total Keys**: {len(api_keys)}\n\n"
        for i, key in enumerate(api_keys, 1):
            # Mask the API key for security (show first 8 and last 4 chars)
            masked_key = f"{key.key[:8]}...{key.key[-4:]}" if len(key.key) > 12 else "***"
            status = "✅" if key.is_active else "❌"
            text += f"{i}. {status} `{masked_key}`\n"
            
            # Add toggle and delete buttons for each key
            keyboard.append([
                InlineKeyboardButton(
                    f"{status} Toggle Key {i}", 
                    callback_data=f"toggle_key_{key.id}"
                ),
                InlineKeyboardButton(
                    f"🗑️ Delete Key {i}", 
                    callback_data=f"del_key_{key.id}"
                )
            ])
    else:
        text += "_No API keys configured_\n"
    
    # Add button to add new key
    keyboard.append([InlineKeyboardButton("➕ Add API Key", callback_data=f"add_key_{provider_id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"view_prov_details_{provider_id}")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def prompt_add_key(query, context, data):
    """Prompt user to add an API key."""
    provider_id = data.split("_")[-1]
    context.user_data['awaiting_config'] = f"add_key_{provider_id}"
    await query.message.reply_text(
        "🔑 **Add API Key**\n\n"
        "Send the API key value:",
        parse_mode="Markdown"
    )


async def toggle_api_key(query, data, provider_service):
    """Toggle API key active status."""
    key_id = int(data.split("_")[-1])
    
    # Get the key to find its current status and provider
    key = await provider_service.api_key_repo.find_by_id(key_id)
    if not key:
        await query.answer("⚠️ API key not found!", show_alert=True)
        return
    
    # Toggle status
    new_status = not key.is_active
    await provider_service.api_key_repo.update_active_status(key_id, new_status)
    
    status_text = "enabled" if new_status else "disabled"
    await query.answer(f"✅ API key {status_text}!")
    
    # Refresh the keys list
    await manage_provider_keys(query, f"prov_keys_{key.provider_id}", provider_service)


async def delete_api_key(query, data, provider_service):
    """Delete an API key with confirmation."""
    key_id = int(data.split("_")[-1])
    
    # Get the key to find its provider
    key = await provider_service.api_key_repo.find_by_id(key_id)
    if not key:
        await query.answer("⚠️ API key not found!", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirm Delete", callback_data=f"del_key_confirm_{key_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"prov_keys_{key.provider_id}")]
    ]
    
    await query.edit_message_text(
        "⚠️ **WARNING**\n\n"
        "This will permanently delete this API key!\n\n"
        "Are you sure?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def delete_api_key_confirm(query, data, provider_service):
    """Confirm and delete API key."""
    key_id = int(data.split("_")[-1])
    
    # Get the key to find its provider before deletion
    key = await provider_service.api_key_repo.find_by_id(key_id)
    if not key:
        await query.answer("⚠️ API key not found!", show_alert=True)
        return
    
    provider_id = key.provider_id
    
    # Delete the key
    await provider_service.api_key_repo.delete(key_id)
    await query.answer("✅ API key deleted!")
    
    # Refresh the keys list
    await manage_provider_keys(query, f"prov_keys_{provider_id}", provider_service)


async def render_strategy_menu(query, config_service):

    """Render strategy settings menu."""
    strategy = await config_service.get_strategy()
    model = await config_service.get_model()
    provider_id = await config_service.get_active_provider_id()
    
    text = "⚙️ AI Strategy Settings\n\n"
    text += f"Current Strategy: {strategy.upper()}\n"
    text += f"Default Model: {model}\n"
    if provider_id:
        text += f"Provider ID: {provider_id}\n"
    
    keyboard = [
        [InlineKeyboardButton("📌 Set Single (Default)", callback_data="set_strategy_single")],
        [InlineKeyboardButton("🔄 Set Round Robin", callback_data="set_strategy_rr")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_ai_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def select_single_provider(query, provider_service):
    """Select provider for single strategy."""
    providers = await provider_service.get_active_providers()
    
    keyboard = []
    for p in providers:
        keyboard.append([InlineKeyboardButton(p.name, callback_data=f"single_prov_{p.id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_ai_strategy")])
    
    await query.edit_message_text(
        "📌 **Select Provider for Single Strategy**:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def select_single_model(query, data, provider_service):
    """Select model for single strategy."""
    provider_id = int(data.split("_")[-1])
    models = await provider_service.get_models_for_provider(provider_id)
    
    if not models:
        await query.answer("⚠️ No models configured for this provider.", show_alert=True)
        return
    
    keyboard = []
    for m in models:
        keyboard.append([InlineKeyboardButton(m.model, callback_data=f"single_final_{provider_id}_{m.model}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="set_strategy_single")])
    
    await query.edit_message_text(
        "📌 **Select Model**:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def save_single_strategy(query, data, config_service):
    """Save single strategy configuration."""
    parts = data.split("_")
    provider_id = int(parts[2])
    model = "_".join(parts[3:])
    
    await config_service.set_strategy("single")
    await config_service.set_active_provider_id(provider_id)
    await config_service.set_model(model)
    
    await query.answer("✅ Single strategy configured!")
    await render_strategy_menu(query, config_service)


async def manage_rr_strategy(query, config_service, provider_service):
    """Manage round robin strategy."""
    polling_config = await config_service.get_polling_config()
    
    text = "🔄 **Round Robin Configuration**\
\
"
    
    if polling_config:
        text += "**Configured Pairs**:\
"
        for i, pair in enumerate(polling_config):
            prov = await provider_service.get_provider(pair['provider_id'])
            prov_name = prov.name if prov else "Unknown"
            text += f"{i+1}. `{pair['model']}` ({prov_name})\
"
    else:
        text += "_No pairs configured_\
"
    
    keyboard = [
        [InlineKeyboardButton("➕ Add Pair", callback_data="add_rr_pair")]
    ]
    
    for i in range(len(polling_config)):
        keyboard.append([InlineKeyboardButton(f"🗑️ Remove Pair {i+1}", callback_data=f"remove_rr_{i}")])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_ai_strategy")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def select_rr_provider(query, provider_service):
    """Select provider for RR pair."""
    providers = await provider_service.get_active_providers()
    
    keyboard = []
    for p in providers:
        keyboard.append([InlineKeyboardButton(p.name, callback_data=f"rr_prov_{p.id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="set_strategy_rr")])
    
    await query.edit_message_text(
        "➕ **Select Provider for RR Pair**:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def select_rr_model(query, data, provider_service):
    """Select model for RR pair."""
    provider_id = int(data.split("_")[-1])
    models = await provider_service.get_models_for_provider(provider_id)
    
    if not models:
        await query.answer("⚠️ No models configured.", show_alert=True)
        return
    
    keyboard = []
    for m in models:
        keyboard.append([InlineKeyboardButton(m.model, callback_data=f"rr_final_{provider_id}_{m.model}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="add_rr_pair")])
    
    await query.edit_message_text(
        "➕ **Select Model**:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def save_rr_pair(query, data, config_service):
    """Save RR pair."""
    parts = data.split("_")
    provider_id = int(parts[2])
    model = "_".join(parts[3:])
    
    config = await config_service.get_polling_config()
    
    # Check duplicates
    for pair in config:
        if pair['provider_id'] == provider_id and pair['model'] == model:
            await query.answer("⚠️ This pair already exists!", show_alert=True)
            return
    
    config.append({"provider_id": provider_id, "model": model})
    await config_service.set_polling_config(config)
    await config_service.set_strategy("round_robin")
    
    await query.answer("✅ Pair added!")
    # Return to RR management
    from src.core.infrastructure import ProviderService
    await manage_rr_strategy(query, config_service, ProviderService())


async def remove_rr_pair(query, data, config_service):
    """Remove RR pair."""
    index = int(data.split("_")[-1])
    config = await config_service.get_polling_config()
    
    if 0 <= index < len(config):
        config.pop(index)
        await config_service.set_polling_config(config)
        await query.answer("✅ Pair removed!")
        from src.core.infrastructure import ProviderService
        await manage_rr_strategy(query, config_service, ProviderService())


async def render_fallback_menu(query, config_service, provider_service):
    """Render fallback rules menu."""
    rules = await config_service.get_fallback_rules()
    
    text = "🔄 **Fallback Rules**\
\
"
    text += "Define which model to use for specific media types when the default model is incompatible.\
\
"
    
    media_types = {
        'image': '🖼️',
        'video': '🎬', 
        'audio': '🎵',
        'file': '📄'
    }
    
    for media_type, icon in media_types.items():
        if media_type in rules:
            rule = rules[media_type]
            prov = await provider_service.get_provider(rule['provider_id'])
            prov_name = prov.name if prov else "Unknown"
            text += f"{icon} **{media_type.title()}**: `{rule['model']}` ({prov_name})\
"
        else:
            text += f"{icon} **{media_type.title()}**: _Not configured_\
"
    
    keyboard = [
        [InlineKeyboardButton("🖼️ Set Image Fallback", callback_data="set_fb_image")],
        [InlineKeyboardButton("🎬 Set Video Fallback", callback_data="set_fb_video")],
        [InlineKeyboardButton("🎵 Set Audio Fallback", callback_data="set_fb_audio")],
        [InlineKeyboardButton("📄 Set File Fallback", callback_data="set_fb_file")],
        [InlineKeyboardButton("🗑️ Clear All", callback_data="clear_fb_all")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_ai_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def select_fallback_provider(query, context, data, provider_service):
    """Select provider for fallback."""
    media_type = data.split("_")[-1]
    context.user_data['fb_media_type'] = media_type
    
    providers = await provider_service.get_active_providers()
    
    keyboard = []
    for p in providers:
        keyboard.append([InlineKeyboardButton(p.name, callback_data=f"fb_prov_{media_type}_{p.id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_ai_fallback")])
    
    await query.edit_message_text(
        f"🔄 **Select Provider for {media_type.upper()} Fallback**:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def select_fallback_model(query, context, data, provider_service):
    """Select model for fallback."""
    parts = data.split("_")
    media_type = parts[2]
    provider_id = int(parts[3])
    
    models = await provider_service.get_models_for_provider(provider_id)
    
    if not models:
        await query.answer("⚠️ No models configured.", show_alert=True)
        return
    
    keyboard = []
    for m in models:
        keyboard.append([InlineKeyboardButton(m.model, callback_data=f"fb_final_{media_type}_{provider_id}_{m.model}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"set_fb_{media_type}")])
    
    await query.edit_message_text(
        f"🔄 **Select Model for {media_type.upper()}**:",
        reply_markup=InlineKeyboardMarkup(keyboard)
    )


async def save_fallback(query, data, config_service):
    """Save fallback rule."""
    parts = data.split("_")
    media_type = parts[2]
    provider_id = int(parts[3])
    model = "_".join(parts[4:])
    
    await config_service.set_fallback_rule(media_type, model, provider_id)
    
    await query.answer(f"✅ {media_type.title()} fallback configured!")
    from src.core.infrastructure import ProviderService
    await render_fallback_menu(query, config_service, ProviderService())


# ── Default Models ────────────────────────────────────────────────────

# Feature type labels used in UI text and callback data
_DEFAULT_MODEL_FEATURES = {
    "search": {"label": "🔍 Search (/s)", "getter": "get_search_model", "setter": "set_search_model"},
    "summary": {"label": "📊 Summary (/summary)", "getter": "get_summary_default_model", "setter": "set_summary_default_model"},
    "recommend": {"label": "🍿 Recommend (/recommend)", "getter": "get_recommend_model", "setter": "set_recommend_model"},
}


async def render_defaults_menu(query, config_service, provider_service):
    """Render the default models configuration menu."""
    text = "🎯 **Default Models**\n\nSet dedicated models for specific features.\nWhen not set, the global strategy model is used.\n\n"

    for key, feat in _DEFAULT_MODEL_FEATURES.items():
        getter = getattr(config_service, feat["getter"])
        model, provider_id = await getter()
        if model:
            prov = await provider_service.get_provider(provider_id) if provider_id else None
            prov_name = prov.name if prov else "—"
            text += f"{feat['label']}: `{model}` ({prov_name})\n"
        else:
            text += f"{feat['label']}: _Not set (use global)_\n"

    keyboard = []
    clear_buttons = []

    for key, feat in _DEFAULT_MODEL_FEATURES.items():
        # Extact emoji from the label (e.g., "🔍 Search (/s)" -> "🔍")
        emoji = feat['label'].split(' ')[0]
        feature_name = key.capitalize()
        
        keyboard.append([InlineKeyboardButton(f"{emoji} Set {feature_name} Model", callback_data=f"set_def_{key}")])
        clear_buttons.append(InlineKeyboardButton(f"🗑️ Clear {feature_name}", callback_data=f"clear_def_{key}"))

    # Group clear buttons into rows of 2
    for i in range(0, len(clear_buttons), 2):
        keyboard.append(clear_buttons[i:i+2])

    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_ai_menu")])

    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def select_default_provider(query, data, provider_service):
    """Select a provider for a default model feature (search / summary)."""
    # data = "set_def_search" or "set_def_summary"
    feature = data.split("_")[-1]  # "search" or "summary"
    feat_info = _DEFAULT_MODEL_FEATURES.get(feature)
    if not feat_info:
        await query.answer("⚠️ Unknown feature.", show_alert=True)
        return

    providers = await provider_service.get_active_providers()
    keyboard = []
    for p in providers:
        keyboard.append([InlineKeyboardButton(p.name, callback_data=f"defprov_{feature}_{p.id}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_ai_defaults")])

    await query.edit_message_text(
        f"🎯 **Select Provider for {feat_info['label']}**:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def select_default_model(query, data, provider_service):
    """Select a model after choosing a provider for a default model feature."""
    # data = "defprov_search_3" or "defprov_summary_3"
    parts = data.split("_")
    feature = parts[1]  # "search" or "summary"
    provider_id = int(parts[2])
    models = await provider_service.get_models_for_provider(provider_id)

    if not models:
        await query.answer("⚠️ No models configured for this provider.", show_alert=True)
        return

    feat_info = _DEFAULT_MODEL_FEATURES.get(feature, {})
    keyboard = []
    for m in models:
        keyboard.append([InlineKeyboardButton(m.model, callback_data=f"deffinal_{feature}_{provider_id}_{m.model}")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data=f"set_def_{feature}")])

    await query.edit_message_text(
        f"🎯 **Select Model for {feat_info.get('label', feature)}**:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown",
    )


async def save_default_model(query, data, config_service):
    """Save the selected default model for a feature."""
    # data = "deffinal_search_3_gpt-4" or "deffinal_summary_3_gemini-pro"
    parts = data.split("_")
    feature = parts[1]  # "search" or "summary"
    provider_id = int(parts[2])
    model = "_".join(parts[3:])

    feat_info = _DEFAULT_MODEL_FEATURES.get(feature)
    if not feat_info:
        await query.answer("⚠️ Unknown feature.", show_alert=True)
        return

    setter = getattr(config_service, feat_info["setter"])
    await setter(model, provider_id)

    await query.answer(f"✅ {feat_info['label']} model set to {model}!")
    from src.core.infrastructure import ProviderService
    await render_defaults_menu(query, config_service, ProviderService())


async def clear_default_model(query, data, config_service, provider_service):
    """Clear a default model setting (revert to global)."""
    # data = "clear_def_search" or "clear_def_summary"
    feature = data.split("_")[-1]
    feat_info = _DEFAULT_MODEL_FEATURES.get(feature)
    if not feat_info:
        await query.answer("⚠️ Unknown feature.", show_alert=True)
        return

    setter = getattr(config_service, feat_info["setter"])
    await setter(None, None)

    await query.answer(f"✅ {feat_info['label']} model cleared!")
    await render_defaults_menu(query, config_service, provider_service)
