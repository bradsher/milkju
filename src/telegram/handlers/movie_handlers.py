"""Telegram handlers for movie recommendation commands."""

from __future__ import annotations

import logging
from telegram import Update
from telegram.ext import ContextTypes

from src.services.movie_service import MovieService
from src.services.permission_service import PermissionService
from src.telegram.utils.message_sender import MessageSender, telegram_escape

logger = logging.getLogger(__name__)


async def recommend_command(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Handle /recommend command for movie recommendations.
    
    Usage: /recommend 电影1,电影2,电影3
    Example: /recommend 肖申克的救赎,楚门的世界,美丽人生
    
    Args:
        update: Telegram update object.
        context: Telegram context object.
    """
    # ✅ P1: Permission restriction removed - all users can use movie recommendations

    # Check if user provided films
    if not context.args:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text="📽️ <b>电影推荐使用方法</b>\n\n"
            "请输入1-5部你喜欢的电影，用逗号分隔：\n"
            "<code>/recommend 电影1,电影2,电影3</code>\n\n"
            "<b>示例:</b>\n"
            "<code>/recommend 肖申克的救赎,楚门的世界</code>\n\n"
            "💡 建议输入2-3部影片以获得更准确的推荐", reply_to_message_id=update.message.message_id)
        return
    
    # Parse film names
    films_input = ' '.join(context.args)
    # Support both English and Chinese commas
    films_input = films_input.replace('，', ',')  # Replace Chinese comma with English
    liked_films = [f.strip() for f in films_input.split(',') if f.strip()]
    
    # Limit to 5 films
    if len(liked_films) > 5:
        await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=f"⚠️ 最多支持5部影片，已截取前5部进行分析", reply_to_message_id=update.message.message_id)
        liked_films = liked_films[:5]
    
    # Send processing message
    processing_msg_ids = await MessageSender(bot=context.bot, chat_id=update.effective_chat.id).send_static(
        text="🎬 <b>正在分析您的观影口味...</b>\n\n"
        f"基于影片: {', '.join([f'《{f}》' for f in liked_films])}\n\n"
        "⏳ 这需要5-10秒，请稍候...",
        reply_to_message_id=update.message.message_id
    )
    
    try:
        # Initialize service (AI interface is handled internally)
        movie_service = MovieService()
        
        # Get recommendations
        chat_id = update.effective_chat.id
        result = await movie_service.recommend_films(
            liked_films=liked_films,
            chat_id=chat_id
        )
        
        # Format response
        response_text = "🎬 <b>为您推荐以下电影</b>\n\n"
        
        # Add user analysis if available
        if "user_analysis" in result:
            analysis = result["user_analysis"]
            response_text += "📊 <b>您的观影偏好分析：</b>\n"
            if "core_themes" in analysis:
                response_text += f"• 主题: {analysis['core_themes']}\n"
            if "emotional_tone" in analysis:
                response_text += f"• 情感: {analysis['emotional_tone']}\n"
            if "narrative_style" in analysis:
                response_text += f"• 叙事: {analysis['narrative_style']}\n"
            response_text += "\n"
        
        response_text += f"基于您喜欢的影片: {', '.join([f'《{f}》' for f in liked_films])}\n\n"
        response_text += "━━━━━━━━━━━━━━━\n\n"
        
        # Add recommendations
        recommendations = result.get("recommendations", [])
        for i, rec in enumerate(recommendations, 1):
            # Prefer actual_title from API (Chinese) over AI suggested title (English)
            metadata = rec.get("metadata", {})
            actual_title = metadata.get("actual_title", "")
            ai_title = rec.get("title", "未知影片")
            
            # Use actual_title if available and different, otherwise use AI title
            if actual_title and actual_title != ai_title:
                title = actual_title
                logger.info(f"Using API title '{actual_title}' instead of AI title '{ai_title}'")
            else:
                title = ai_title
            
            reason = rec.get("reason", "无推荐理由")
            rec_type = rec.get("type", "")
            
            # Add type emoji
            type_emoji = ""
            if rec_type == "safe":
                type_emoji = "✅"
            elif rec_type == "niche":
                type_emoji = "💎"
            elif rec_type == "surprise":
                type_emoji = "🎁"
            
            # Format title with hyperlink if search_url is available
            search_url = metadata.get("search_url", "")
            
            if search_url:
                # Use Telegram HTML hyperlink format: <a href="URL">text</a>
                title_html = f'<a href="{search_url}">《{title}》</a>'
            else:
                title_html = f"《{title}》"
            
            response_text += f"<b>{i}. {type_emoji} {title_html}</b>\n"
            response_text += f"{reason}\n"
            
            # Add metadata if available
            year = metadata.get("year", "N/A")
            rating = metadata.get("rating", "N/A")
            source = metadata.get("source", "")
            
            if year != "N/A" or rating != "N/A":
                metadata_line = f"📅 {year}年 | ⭐ {rating}/10"
                if source:
                    metadata_line += f" | 📊 {source}"
                response_text += metadata_line + "\n"
            
            response_text += "\n"
        
        # Add footer
        response_text += "━━━━━━━━━━━━━━━\n"
        response_text += "💡 提示: 本推荐基于AI深度分析，不存储您的个人数据"
        
        # Delete processing message
        try:
            await context.bot.delete_message(chat_id=chat_id, message_id=processing_msg_ids[0])
        except Exception as e:
            logger.warning(f"Failed to delete processing message: {e}")
        
        # Send recommendations using unified sender
        sender = MessageSender(bot=context.bot, chat_id=chat_id)
        await sender.send_static(text=response_text, reply_to_message_id=update.message.message_id)
        
        logger.info(f"Successfully sent {len(recommendations)} recommendations for films: {liked_films}")
        
    except ValueError as e:
        # User input validation errors
        await context.bot.edit_message_text(
            chat_id=chat_id,
            message_id=processing_msg_ids[0],
            text=f"❌ <b>输入错误</b>\n\n{str(e)}",
            parse_mode="HTML"
        )
        
    except Exception as e:
        # General errors
        logger.error(f"Movie recommendation error: {e}", exc_info=True)
        
        error_msg = (
            "❌ <b>推荐失败</b>\n\n"
            "可能的原因:\n"
            "• TMDB API未配置或超时\n"
            "• AI服务暂时不可用\n"
            "• 影片名称无法识别\n\n"
            "请稍后重试或联系管理员"
        )
        
        try:
            await context.bot.edit_message_text(text=error_msg, chat_id=chat_id, message_id=processing_msg_ids[0], parse_mode="HTML")
        except:
            await MessageSender(bot=update.message.get_bot(), chat_id=update.message.chat_id, parse_mode="HTML").send_static(text=error_msg, reply_to_message_id=update.message.message_id)
