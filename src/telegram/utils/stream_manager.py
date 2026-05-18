import logging
import time
from src.telegram.utils.message_splitter import HTMLSplitter
from src.core.message_config import DRAFT_UPDATE_INTERVAL, FALLBACK_UPDATE_INTERVAL

logger = logging.getLogger(__name__)

class StreamManager:
    """流式消息状态管理器"""
    
    def __init__(self):
        self.primary_mode = "draft"       # "draft" | "fallback"
        self.update_interval = DRAFT_UPDATE_INTERVAL
        self.fallback_interval = FALLBACK_UPDATE_INTERVAL
        self.last_update_time = 0
        self.retry_after = 0
        self.message_ids = []             # 所有已定稿的 message_id
        self.fallback_message = None      # 回退模式中编辑的消息对象
        
        self.draft_id = 1                 # 当前草稿 ID
        self.buffer = ""                  # 当前段内容缓冲区
        
        # 集成 HTMLSplitter
        self.splitter = HTMLSplitter()
        
    def should_update(self) -> bool:
        """检查是否达到更新间隔"""
        current_time = time.time()
        interval = self.update_interval if self.primary_mode == "draft" else self.fallback_interval
        return (current_time - self.last_update_time) >= interval
        
    def mark_updated(self):
        """记录更新时间"""
        self.last_update_time = time.time()
        
    def handle_429(self, retry_after: int):
        """捕获 429 错误，执行回退。"""
        self.primary_mode = "fallback"
        self.retry_after = retry_after
        self.update_interval = self.fallback_interval
        
        logger.warning(
            f"Flood control triggered. "
            f"Switching to fallback mode. "
            f"Retry after {retry_after}s."
        )
        
    def append_content(self, content: str):
        """追加内容到缓冲区"""
        self.buffer += content
        
    def check_split(self) -> tuple[str, str]:
        """
        检查是否需要分段。
        如果需要，返回 (chunk_text, remaining_buffer)
        否则返回 ("", self.buffer)
        """
        chunk, remaining = self.splitter.split_off(self.buffer)
        if chunk:
            self.buffer = remaining
        return chunk, self.buffer
