"""Admin management module - Super Admin only.

Allows super admins to:
- View list of current bot admins
- Add new bot admins
- Remove bot admins (except super admins)
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.services import PermissionService


async def handle_admin_mgmt_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle admin management callbacks."""
    query = update.callback_query
    data = query.data
    permission_service = PermissionService()
    user_id = query.from_user.id
    
    # ✅ P2: Only super admins can manage admins
    if not await permission_service.is_super_admin(user_id):
        await query.answer("⛔ Only Super Admins can manage admins.", show_alert=True)
        return
    
    if data == "admin_mgmt_menu":
        await show_admin_list(query, permission_service)
    
    elif data == "admin_mgmt_add":
        context.user_data['awaiting_config'] = 'add_admin'
        await query.message.reply_text(
            "👤 **Add Admin**\n\n"
            "Send the Telegram User ID to grant admin privileges:\n"
            "Example: `123456789`",
            parse_mode="Markdown"
        )
    
    elif data.startswith("admin_mgmt_remove_confirm_"):
        target_user_id = int(data.split("_")[-1])
        await remove_admin(query, target_user_id, permission_service)
    
    elif data.startswith("admin_mgmt_remove_"):
        target_user_id = int(data.split("_")[-1])
        await show_remove_confirmation(query, target_user_id, permission_service)


async def show_admin_list(query, permission_service: PermissionService):
    """Display list of current admins."""
    admin_ids = await permission_service.get_all_admins()
    
    text = "👥 **Admin Management**\n\n"
    text += f"**Total Admins**: {len(admin_ids)}\n\n"
    
    keyboard = []
    
    if admin_ids:
        text += "**Current Admins**:\n"
        for admin_id in admin_ids:
            # Check if this admin is also a super admin
            is_super = await permission_service.is_super_admin(admin_id)
            badge = " 🔱" if is_super else ""
            text += f"• User ID: `{admin_id}`{badge}\n"
            
            # Only show remove button for non-super admins
            if not is_super:
                keyboard.append([
                    InlineKeyboardButton(
                        f"🗑️ Remove {admin_id}", 
                        callback_data=f"admin_mgmt_remove_{admin_id}"
                    )
                ])
    else:
        text += "_No admins configured_\n"
    
    text += "\n🔱 = Super Admin (cannot be removed)"
    
    keyboard.append([InlineKeyboardButton("➕ Add Admin", callback_data="admin_mgmt_add")])
    keyboard.append([InlineKeyboardButton("🔙 Back", callback_data="admin_main")])
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def show_remove_confirmation(query, target_user_id: int, permission_service: PermissionService):
    """Show confirmation dialog for removing admin."""
    # ✅ Prevent removing super admins
    if await permission_service.is_super_admin(target_user_id):
        await query.answer("⚠️ Cannot remove Super Admin!", show_alert=True)
        return
    
    text = (
        "⚠️ **Confirm Admin Removal**\n\n"
        f"Are you sure you want to remove admin privileges from user `{target_user_id}`?\n\n"
        "This action cannot be undone."
    )
    
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirm Remove", callback_data=f"admin_mgmt_remove_confirm_{target_user_id}")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_mgmt_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def remove_admin(query, target_user_id: int, permission_service: PermissionService):
    """Remove admin privileges."""
    # Double-check super admin protection
    if await permission_service.is_super_admin(target_user_id):
        await query.answer("⚠️ Cannot remove Super Admin!", show_alert=True)
        return
    
    await permission_service.remove_admin(target_user_id)
    await query.answer("✅ Admin removed successfully!")
    await show_admin_list(query, permission_service)
