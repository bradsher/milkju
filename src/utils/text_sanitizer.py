"""Text sanitizer utility for handling sensitive content."""

from typing import Dict


class TextSanitizer:
    """Sanitizes text by inserting zero-width spaces into sensitive words."""
    
    # 敏感词列表
    SENSITIVE_WORDS = [
        '淫水', '骚逼', '大鸡吧', '阴唇', '肛交', 
        '乳交', '操逼', '粉穴', '轮奸'
    ]
    
    # 零宽空格字符
    ZWSP = '\u200b'
    
    def __init__(self):
        """Initialize sanitizer with pre-computed sanitized versions."""
        self._sanitized_map: Dict[str, str] = self._build_sanitized_map()
    
    def _build_sanitized_map(self) -> Dict[str, str]:
        """Build mapping of sensitive words to their sanitized versions.
        
        Returns:
            Dictionary mapping original words to zero-width space versions.
        """
        return {
            word: self.ZWSP.join(word)
            for word in self.SENSITIVE_WORDS
        }
    
    def sanitize(self, text: str) -> str:
        """Sanitize text by inserting zero-width spaces into sensitive words.
        
        Args:
            text: Original text content.
            
        Returns:
            Sanitized text with zero-width spaces inserted.
        """
        if not text:
            return text
            
        sanitized_text = text
        for word, sanitized in self._sanitized_map.items():
            if word in sanitized_text:
                sanitized_text = sanitized_text.replace(word, sanitized)
        
        return sanitized_text


# 全局实例，避免重复创建
_sanitizer = TextSanitizer()


def sanitize_text(text: str) -> str:
    """Convenience function to sanitize text.
    
    Args:
        text: Text to sanitize.
        
    Returns:
        Sanitized text.
    """
    return _sanitizer.sanitize(text)
