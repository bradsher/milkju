"""File & Storage Settings module for admin panel.

Handles:
- File storage statistics
- Storage quota configuration
- Retention policy
- File cleanup operations
"""

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import ContextTypes
from src.core.infrastructure import ConfigService
from src.services.file_service import FileService


async def handle_file_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Route file settings callbacks."""
    query = update.callback_query
    data = query.data
    config_service = ConfigService()
    
    if data == "admin_file_menu":
        await render_file_menu(query, config_service)
    elif data == "view_file_stats":
        await view_storage_stats(query)
    elif data == "set_max_size":
        context.user_data['awaiting_config'] = 'file_max_size'
        await query.message.reply_text(
            "💾 **Set Max File Size**\
\
Enter size in MB (e.g., 20):",
            parse_mode="Markdown"
        )
    elif data == "set_retention":
        context.user_data['awaiting_config'] = 'file_retention'
        await query.message.reply_text(
            "📅 **Set Retention Days**\
\
Enter days (e.g., 30):",
            parse_mode="Markdown"
        )
    elif data == "clean_old_files":
        await clean_old_files(query, config_service)
    elif data == "delete_all_files":
        await confirm_delete_all(query)
    elif data == "delete_all_confirm":
        await delete_all_files(query)


async def render_file_menu(query, config_service):
    """Render file settings menu."""
    max_size = await config_service.get("file_max_size_mb") or "20"
    retention = await config_service.get("file_retention_days") or "30"
    
    text = (
        "📁 **File & Storage Settings**\
\
"
        f"💾 **Max File Size**: {max_size} MB\
"
        f"📅 **Retention Policy**: {retention} days\
"
    )
    
    keyboard = [
        [InlineKeyboardButton("📊 View Storage Stats", callback_data="view_file_stats")],
        [InlineKeyboardButton("Set Max File Size", callback_data="set_max_size")],
        [InlineKeyboardButton("Set Retention Days", callback_data="set_retention")],
        [InlineKeyboardButton("🗑️ Clean Old Files Now", callback_data="clean_old_files")],
        [InlineKeyboardButton("🗑️ Delete All Files", callback_data="delete_all_files")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_main")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def view_storage_stats(query):
    """View file storage statistics."""
    file_service = FileService()
    stats = await file_service.get_storage_stats()
    
    text = (
        "📊 **File Storage Statistics**\
\
"
        f"📁 **Total Files**: {stats['total_files']}\
"
        f"💾 **Total Size**: {stats['total_size_mb']:.2f} MB / {stats['quota_mb']} MB\
"
        f"📈 **Usage**: {stats['usage_percent']:.1f}%\
"
        f"📅 **Oldest File**: {stats['oldest_file_date']}\
"
        f"📅 **Newest File**: {stats['newest_file_date']}\
"
    )
    
    keyboard = [
        [InlineKeyboardButton("🔄 Refresh", callback_data="view_file_stats")],
        [InlineKeyboardButton("🔙 Back", callback_data="admin_file_menu")]
    ]
    
    await query.edit_message_text(
        text,
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def clean_old_files(query, config_service):
    """Clean old files based on retention policy."""
    retention = await config_service.get("file_retention_days")
    if not retention:
        retention = 30
    else:
        retention = int(retention)
    
    file_service = FileService()
    deleted_count = await file_service.cleanup_old_files(days=retention)
    
    await query.answer(f"✅ Cleaned {deleted_count} old files!")
    await view_storage_stats(query)


async def confirm_delete_all(query):
    """Confirm delete all files."""
    keyboard = [
        [InlineKeyboardButton("⚠️ Confirm Delete All", callback_data="delete_all_confirm")],
        [InlineKeyboardButton("❌ Cancel", callback_data="admin_file_menu")]
    ]
    
    await query.edit_message_text(
        "⚠️ **WARNING**: This will delete ALL uploaded files permanently!\
\
Are you sure?",
        reply_markup=InlineKeyboardMarkup(keyboard),
        parse_mode="Markdown"
    )


async def delete_all_files(query):
    """Delete all files."""
    file_service = FileService()
    deleted_count = await file_service.delete_all_files()
    
    await query.edit_message_text(
        f"✅ Deleted **{deleted_count}** files successfully.",
        parse_mode="Markdown"
    )
