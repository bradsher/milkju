"""Input handler for admin configuration."""

from telegram import Update
from telegram.ext import ContextTypes
from src.core.infrastructure import ConfigService, ProviderService


async def admin_input_handler(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle text input for admin configuration."""
    if not context.user_data.get('awaiting_config'):
        return

    from src.services import PermissionService
    permission_service = PermissionService()
    user_id = update.effective_user.id
    
    if not await permission_service.is_admin(user_id):
        await update.message.reply_text("⛔ Unauthorized access.")
        context.user_data['awaiting_config'] = None
        return

    config_type = context.user_data['awaiting_config']
    text = update.message.text.strip()
    config_service = ConfigService()
    
    try:
        # System settings
        if config_type == 'sys_timeout':
            val = int(text)
            await config_service.set_system_override("timeout", val)
            await update.message.reply_text(f"✅ System timeout set to {val} seconds.")
            
        elif config_type == 'sys_max_msg_len':
            await update.message.reply_text("ℹ️ This setting is now hardcoded in the system architecture and cannot be changed.")
            
        elif config_type == 'sys_public_rate':
            val = int(text)
            if val < 1:
                raise ValueError("Rate must be at least 1")
            await config_service.set_public_chat_rate_limit(val)
            await update.message.reply_text(f"✅ Public Chat Rate Limit set to {val} msgs/hr.")
        
        # File settings
        elif config_type == 'file_max_size':
            val = int(text)
            await config_service.set("file_max_size_mb", str(val))
            await update.message.reply_text(f"✅ Max file size set to {val} MB.")
            
        elif config_type == 'file_retention':
            val = int(text)
            await config_service.set("file_retention_days", str(val))
            await update.message.reply_text(f"✅ File retention set to {val} days.")
        
        # Chat settings
        elif config_type == 'history_private':
            val = int(text)
            await config_service.set_history_limit(val)
            await update.message.reply_text(f"✅ Private history limit set to {val} messages.")
        
        elif config_type == 'history_group':
            val = int(text)
            await config_service.set_group_history_limit(val)
            await update.message.reply_text(f"✅ Group history limit set to {val} messages.")
        
        elif config_type == 'max_tokens':
            if text.lower() in ['', 'unlimited', 'none']:
                await config_service.set_max_tokens("")
                await update.message.reply_text("✅ Max tokens set to unlimited.")
            else:
                val = int(text)
                await config_service.set_max_tokens(str(val))
                await update.message.reply_text(f"✅ Max tokens set to {val}.")
        
        elif config_type == 'summary_lang':
            await config_service.set_summary_language(text)
            await update.message.reply_text(f"✅ Summary language set to: {text}")
        
        elif config_type == 'cleanup_days':
            val = int(text)
            if val < 1:
                raise ValueError("Days must be at least 1")
            await config_service.set_auto_cleanup_days(val)
            await update.message.reply_text(f"✅ Message retention set to {val} days.")
        

        
        # ✅ P2: Admin management - only super admins can add admins
        elif config_type == 'add_admin':
            if not await permission_service.is_super_admin(user_id):
                await update.message.reply_text("⛔ Only Super Admins can add admins.")
                context.user_data['awaiting_config'] = None
                return
            
            try:
                new_admin_id = int(text)
                await permission_service.add_admin(new_admin_id, is_admin=True)
                await update.message.reply_text(f"✅ User `{new_admin_id}` is now an admin!", parse_mode="Markdown")
            except ValueError:
                await update.message.reply_text("❌ Invalid User ID. Please send a numeric ID.")
        
        # Model management
        elif config_type.startswith('add_model_'):
            provider_id = int(config_type.split('_')[-1])
            provider_service = ProviderService()
            await provider_service.create_model(provider_id, text)
        
        # Provider management
        elif config_type == 'add_provider':
            # Format: name base_url client_type
            parts = text.split()
            if len(parts) < 3:
                raise ValueError("Format must be 'name base_url client_type'")
            
            name = parts[0]
            base_url = parts[1]
            client_type = parts[2].lower()
            
            if client_type not in ['openai', 'google']:
                raise ValueError("Client type must be 'openai' or 'google'")
            
            provider_service = ProviderService()
            await provider_service.create_provider(name, base_url, client_type)
            await update.message.reply_text(f"✅ Provider **{name}** created successfully!", parse_mode="Markdown")
        
        # API Key management  
        elif config_type.startswith('add_key_'):
            provider_id = int(config_type.split('_')[-1])
            provider_service = ProviderService()
            await provider_service.create_api_key(provider_id, text)
            await update.message.reply_text("✅ API key added successfully!")
        
        # NovelAI settings
        elif config_type == 'nai_rate_limit':
            val = int(text)
            if val < 1 or val > 100:
                raise ValueError("Rate limit must be between 1-100")
            await config_service.set("nai_rate_limit", str(val))
            await update.message.reply_text(f"✅ NovelAI rate limit set to {val} generations per hour per user.")
        
        elif config_type == 'nai_negative_prompt':
            await config_service.set("nai_negative_prompt", text)
            await update.message.reply_text(f"✅ NovelAI negative prompt updated ({len(text)} chars).")
        
        elif config_type == 'nai_steps':
            val = int(text)
            if val < 1 or val > 50:
                raise ValueError("Steps must be between 1-50")
            await config_service.set("nai_steps", str(val))
            await update.message.reply_text(f"✅ NovelAI steps set to {val}.")
        
        elif config_type == 'nai_scale':
            val = float(text)
            if val < 1.0 or val > 10.0:
                raise ValueError("Scale must be between 1.0-10.0")
            await config_service.set("nai_scale", str(val))
            await update.message.reply_text(f"✅ NovelAI guidance scale set to {val}.")
        
        # Author preset management
        elif config_type == 'add_author_preset':
            # Format: preset_name author_string_content
            # First word is name, rest is content
            parts = text.split(maxsplit=1)
            if len(parts) < 2:
                raise ValueError(
                    "Format must be 'preset_name content'\n"
                    "Example: mystyle artist:xyz, style:abc"
                )
            
            preset_name = parts[0].strip()
            preset_content = parts[1].strip()
            
            if ' ' in preset_name:
                raise ValueError("Preset name cannot contain spaces")
            
            from src.services import AuthorPresetService
            preset_service = AuthorPresetService()
            await preset_service.create_preset(preset_name, preset_content, user_id)
            await update.message.reply_text(
                f"✅ Author preset `{preset_name}` created!\n\n"
                f"Use `/naia {preset_name} <prompt>` to generate with this preset.",
                parse_mode="Markdown"
            )
        
        # Fallback rules (legacy support from old format)
        elif config_type.startswith('fb_'):
            media_type = config_type.split('_')[-1]
            # Format: model, provider_id
            parts = [p.strip() for p in text.split(',')]
            if len(parts) != 2 or not parts[1].isdigit():
                raise ValueError("Format must be 'ModelName, ProviderID'")
            
            model_name = parts[0]
            provider_id = int(parts[1])
            
            await config_service.set_fallback_rule(media_type, model_name, provider_id)
            await update.message.reply_text(
                f"✅ Fallback for **{media_type}** set to `{model_name}` (Provider: {provider_id})",
                parse_mode="Markdown"
            )
        
        else:
            await update.message.reply_text(f"❓ Unknown config type: {config_type}")
            
    except ValueError as e:
        await update.message.reply_text(f"❌ Invalid input: {e}\nPlease enter a valid number.")
    except Exception as e:
        await update.message.reply_text(f"❌ Error saving config: {e}")
    finally:
        # Clear state
        context.user_data['awaiting_config'] = None
