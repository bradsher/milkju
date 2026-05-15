"""统一AI响应数据结构

提供标准化的AI响应格式，自动分离思考过程和最终答案。
"""

from __future__ import annotations

from dataclasses import dataclass


@dataclass
class AIResponse:
    """统一的AI响应
    
    自动分离思考过程（thinking）和最终答案（answer）。
    
    Attributes:
        thinking: 思考过程（推理模型专用）
        answer: 最终答案
    
    Example:
        >>> response = AIResponse()
        >>> response.thinking = "让我分析一下..."
        >>> response.answer = "答案是..."
        >>> print(response.has_thinking)  # True
        >>> print(response.full_response)  # 完整内容
    """
    
    thinking: str = ""  # 思考过程
    answer: str = ""    # 最终答案
    
    @property
    def has_thinking(self) -> bool:
        """是否包含思考过程"""
        return bool(self.thinking.strip())
    
    @property
    def full_response(self) -> str:
        """完整响应（思考+答案）"""
        if self.has_thinking:
            return f"{self.thinking}\n\n{self.answer}"
        return self.answer
    
    @property
    def display_answer(self) -> str:
        """用于显示的答案（优先answer，无answer时用thinking）"""
        return self.answer if self.answer else self.thinking
    
    def to_dict(self) -> dict:
        """转为字典
        
        Returns:
            包含thinking, answer, has_thinking的字典
        """
        return {
            "thinking": self.thinking,
            "answer": self.answer,
            "has_thinking": self.has_thinking,
            "full_response": self.full_response
        }
    
    def copy(self) -> AIResponse:
        """创建副本"""
        return AIResponse(thinking=self.thinking, answer=self.answer)
