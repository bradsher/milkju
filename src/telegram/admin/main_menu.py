"""Main menu and routing for admin panel."""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, constants
from telegram.ext import ContextTypes
from src.services import PermissionService


async def admin_panel(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point for admin panel."""
    permission_service = PermissionService()
    user_id = update.effective_user.id
    
    # Check permissions
    if not await permission_service.check_admin_from_update(update):
        await update.message.reply_text("⛔ You are not an admin. ")
        return

    # Only private chat
    if update.effective_chat.type not in [constants.ChatType.PRIVATE]:
        return

    # ✅ P1: Check if user is super admin for System Config access
    is_super_admin = await permission_service.is_super_admin(user_id)

    keyboard = [
        [InlineKeyboardButton("🤖 AI Settings", callback_data="admin_ai_menu")],
        [InlineKeyboardButton("🎨 NovelAI", callback_data="admin_nai_menu")],
        [InlineKeyboardButton("💬 Chat Settings", callback_data="admin_chat_menu")],
        [InlineKeyboardButton("📁 File & Storage", callback_data="admin_file_menu")],
    ]
    
    # ✅ P2: Super admin exclusive features
    if is_super_admin:
        keyboard.append([InlineKeyboardButton("👥 Admin Management", callback_data="admin_mgmt_menu")])
        keyboard.append([InlineKeyboardButton("🔧 System Config", callback_data="admin_sys_menu")])
    
    await update.message.reply_text(
        "⚙️ **Admin Control Panel**\n\nSelect a module to manage:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def admin_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Router for admin callbacks."""
    query = update.callback_query
    await query.answer()
    data = query.data

    # ✅ P1: Permission middleware - all admin callbacks require Bot admin privileges
    permission_service = PermissionService()
    user_id = query.from_user.id
    
    if not await permission_service.is_admin(user_id):
        await query.answer("⛔ Unauthorized. Admin privileges required.", show_alert=True)
        return

    # Import sub-handlers
    from .ai_settings import handle_ai_callback
    from .chat_settings import handle_chat_callback
    from .system_settings import handle_sys_callback
    from .file_settings import handle_file_callback
    from .admin_management import handle_admin_mgmt_callback
    from .novelai_settings import handle_nai_callback
    
    if data == "admin_main":
        await admin_panel_callback(query)
    elif data.startswith("admin_mgmt"):
        await handle_admin_mgmt_callback(update, context)
    elif data.startswith("admin_ai") or data.startswith("admin_ai_"):
        await handle_ai_callback(update, context)
    elif data.startswith("admin_chat"):
        await handle_chat_callback(update, context)
    elif data.startswith("admin_sys"):
        await handle_sys_callback(update, context)
    elif data.startswith("admin_file"):
        await handle_file_callback(update, context)
    elif data.startswith("admin_nai") or data.startswith("nai_"):
        await handle_nai_callback(update, context)
    # AI Settings sub-routes
    elif data in ["add_provider"] or data.startswith(("toggle_prov_", "view_prov_", "del_prov_", "add_model_", "del_model_", "prov_keys_", "add_key_", "toggle_key_", "del_key_")):
        await handle_ai_callback(update, context)
    # Chat Settings sub-routes
    elif data.startswith(("set_history", "set_max_tokens", "set_summary", "toggle_summary")):
        await handle_chat_callback(update, context)
    # File Settings sub-routes
    elif data.startswith(("view_file", "set_max_size", "set_retention", "clean_old", "delete_all")):
        await handle_file_callback(update, context)
    # Strategy and Fallback routes
    elif data.startswith(("single_", "rr_", "add_rr", "remove_rr", "set_strategy", "set_fb", "fb_", "clear_fb")):

        await handle_ai_callback(update, context)
    # System settings routes
    elif data.startswith(("sys_set_", "sys_msg_", "sys_toggle_", "sys_delete_")):
        await handle_sys_callback(update, context)


async def admin_panel_callback(query):
    """Render main menu via callback."""
    # ✅ P1: Check super admin status for System Config button
    from src.services import PermissionService
    permission_service = PermissionService()
    user_id = query.from_user.id
    is_super_admin = await permission_service.is_super_admin(user_id)
    
    keyboard = [
        [InlineKeyboardButton("🤖 AI Settings", callback_data="admin_ai_menu")],
        [InlineKeyboardButton("🎨 NovelAI", callback_data="admin_nai_menu")],
        [InlineKeyboardButton("💬 Chat Settings", callback_data="admin_chat_menu")],
        [InlineKeyboardButton("📁 File & Storage", callback_data="admin_file_menu")],
    ]
    
    # ✅ P2: Super admin exclusive features
    if is_super_admin:
        keyboard.append([InlineKeyboardButton("👥 Admin Management", callback_data="admin_mgmt_menu")])
        keyboard.append([InlineKeyboardButton("🔧 System Config", callback_data="admin_sys_menu")])
    
    await query.edit_message_text(
        "⚙️ **Admin Control Panel**\n\nSelect a module to manage:",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )
