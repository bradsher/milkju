"""Core constants and enums for TeleChat application."""

from __future__ import annotations

from enum import Enum, auto
from datetime import timezone, timedelta


# Database
DB_NAME = "bot.db"

# Timezone
UTC8 = timezone(timedelta(hours=8))

# Configuration Keys
class ConfigKey(str, Enum):
    """Database configuration keys."""

    MODEL = "model"
    STRATEGY = "strategy"
    ACTIVE_PROVIDER_ID = "active_provider_id"
    POLLING_PROVIDER_IDS = "polling_provider_ids"
    HISTORY_LIMIT = "history_limit"
    GROUP_HISTORY_LIMIT = "group_history_limit"
    MAX_TOKENS = "max_tokens"
    SUMMARY_LANGUAGE = "summary_language"
    SUMMARY_PERMISSION_REQUIRED = "summary_permission_required"


# Strategy Types
class StrategyType(str, Enum):
    """AI provider selection strategies."""

    SINGLE = "single"
    ROUND_ROBIN = "round_robin"


# Client Types
class ClientType(str, Enum):
    """AI client types."""

    OPENAI = "openai"
    GOOGLE = "google"


# Message Roles
class MessageRole(str, Enum):
    """Message roles in conversation."""

    SYSTEM = "system"
    USER = "user"
    ASSISTANT = "assistant"


# Callback Data Patterns
class CallbackPattern(str, Enum):
    """Patterns for callback query data."""

    # Admin Panel
    ADMIN_MAIN = "admin_main"
    ADMIN_VIEW = "admin_view"
    ADMIN_PROVIDERS = "admin_providers"
    ADMIN_KEYS = "admin_keys"
    ADMIN_VIEW_MODELS = "admin_view_models"
    ADMIN_SET_SINGLE = "admin_set_single"
    ADMIN_SET_RR = "admin_set_rr"
    ADMIN_SET_LIMIT = "admin_set_limit"
    ADMIN_SET_GROUP_LIMIT = "admin_set_group_limit"
    ADMIN_SET_MAX_TOKENS = "admin_set_max_tokens"
    ADMIN_SET_SUMMARY_LANG = "admin_set_summary_lang"
    ADMIN_TOGGLE_SUMMARY_PERM = "admin_toggle_summary_perm"
    ADMIN_CLEAN_MESSAGES = "admin_clean_messages"

    # Provider Management
    ADD_PROV = "add_prov"
    DEL_PROV = "del_prov_"  # + provider_id
    VIEW_PROV_MODELS = "view_prov_models_"  # + provider_id
    ADD_PROV_MODEL = "add_prov_model_"  # + provider_id
    DEL_PROV_MODEL = "del_prov_model_"  # + model_id
    SET_CLIENT_TYPE = "set_client_type_"  # + type

    # API Keys
    VIEW_KEYS = "view_keys_"  # + provider_id
    ADD_KEY = "add_key_"  # + provider_id
    DEL_KEY = "del_key_"  # + key_id

    # Model Selection
    SET_SINGLE_PROV = "set_single_prov_"  # + provider_id
    SET_SINGLE_FINAL = "set_single_final_"  # + provider_id + model
    SET_RR_MODEL = "set_rr_model_"  # + model
    TOGGLE_RR = "toggle_rr_"  # + provider_id
    CONFIRM_RR = "confirm_rr"

    # Chat Settings
    SET_MODEL_PROV = "set_model_prov_"  # + provider_id
    SET_MODEL_FINAL = "set_model_final_"  # + provider_id + model
    SET_MODEL_BACK = "set_model_back"
    SET_MODEL_RESET = "set_model_reset"
    CANCEL_ACTION = "cancel_action"

    # Message Cleanup
    SYS_MSG_CLEANUP_MENU = "sys_msg_cleanup_menu"
    SYS_TOGGLE_AUTO_CLEANUP = "sys_toggle_auto_cleanup"
    SYS_SET_CLEANUP_DAYS = "sys_set_cleanup_days"
    SYS_DELETE_ALL_MESSAGES = "sys_delete_all_messages"
    SYS_DELETE_ALL_CONFIRM = "sys_delete_all_confirm"


# Admin Input States
class AdminInputState(str, Enum):
    """States for admin input handling."""

    ADD_PROVIDER_NAME = "add_provider_name"
    ADD_PROVIDER_URL = "add_provider_url"
    ADD_API_KEY = "add_api_key"
    ADD_PROVIDER_MODEL = "add_provider_model"
    CLEAN_MESSAGES_DURATION = "clean_messages_duration"
    HISTORY_LIMIT = "history_limit"
    GROUP_HISTORY_LIMIT = "group_history_limit"
    MAX_TOKENS = "max_tokens"
    SUMMARY_LANGUAGE = "summary_language"
    CLEANUP_DAYS = "cleanup_days"


# Default Values
class Defaults:
    """Default configuration values."""

    HISTORY_LIMIT = 20
    GROUP_HISTORY_LIMIT = 20
    MAX_TOKENS = ""  # Empty means unlimited
    SUMMARY_LANGUAGE = "Simplified Chinese"
    SUMMARY_PERMISSION = "true"  # true = Restricted (Admin only), false = Unrestricted
    CLEANUP_INTERVAL_SECONDS = 2592000  # 30 days
    
    # Default Models
    DEFAULT_MODEL = "gpt-5-mini"  # Global fallback model
    DEFAULT_FILE_MODEL = "gemini-3-flash-preview"  # File processing model
    INSURANCE_MULTIMODAL_MODEL = "gemini-3-flash-preview"  # Fallback for unsupported media


# Streaming
class StreamConfig:
    """Configuration for streaming responses."""

    UPDATE_INTERVAL_SECONDS = 2.0  # Seconds between message edits
    CURSOR_SYMBOL = " ▌"
    THINKING_EMOJI = "💭"


# UI Messages
class UIMessages:
    """User-facing messages."""

    # Errors
    ERROR_PREFIX = "❌ Error: "
    ERROR_CONFIG_MISSING = "⚠️ Configuration missing. Please check Providers and API Keys in Admin Panel."
    ERROR_PERMISSION_DENIED = "⛔ Permission Denied. Only Admins can use this command."
    ERROR_GROUP_ONLY = "⚠️ This command only works in group chats."
    ERROR_PRIVATE_ONLY = "⚠️ This command only works in private chats."
    ERROR_INVALID_FORMAT = "⚠️ Invalid format. Please check the command syntax."
    ERROR_NO_PROVIDER_MODELS = "⚠️ This provider has no models configured."

    # Success
    SUCCESS_PREFIX = "✅ "
    SUCCESS_OPERATION_CANCELLED = "🚫 Operation cancelled."
    SUCCESS_NOTHING_TO_CANCEL = "🚫 Nothing to cancel."
    SUCCESS_CONVERSATION_CLEARED = "🗑️ Conversation history cleared!"
    SUCCESS_NEW_CONVERSATION = "🔄 New conversation started! What would you like to talk about?"

    # Status
    STATUS_THINKING = "Thinking... 💭"
    STATUS_GENERATING_SUMMARY = "🔄 Generating summary... ⏳"
    STATUS_NO_MESSAGES = "📭 No messages found in the specified time range."
    STATUS_NO_RESPONSE = "❌ No response received."

    # Media
    MEDIA_SEND_AS_PHOTO = "⚠️ Please send images as 'Photo' (compressed), not as 'File'."
    MEDIA_TEXT_AND_PHOTOS_ONLY = "⚠️ I can only understand text and photos."
    MEDIA_DEFAULT_PROMPT = "Describe this image."


# Time Parsing
class TimeUnits:
    """Time unit constants for parsing."""

    SECONDS_PER_MINUTE = 60
    SECONDS_PER_HOUR = 3600
    SECONDS_PER_DAY = 86400
    MAX_SUMMARY_SECONDS = 86400  # 24 hours


# Icons
class Icons:
    """Icon constants for UI."""

    OPENAI = "🤖"
    GOOGLE = "🇬"
    ENABLED = "✅"
    DISABLED = "❌"
    THINKING = "💭"
    SUMMARY = "📊"
    ADMIN = "⚙️"
    CLEAN = "🗑️"
    KEY = "🔑"
    MODEL = "🤖"
    BACK = "🔙"
    ADD = "➕"
    CANCEL = "❌"
