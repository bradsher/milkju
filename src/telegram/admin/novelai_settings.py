"""NovelAI settings panel for admin control."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes

from src.core.infrastructure import ConfigService
from src.services import PermissionService, AuthorPresetService

# Resolution presets
RESOLUTION_PRESETS = {
    "portrait": "竖版 / Portrait (832×1216)",
    "landscape": "横版 / Landscape (1216×832)",
    "square": "方形 / Square (1024×1024)",
    "large_portrait": "大竖版 / Large Portrait (1024×1536)",
    "large_landscape": "大横版 / Large Landscape (1536×1024)",
}

# Sampler options
SAMPLERS = {
    "k_euler": "Euler",
    "k_euler_ancestral": "Euler Ancestral (推荐 / Recommended)",
    "k_dpmpp_2s_ancestral": "DPM++ 2S Ancestral",
    "k_dpmpp_2m_sde": "DPM++ 2M SDE",
    "k_dpmpp_sde": "DPM++ SDE",
}

# Model options
MODELS = {
    "nai-diffusion-4-5-full": "NAI Diffusion V4.5 Full (推荐 / Recommended)",
    "nai-diffusion-4-5-curated": "NAI Diffusion V4.5 Curated",
    "nai-diffusion-4-curated-preview": "NAI Diffusion V4 Curated",
    "nai-diffusion-3": "NAI Diffusion V3",
}


async def handle_nai_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle NovelAI settings callbacks."""
    query = update.callback_query
    data = query.data
    config_service = ConfigService()
    permission_service = PermissionService()
    user_id = query.from_user.id
    
    # Check if user is admin
    is_super_admin = await permission_service.is_super_admin(user_id)

    if not await permission_service.is_bot_admin(user_id):
        await query.answer("⛔ Only admins can access NovelAI settings.", show_alert=True)
        return
    
    if data == "admin_nai_menu":
        await show_nai_menu(query, config_service, is_super_admin)
    
    elif data == "nai_toggle_enabled":
        # Only super admin can toggle feature
        if not is_super_admin:
            await query.answer("⛔ Only Super Admins can enable/disable NovelAI feature.", show_alert=True)
            return
        
        current = await config_service.get("nai_enabled", default="true")
        new_value = "false" if current.lower() == "true" else "true"
        await config_service.set("nai_enabled", new_value)
        
        await show_nai_menu(query, config_service, is_super_admin)
        await query.answer(f"NovelAI {'enabled' if new_value == 'true' else 'disabled'}")
    
    elif data == "nai_toggle_anlas_free":
        current = await config_service.get("nai_anlas_free", default="true")
        new_value = "false" if current.lower() == "true" else "true"
        await config_service.set("nai_anlas_free", new_value)
        
        await show_nai_menu(query, config_service, is_super_admin)
        await query.answer(f"Anlas-Free mode {'enabled' if new_value == 'true' else 'disabled'}")
    
    elif data == "nai_set_rate_limit":
        context.user_data['awaiting_config'] = 'nai_rate_limit'
        await query.message.reply_text(
            "Please enter rate limit (generations per hour per user, 1-100):\n\n"
            "Example: `10`",
            parse_mode="Markdown"
        )
    
    elif data == "nai_set_negative_prompt":
        context.user_data['awaiting_config'] = 'nai_negative_prompt'
        current = await config_service.get(
            "nai_negative_prompt",
            default="lowres, bad anatomy, bad hands, text, error"
        )
        await query.message.reply_text(
            f"**Current Negative Prompt:**\n`{current[:200]}...`\n\n"
            f"Please enter new negative prompt (tags to avoid):",
            parse_mode="Markdown"
        )
    
    elif data == "nai_set_steps":
        context.user_data['awaiting_config'] = 'nai_steps'
        await query.message.reply_text(
            "Please enter sampling steps (1-50):\n\n"
            "Recommended: `28` (standard quality)\n"
            "Note: Anlas-Free mode locks this to 28",
            parse_mode="Markdown"
        )
    
    elif data == "nai_set_scale":
        context.user_data['awaiting_config'] = 'nai_scale'
        await query.message.reply_text(
            "Please enter guidance scale / CFG (1.0-10.0):\n\n"
            "Recommended: `5.0`",
            parse_mode="Markdown"
        )
    
    elif data.startswith("nai_set_resolution_"):
        preset = data.replace("nai_set_resolution_", "")
        await config_service.set("nai_resolution", preset)
        await show_nai_menu(query, config_service, is_super_admin)
        await query.answer(f"Resolution set to {RESOLUTION_PRESETS.get(preset, preset)}")
    
    elif data.startswith("nai_set_sampler_"):
        sampler = data.replace("nai_set_sampler_", "")
        await config_service.set("nai_sampler", sampler)
        await show_nai_menu(query, config_service, is_super_admin)
        await query.answer(f"Sampler changed")
    
    elif data.startswith("nai_set_model_"):
        model = data.replace("nai_set_model_", "")
        await config_service.set("nai_model", model)
        await show_nai_menu(query, config_service, is_super_admin)
        await query.answer(f"Model changed")
    
    elif data == "nai_resolution_menu":
        await show_resolution_menu(query, config_service)
    
    elif data == "nai_sampler_menu":
        await show_sampler_menu(query, config_service)
    
    elif data == "nai_model_menu":
        await show_model_menu(query, config_service)
    
    # Author preset management
    elif data == "nai_author_presets":
        await show_author_presets(query, user_id, is_super_admin)
    
    elif data == "nai_add_author_preset":
        await prompt_add_author_preset(query, context)
    
    elif data.startswith("nai_view_preset_"):
        preset_id = int(data.replace("nai_view_preset_", ""))
        await view_author_preset(query, preset_id, user_id, is_super_admin)
    
    elif data.startswith("nai_toggle_preset_"):
        preset_id = int(data.replace("nai_toggle_preset_", ""))
        await toggle_author_preset(query, preset_id, user_id, is_super_admin)
    
    elif data.startswith("nai_del_preset_confirm_"):
        preset_id = int(data.replace("nai_del_preset_confirm_", ""))
        await delete_author_preset_confirm(query, preset_id, user_id, is_super_admin)
    
    elif data.startswith("nai_del_preset_"):
        preset_id = int(data.replace("nai_del_preset_", ""))
        await prompt_delete_author_preset(query, preset_id, user_id, is_super_admin)


async def show_nai_menu(query, config_service: ConfigService, is_super_admin: bool):
    """Display main NovelAI settings menu."""
    # Get current settings
    enabled = await config_service.get("nai_enabled", default="true")
    anlas_free = await config_service.get("nai_anlas_free", default="true")
    rate_limit = await config_service.get("nai_rate_limit", default="10")
    model = await config_service.get("nai_model", default="nai-diffusion-4-5-full")
    resolution = await config_service.get("nai_resolution", default="square")
    steps = await config_service.get("nai_steps", default="28")
    scale = await config_service.get("nai_scale", default="5.0")
    sampler = await config_service.get("nai_sampler", default="k_euler_ancestral")
    negative_prompt = await config_service.get("nai_negative_prompt", default="lowres, bad anatomy...")
    
    # Format status
    enabled_icon = "✅" if enabled.lower() == "true" else "❌"
    anlas_free_icon = "✅" if anlas_free.lower() == "true" else "❌"
    
    # Get display names
    model_display = MODELS.get(model, model)[:30]
    resolution_display = RESOLUTION_PRESETS.get(resolution, resolution)
    sampler_display = SAMPLERS.get(sampler, sampler)
    
    text = (
        "🎨 **NovelAI Settings**\n\n"
        f"• **Status**: {enabled_icon} {'Enabled' if enabled.lower() == 'true' else 'Disabled'}\n"
        f"• **Anlas-Free Mode**: {anlas_free_icon} {'ON' if anlas_free.lower() == 'true' else 'OFF'}\n"
        f"• **Rate Limit**: {rate_limit}/hour/user\n\n"
        f"**Generation Settings:**\n"
        f"• **Model**: {model_display}\n"
        f"• **Resolution**: {resolution_display}\n"
        f"• **Steps**: {steps} | **Guidance**: {scale}\n"
        f"• **Sampler**: {sampler_display}\n"
        f"• **Negative Prompt**: {negative_prompt[:40]}...\n\n"
    )
    
    if anlas_free.lower() == "true":
        text += "💡 Anlas-Free mode locks resolution to ≤1024×1024 and steps to ≤28\n"
    
    keyboard = []
    
    # Feature toggle (Super Admin only)
    if is_super_admin:
        keyboard.append([InlineKeyboardButton(
            f"{'🔴 Disable' if enabled.lower() == 'true' else '🟢 Enable'} Feature",
            callback_data="nai_toggle_enabled"
        )])
    
    # Anlas-Free toggle
    keyboard.append([InlineKeyboardButton(
        f"{'🔴 Disable' if anlas_free.lower() == 'true' else '🟢 Enable'} Anlas-Free Mode",
        callback_data="nai_toggle_anlas_free"
    )])
    
    # Settings buttons
    keyboard.extend([
        [
            InlineKeyboardButton("📐 Resolution", callback_data="nai_resolution_menu"),
            InlineKeyboardButton("🔢 Steps", callback_data="nai_set_steps"),
        ],
        [
            InlineKeyboardButton("📊 Guidance", callback_data="nai_set_scale"),
            InlineKeyboardButton("🎲 Sampler", callback_data="nai_sampler_menu"),
        ],
        [InlineKeyboardButton("🚫 Negative Prompt", callback_data="nai_set_negative_prompt")],
        [InlineKeyboardButton("🤖 Model", callback_data="nai_model_menu")],
        [InlineKeyboardButton("👤 Author Presets", callback_data="nai_author_presets")],
        [InlineKeyboardButton("⏱️ Rate Limit", callback_data="nai_set_rate_limit")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")],
    ])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_resolution_menu(query, config_service: ConfigService):
    """Show resolution selection menu."""
    current = await config_service.get("nai_resolution", default="square")
    
    text = "📐 **Select Resolution**\n\n"
    for key, display in RESOLUTION_PRESETS.items():
        if key == current:
            text += f"✅ {display}\n"
        else:
            text += f"• {display}\n"
    
    keyboard = []
    for key, display in RESOLUTION_PRESETS.items():
        icon = "✅ " if key == current else ""
        keyboard.append([InlineKeyboardButton(
            f"{icon}{display}",
            callback_data=f"nai_set_resolution_{key}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_nai_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_sampler_menu(query, config_service: ConfigService):
    """Show sampler selection menu."""
    current = await config_service.get("nai_sampler", default="k_euler_ancestral")
    
    text = "🎲 **Select Sampler**\n\n"
    
    keyboard = []
    for key, display in SAMPLERS.items():
        icon = "✅ " if key == current else ""
        keyboard.append([InlineKeyboardButton(
            f"{icon}{display}",
            callback_data=f"nai_set_sampler_{key}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_nai_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_model_menu(query, config_service: ConfigService):
    """Show model selection menu."""
    current = await config_service.get("nai_model", default="nai-diffusion-4-5-full")
    
    text = "🤖 **Select Model**\n\n"
    
    keyboard = []
    for key, display in MODELS.items():
        icon = "✅ " if key == current else ""
        keyboard.append([InlineKeyboardButton(
            f"{icon}{display}",
            callback_data=f"nai_set_model_{key}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_nai_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


# ============================================================
# Author Preset Management Functions
# ============================================================

async def show_author_presets(query, user_id: int, is_super_admin: bool):
    """Display author presets list."""
    preset_service = AuthorPresetService()
    presets = await preset_service.get_all_presets()
    
    text = "👤 **Author Presets**\n\n"
    text += "Author presets let you save artist/style tags privately.\n"
    text += "Use `/naia <preset> <prompt>` to generate with a preset.\n\n"
    
    keyboard = []
    
    if presets:
        text += f"**Total Presets**: {len(presets)}\n\n"
        for preset in presets:
            status = "✅" if preset.is_active else "❌"
            owner_tag = " 👑" if preset.created_by == user_id else ""
            text += f"{status} `{preset.name}`{owner_tag}\n"
            
            # View button for each preset
            keyboard.append([InlineKeyboardButton(
                f"{status} {preset.name}",
                callback_data=f"nai_view_preset_{preset.id}"
            )])
    else:
        text += "_No presets configured_\n"
    
    keyboard.append([InlineKeyboardButton("➕ Add Preset", callback_data="nai_add_author_preset")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_nai_menu")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def prompt_add_author_preset(query, context):
    """Prompt user to add an author preset."""
    context.user_data['awaiting_config'] = 'add_author_preset'
    await query.message.reply_text(
        "👤 **Add Author Preset**\n\n"
        "Send the preset in format:\n"
        "`preset_name author_string_content`\n\n"
        "**Example:**\n"
        "`mystyle artist:xyz, style:abc, masterpiece`\n\n"
        "⚠️ Name cannot contain spaces.\n"
        "⚠️ Content is hidden from other admins.",
        parse_mode="Markdown"
    )


async def view_author_preset(query, preset_id: int, user_id: int, is_super_admin: bool):
    """View author preset details."""
    preset_service = AuthorPresetService()
    preset = await preset_service.get_preset_by_id(preset_id)
    
    if not preset:
        await query.answer("⚠️ Preset not found!", show_alert=True)
        return
    
    status = "✅ Active" if preset.is_active else "❌ Inactive"
    is_owner = preset.created_by == user_id
    can_manage = preset_service.can_manage_preset(preset, user_id, is_super_admin)
    
    # Show full content if owner/super admin, masked otherwise
    display_content = preset_service.get_display_content(preset, user_id, is_super_admin)
    content_label = "Content" if can_manage else "Content (masked)"
    
    text = (
        f"👤 **Preset Details**\n\n"
        f"**Name**: `{preset.name}`\n"
        f"**Status**: {status}\n"
        f"**{content_label}**:\n`{display_content}`\n"
    )
    
    if is_owner:
        text += "\n👑 You created this preset\n"
    
    keyboard = []
    
    if can_manage:
        keyboard.append([InlineKeyboardButton(
            f"{'🔴 Disable' if preset.is_active else '🟢 Enable'}",
            callback_data=f"nai_toggle_preset_{preset_id}"
        )])
        keyboard.append([InlineKeyboardButton(
            "🗑️ Delete Preset",
            callback_data=f"nai_del_preset_{preset_id}"
        )])
    
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="nai_author_presets")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def toggle_author_preset(query, preset_id: int, user_id: int, is_super_admin: bool):
    """Toggle author preset active status."""
    preset_service = AuthorPresetService()
    
    try:
        new_status = await preset_service.toggle_preset(preset_id, user_id, is_super_admin)
        if new_status is None:
            await query.answer("⚠️ Preset not found!", show_alert=True)
            return
        
        status_text = "enabled" if new_status else "disabled"
        await query.answer(f"✅ Preset {status_text}!")
        await view_author_preset(query, preset_id, user_id, is_super_admin)
        
    except PermissionError:
        await query.answer("⛔ You can only toggle your own presets.", show_alert=True)


async def prompt_delete_author_preset(query, preset_id: int, user_id: int, is_super_admin: bool):
    """Prompt confirmation for preset deletion."""
    preset_service = AuthorPresetService()
    preset = await preset_service.get_preset_by_id(preset_id)
    
    if not preset:
        await query.answer("⚠️ Preset not found!", show_alert=True)
        return
    
    if not preset_service.can_manage_preset(preset, user_id, is_super_admin):
        await query.answer("⛔ You can only delete your own presets.", show_alert=True)
        return
    
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirm Delete", callback_data=f"nai_del_preset_confirm_{preset_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data=f"nai_view_preset_{preset_id}")]
    ]
    
    await query.edit_message_text(
        f"⚠️ **WARNING**\n\n"
        f"Delete preset `{preset.name}`?\n\n"
        f"This action cannot be undone!",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def delete_author_preset_confirm(query, preset_id: int, user_id: int, is_super_admin: bool):
    """Confirm and delete author preset."""
    preset_service = AuthorPresetService()
    
    try:
        deleted = await preset_service.delete_preset(preset_id, user_id, is_super_admin)
        if not deleted:
            await query.answer("⚠️ Preset not found!", show_alert=True)
            return
        
        await query.answer("✅ Preset deleted!")
        await show_author_presets(query, user_id, is_super_admin)
        
    except PermissionError:
        await query.answer("⛔ You can only delete your own presets.", show_alert=True)
