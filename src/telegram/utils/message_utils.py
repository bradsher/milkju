"""Telegram message utilities for safe and robust message handling.

This module provides utilities to safely send, edit, and reply to messages
with automatic parse mode detection and fallback handling.
"""

from __future__ import annotations

import re
import logging
from typing import Optional
from telegram import Message, error
from telegram.ext import ContextTypes

logger = logging.getLogger(__name__)

# Telegram message length limit
MAX_MESSAGE_LENGTH = 4096


def telegram_escape(text: str) -> str:
    """Escape text for Telegram HTML parse mode.
    
    Only escapes &, <, and >.
    """
    if not text:
        return text
    return text.replace('&', '&amp;').replace('<', '&lt;').replace('>', '&gt;')

def sanitize_html_for_telegram(text: str) -> str:
    """Sanitize HTML content to be compatible with Telegram's HTML parser.
    
    Args:
        text: The HTML text to sanitize.
    
    Returns:
        Sanitized HTML text that Telegram can parse correctly.
    """
    if not text:
        return text
    
    # Replace <br> tags with newlines
    text = re.sub(r'<br\s*/?>(\s*\n)?', '\n', text, flags=re.IGNORECASE)
    
    # Remove unsupported tags but keep content? 
    # For now, we trust markdown_to_html, but let's ensure we don't have unclosed tags or illegal entities.
    # Actually, the biggest issue was &#x27;.
    
    return text.strip()


def detect_parse_mode(text: str) -> Optional[str]:
    """Detect the most appropriate parse mode for a text message.
    
    Args:
        text: The message text to analyze.
    
    Returns:
        'HTML', 'Markdown', or None based on detected formatting.
    """
    if not text:
        return None
    
    # Check for HTML tags
    html_patterns = [
        r'<b>.*?</b>',
        r'<i>.*?</i>',
        r'<code>.*?</code>',
        r'<pre>.*?</pre>',
        r'<a\s+href=',
        r'<blockquote',
        r'<br\s*/?>',
        r'<u>.*?</u>',
        r'<s>.*?</s>',
        r'<tg-spoiler>',
    ]
    
    for pattern in html_patterns:
        if re.search(pattern, text, re.IGNORECASE | re.DOTALL):
            return 'HTML'
    
    # Check for Markdown patterns
    markdown_patterns = [
        r'\*\*.*?\*\*',  # Bold
        r'__.*?__',      # Bold alternative
        r'\*.*?\*',      # Italic
        r'_.*?_',        # Italic alternative
        r'`.*?`',        # Inline code
        r'```.*?```',    # Code block
        r'\[.*?\]\(.*?\)',  # Links
    ]
    
    for pattern in markdown_patterns:
        if re.search(pattern, text, re.DOTALL):
            return 'Markdown'
    
    # No special formatting detected
    return None


async def send_message_safe(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    text: str,
    parse_mode: Optional[str] = 'auto',
    **kwargs
) -> Optional[Message]:
    """Safely send a message with automatic parse mode fallback.
    
    Args:
        context: Bot context.
        chat_id: Target chat ID.
        text: Message text to send.
        parse_mode: Parse mode to use. 'auto' for automatic detection,
                    'HTML', 'Markdown', None, or other valid modes.
        **kwargs: Additional arguments to pass to send_message.
    
    Returns:
        Sent Message object, or None if failed.
    """
    # Auto-detect parse mode if requested
    if parse_mode == 'auto':
        parse_mode = detect_parse_mode(text)
    
    # Sanitize HTML content if using HTML mode
    if parse_mode == 'HTML':
        text = sanitize_html_for_telegram(text)
    
    # Try sending with the specified parse mode
    modes_to_try = []
    
    if parse_mode == 'HTML':
        modes_to_try = ['HTML', 'Markdown', None]
    elif parse_mode == 'Markdown':
        modes_to_try = ['Markdown', None]
    elif parse_mode is None:
        modes_to_try = [None]
    else:
        modes_to_try = [parse_mode, None]
    
    last_error = None
    
    for mode in modes_to_try:
        try:
            return await context.bot.send_message(
                chat_id=chat_id,
                text=text,
                parse_mode=mode,
                **kwargs
            )
        except error.BadRequest as e:
            if "Can't parse entities" in str(e) or "Can't parse" in str(e):
                logger.warning(f"Parse error with mode '{mode}': {e}. Trying fallback...")
                last_error = e
                continue
            else:
                # Other BadRequest errors should be raised
                raise
        except Exception as e:
            logger.error(f"Error sending message: {e}")
            raise
    
    # All modes failed
    logger.error(f"Failed to send message with all parse modes. Last error: {last_error}")
    return None


async def edit_message_safe(
    message: Message,
    text: str,
    parse_mode: Optional[str] = 'auto',
    **kwargs
) -> Optional[Message]:
    """Safely edit a message with automatic parse mode fallback.
    
    Args:
        message: Message object to edit.
        text: New message text.
        parse_mode: Parse mode to use. 'auto' for automatic detection,
                    'HTML', 'Markdown', None, or other valid modes.
        **kwargs: Additional arguments to pass to edit_text.
    
    Returns:
        Edited Message object, or None if failed.
    """
    # Auto-detect parse mode if requested
    if parse_mode == 'auto':
        parse_mode = detect_parse_mode(text)
    
    # Sanitize HTML content if using HTML mode
    if parse_mode == 'HTML':
        text = sanitize_html_for_telegram(text)
    
    # Try editing with the specified parse mode
    modes_to_try = []
    
    if parse_mode == 'HTML':
        modes_to_try = ['HTML', 'Markdown', None]
    elif parse_mode == 'Markdown':
        modes_to_try = ['Markdown', None]
    elif parse_mode is None:
        modes_to_try = [None]
    else:
        modes_to_try = [parse_mode, None]
    
    last_error = None
    
    for mode in modes_to_try:
        try:
            return await message.edit_text(
                text=text,
                parse_mode=mode,
                **kwargs
            )
        except error.BadRequest as e:
            if "Can't parse entities" in str(e) or "Can't parse" in str(e):
                logger.warning(f"Parse error with mode '{mode}': {e}. Trying fallback...")
                last_error = e
                continue
            else:
                # Other BadRequest errors should be raised
                raise
        except Exception as e:
            logger.error(f"Error editing message: {e}")
            raise
    
    # All modes failed
    logger.error(f"Failed to edit message with all parse modes. Last error: {last_error}")
    return None


async def reply_message_safe(
    message: Message,
    text: str,
    parse_mode: Optional[str] = 'auto',
    **kwargs
) -> Optional[Message]:
    """Safely reply to a message with automatic parse mode fallback.
    
    If the original message is not found (e.g., deleted by a bot), this will
    automatically fallback to sending a regular message to the same chat.
    
    Args:
        message: Message object to reply to.
        text: Reply text.
        parse_mode: Parse mode to use. 'auto' for automatic detection,
                    'HTML', 'Markdown', None, or other valid modes.
        **kwargs: Additional arguments to pass to reply_text.
    
    Returns:
        Sent Message object, or None if failed.
    """
    # Auto-detect parse mode if requested
    if parse_mode == 'auto':
        parse_mode = detect_parse_mode(text)
    
    # Sanitize HTML content if using HTML mode
    if parse_mode == 'HTML':
        text = sanitize_html_for_telegram(text)
    
    # Try replying with the specified parse mode
    modes_to_try = []
    
    if parse_mode == 'HTML':
        modes_to_try = ['HTML', 'Markdown', None]
    elif parse_mode == 'Markdown':
        modes_to_try = ['Markdown', None]
    elif parse_mode is None:
        modes_to_try = [None]
    else:
        modes_to_try = [parse_mode, None]
    
    last_error = None
    
    for mode in modes_to_try:
        try:
            return await message.reply_text(
                text=text,
                parse_mode=mode,
                **kwargs
            )
        except error.BadRequest as e:
            error_msg = str(e)
            
            # Check if the original message was deleted (e.g., by nmbot)
            if "message to be replied not found" in error_msg.lower():
                logger.warning(
                    f"Original message not found (possibly deleted by bot). "
                    f"Falling back to regular message in chat {message.chat_id}"
                )
                
                # Fallback: send as regular message instead of reply
                try:
                    # Get bot instance from message
                    bot = message.get_bot()
                    return await bot.send_message(
                        chat_id=message.chat_id,
                        text=text,
                        parse_mode=mode,
                        **kwargs
                    )
                except Exception as fallback_error:
                    logger.error(f"Fallback send_message also failed: {fallback_error}")
                    # Continue trying other parse modes with fallback
                    last_error = fallback_error
                    continue
            
            elif "Can't parse entities" in error_msg or "Can't parse" in error_msg:
                logger.warning(f"Parse error with mode '{mode}': {e}. Trying fallback...")
                last_error = e
                continue
            else:
                # Other BadRequest errors should be raised
                raise
        except Exception as e:
            logger.error(f"Error replying to message: {e}")
            raise
    
    # All modes failed
    logger.error(f"Failed to reply to message with all parse modes. Last error: {last_error}")
    return None


def _chunk_message(text: str, max_length: int = MAX_MESSAGE_LENGTH) -> list[str]:
    """Split a long message into chunks at natural break points while preserving HTML tag integrity.
    
    Args:
        text: Text to split.
        max_length: Maximum length per chunk.
    
    Returns:
        List of text chunks with complete HTML tags.
    """
    if len(text) <= max_length:
        return [text]
    
    chunks = []
    current_chunk = ""
    
    # Track open HTML tags using a stack
    open_tags = []
    
    # Split by paragraphs first (double newline)
    paragraphs = text.split('\n\n')
    
    for para in paragraphs:
        # If adding this paragraph exceeds limit, save current chunk
        if current_chunk and len(current_chunk) + len(para) + 2 > max_length:
            # Close any open tags before ending chunk
            closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
            chunks.append((current_chunk + closing_tags).strip())
            
            # Start new chunk by reopening tags
            current_chunk = ''.join(f'<{tag}>' for tag in open_tags) + para
        # If paragraph itself is too long, split by sentences
        elif len(para) > max_length:
            if current_chunk:
                closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
                chunks.append((current_chunk + closing_tags).strip())
                current_chunk = ''.join(f'<{tag}>' for tag in open_tags)
            
            # Split long paragraph by sentences
            sentences = para.replace('. ', '.\n').split('\n')
            for sentence in sentences:
                if current_chunk and len(current_chunk) + len(sentence) + 1 > max_length:
                    closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
                    chunks.append((current_chunk + closing_tags).strip())
                    current_chunk = ''.join(f'<{tag}>' for tag in open_tags) + sentence
                elif len(sentence) > max_length:
                    # If single sentence is too long, hard split
                    if current_chunk:
                        closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
                        chunks.append((current_chunk + closing_tags).strip())
                        current_chunk = ''.join(f'<{tag}>' for tag in open_tags)
                    
                    while len(sentence) > max_length:
                        closing_tags = ''.join(f'</{tag}>' for tag in reversed(open_tags))
                        chunk_part = sentence[:max_length - len(closing_tags)]
                        chunks.append((current_chunk + chunk_part + closing_tags).strip())
                        sentence = sentence[len(chunk_part):]
                        current_chunk = ''.join(f'<{tag}>' for tag in open_tags)
                    current_chunk += sentence
                else:
                    current_chunk += (" " if current_chunk and not current_chunk.endswith('>') else "") + sentence
        else:
            current_chunk += ("\n\n" if current_chunk and not current_chunk.endswith('>') else "") + para
        
        # Update open_tags based on HTML tags in current_chunk
        # Find all HTML tags in the ENTIRE current_chunk
        import re
        tag_pattern = r'<(/?)(\w+)[^>]*>'
        temp_tags = []
        for match in re.finditer(tag_pattern, current_chunk):
            is_closing = match.group(1) == '/'
            tag_name = match.group(2).lower()
            
            # Skip self-closing tags and void elements
            if match.group(0).endswith('/>') or tag_name in ['br', 'hr', 'img']:
                continue
            
            if is_closing:
                # Remove from temp_tags
                if temp_tags and temp_tags[-1] == tag_name:
                    temp_tags.pop()
            else:
                temp_tags.append(tag_name)
        
        # Update open_tags to match current state
        open_tags = temp_tags
    
    if current_chunk:
        chunks.append(current_chunk.strip())
    
    return chunks


async def send_long_message(
    message: Message,
    text: str,
    parse_mode: Optional[str] = 'auto',
    **kwargs
) -> list[Optional[Message]]:
    """Send a potentially long message, splitting into multiple messages if needed.
    
    Args:
        message: Message object to reply to.
        text: Text to send (may be longer than Telegram's limit).
        parse_mode: Parse mode to use. 'auto' for automatic detection.
        **kwargs: Additional arguments to pass to reply_text.
    
    Returns:
        List of sent Message objects.
    """
    # Auto-detect parse mode if requested
    if parse_mode == 'auto':
        parse_mode = detect_parse_mode(text)
    
    # Sanitize HTML content if using HTML mode
    if parse_mode == 'HTML':
        text = sanitize_html_for_telegram(text)
    
    # Check if message needs splitting
    if len(text) <= MAX_MESSAGE_LENGTH:
        # Single message - use regular reply
        result = await reply_message_safe(message, text, parse_mode=parse_mode, **kwargs)
        return [result] if result else []
    
    # Split into chunks
    chunks = _chunk_message(text, MAX_MESSAGE_LENGTH)
    logger.info(f"Splitting long message into {len(chunks)} chunks")
    
    sent_messages = []
    
    for i, chunk in enumerate(chunks):
        try:
            if i == 0:
                # First chunk - reply to original message
                msg = await reply_message_safe(message, chunk, parse_mode=parse_mode, **kwargs)
            else:
                # Subsequent chunks - reply to original message to keep context
                msg = await message.reply_text(
                    text=chunk,
                    parse_mode=parse_mode,
                    **kwargs
                )
            
            if msg:
                sent_messages.append(msg)
        except Exception as e:
            logger.error(f"Error sending chunk {i+1}/{len(chunks)}: {e}")
            # Continue sending remaining chunks
    
    return sent_messages
