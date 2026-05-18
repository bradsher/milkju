import re
import logging
from src.core.message_config import SOFT_LIMIT, HARD_LIMIT

logger = logging.getLogger(__name__)

class HTMLSplitter:
    """HTML 格式保全的消息分段引擎"""
    
    def __init__(self, soft_limit=SOFT_LIMIT, hard_limit=HARD_LIMIT):
        self.SOFT_LIMIT = soft_limit
        self.HARD_LIMIT = hard_limit
        
    def split(self, html_text: str) -> list[dict]:
        """
        将 HTML 格式文本安全分段。
        用于静态文本。
        """
        chunks = []
        current_chunk = ""
        current_length = 0
        tag_stack = [] # 存储完整的开始标签，如 '<b>' 或 '<a href="...">'
        
        # 正则匹配 HTML 标签
        tag_pattern = re.compile(r'<(/?)(\w+)[^>]*>')
        
        # 分词：文本和标签
        tokens = []
        last_idx = 0
        for match in tag_pattern.finditer(html_text):
            if match.start() > last_idx:
                tokens.append(('text', html_text[last_idx:match.start()]))
            tokens.append(('tag', match.group(0), match.group(1) == '/', match.group(2)))
            last_idx = match.end()
        if last_idx < len(html_text):
            tokens.append(('text', html_text[last_idx:]))
            
        for token in tokens:
            if token[0] == 'text':
                text_content = token[1]
                
                while text_content:
                    # 如果添加全部文本不超软上限
                    if current_length + len(text_content) <= self.SOFT_LIMIT:
                        current_chunk += text_content
                        current_length += len(text_content)
                        text_content = ""
                    else:
                        # 需要切分
                        remaining_space = self.SOFT_LIMIT - current_length
                        if remaining_space <= 0:
                            # 已经超过，找下一个空格
                            split_idx = text_content.find(' ')
                            if split_idx == -1 or split_idx > 100:
                                split_idx = 0
                        else:
                            # 尝试在剩余空间内找最后一个空格
                            split_idx = text_content.rfind(' ', 0, remaining_space)
                            if split_idx == -1:
                                split_idx = remaining_space # 强制切分
                                
                        current_chunk += text_content[:split_idx]
                        current_length += split_idx
                        text_content = text_content[split_idx:].lstrip()
                        
                        # 闭合当前块的所有未闭合标签
                        closed_chunk = current_chunk
                        for tag_str in reversed(tag_stack):
                            tag_name = self._extract_name(tag_str)
                            closed_chunk += f"</{tag_name}>"
                            
                        chunks.append({"text": closed_chunk, "has_open_tags": list(tag_stack)})
                        
                        # 开始新块
                        current_chunk = ""
                        current_length = 0
                        
                        # 在新块开头重开所有标签
                        for tag_str in tag_stack:
                            current_chunk += tag_str
                            current_length += len(tag_str)
                            
            elif token[0] == 'tag':
                tag_str = token[1]
                is_close = token[2]
                tag_name = token[3]
                
                current_chunk += tag_str
                current_length += len(tag_str)
                
                if is_close:
                    # 从栈底向上找匹配的开标签并移除
                    found = False
                    for idx in range(len(tag_stack) - 1, -1, -1):
                        if self._extract_name(tag_stack[idx]) == tag_name:
                            tag_stack.pop(idx)
                            found = True
                            break
                    if not found:
                        logger.warning(f"Unexpected closing tag: {tag_str}")
                else:
                    if tag_name != 'br':
                        tag_stack.append(tag_str)
                        
        # 处理最后一块
        if current_chunk:
            closed_chunk = current_chunk
            for tag_str in reversed(tag_stack):
                tag_name = self._extract_name(tag_str)
                closed_chunk += f"</{tag_name}>"
            chunks.append({"text": closed_chunk, "has_open_tags": list(tag_stack)})
            
        return chunks

    def split_off(self, buffer: str) -> tuple[str, str]:
        """
        从 buffer 中切分出第一段，返回 (chunk_text, remaining_buffer_with_reopens)
        如果未达到软上限，返回 ("", buffer)
        用于流式分段。
        """
        current_length = 0
        tag_stack = []
        tag_pattern = re.compile(r'<(/?)(\w+)[^>]*>')
        
        tokens = []
        last_idx = 0
        for match in tag_pattern.finditer(buffer):
            if match.start() > last_idx:
                tokens.append(('text', buffer[last_idx:match.start()]))
            tokens.append(('tag', match.group(0), match.group(1) == '/', match.group(2)))
            last_idx = match.end()
        if last_idx < len(buffer):
            tokens.append(('text', buffer[last_idx:]))
            
        current_chunk = ""
        for i, token in enumerate(tokens):
            if token[0] == 'text':
                text_content = token[1]
                
                if current_length + len(text_content) > self.SOFT_LIMIT:
                    # 需要切分
                    remaining_space = self.SOFT_LIMIT - current_length
                    if remaining_space <= 0:
                        split_idx = text_content.find(' ')
                        if split_idx == -1 or split_idx > 100:
                            split_idx = 0
                    else:
                        split_idx = text_content.rfind(' ', 0, remaining_space)
                        if split_idx == -1:
                            split_idx = remaining_space
                            
                    current_chunk += text_content[:split_idx]
                    
                    # 闭合标签
                    closed_chunk = current_chunk
                    for tag_str in reversed(tag_stack):
                        closed_chunk += f"</{self._extract_name(tag_str)}>"
                        
                    # 构造剩余的 buffer
                    remaining_buffer = text_content[split_idx:].lstrip()
                    
                    # 添加后续的所有 token
                    for j in range(i + 1, len(tokens)):
                        remaining_buffer += tokens[j][1]
                            
                    # 在剩余 buffer 开头补上需要重开的标签
                    reopened_buffer = ""
                    for tag_str in tag_stack:
                        reopened_buffer += tag_str
                    remaining_buffer = reopened_buffer + remaining_buffer
                    
                    return closed_chunk, remaining_buffer
                else:
                    current_chunk += text_content
                    current_length += len(text_content)
                    
            elif token[0] == 'tag':
                tag_str = token[1]
                is_close = token[2]
                tag_name = token[3]
                
                current_chunk += tag_str
                current_length += len(tag_str)
                
                if is_close:
                    found = False
                    for idx in range(len(tag_stack) - 1, -1, -1):
                        if self._extract_name(tag_stack[idx]) == tag_name:
                            tag_stack.pop(idx)
                            found = True
                            break
                else:
                    if tag_name != 'br':
                        tag_stack.append(tag_str)
                        
        return "", buffer # 未发生切分

    def _extract_name(self, tag_str: str) -> str:
        """从开始标签中提取标签名，例如从 '<a href="...">' 提取 'a'"""
        match = re.search(r'<(\w+)', tag_str)
        return match.group(1) if match else ""

def strip_html(text: str) -> str:
    """移除 HTML 标签以计算纯文本长度"""
    return re.sub(r'<[^>]*>', '', text)
