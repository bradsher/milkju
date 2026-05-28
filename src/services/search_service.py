"""Search service for web search functionality"""

from __future__ import annotations

from typing import Optional
import logging

from ddgs import DDGS
import asyncio

# Clean import from Layer 2 (AI Manager)
from src.ai import AIManager, MultimodalInput

logger = logging.getLogger(__name__)


class SearchService:
    """Web搜索和AI总结服务
    
    Layer 3 service that depends on Layer 2 (AI Manager).
    """

    def __init__(self, ai_manager: Optional[AIManager] = None):
        """初始化搜索服务
        
        Args:
            ai_manager: AI管理器实例
        """
        self.ai_manager = ai_manager or AIManager()

    def _sync_search(self, query: str, max_results: int) -> list:
        """同步执行网络搜索."""
        with DDGS() as ddgs:
            return list(ddgs.text(
                query,
                region='wt-wt',
                safesearch='moderate',
                max_results=max_results,
                backend='auto'
            ))

    async def search(self, query: str, chat_id: int, max_results: int = 20, model: Optional[str] = None) -> str:
        """执行网络搜索并返回AI总结
        
        Args:
            query: 搜索关键词
            chat_id: 聊天ID（用于选择AI模型）
            max_results: 最大搜索结果数
            model: 强制指定的AI模型 (可选)
            
        Returns:
            HTML格式的搜索结果和AI总结
            
        Raises:
            ValueError: 搜索词为空
            Exception: 网络或API错误
        """
        if not query or not query.strip():
            raise ValueError("Search query cannot be empty")

        logger.info(f"Searching for: {query}")

        try:
            # 1. 执行DuckDuckGo搜索 (使用 to_thread 避免阻塞 event loop)
            results = []
            search_results = await asyncio.to_thread(self._sync_search, query, max_results)
            logger.info(f"Found {len(search_results)} results")
            
            for result in search_results:
                results.append({
                    'title': result.get('title', 'No title'),
                    'link': result.get('href', ''),
                    'snippet': result.get('body', 'No description'),
                })

            if not results:
                logger.warning(f"No results found for query: {query}")
                return "🔍 No results found for your query."

            logger.info(f"Processed {len(results)} results successfully")
            
            # 2. 构建AI提示词
            search_context = self._format_results_for_ai(query, results)
            
            # 3. 使用统一AI接口获取总结
            summary = await self._get_ai_summary(chat_id, query, search_context, model)

            # 4. 格式化最终输出
            output = self._format_final_output(summary, results)

            return output

        except Exception as e:
            logger.error(f"Search error: {e}", exc_info=True)
            raise Exception(f"Search failed: {str(e)}")

    def _format_results_for_ai(self, query: str, results: list[dict]) -> str:
        """格式化搜索结果供AI处理
        
        Args:
            query: 原始搜索词
            results: 搜索结果列表
            
        Returns:
            格式化的文本
        """
        context = f"User searched for: {query}\n\n"
        context += "Search Results:\n\n"
        
        for i, result in enumerate(results, 1):
            context += f"{i}. {result['title']}\n"
            context += f"   {result['snippet']}\n"
            context += f"   Source: {result['link']}\n\n"
        
        return context

    async def _get_ai_summary(self, chat_id: int, query: str, search_context: str, model: Optional[str] = None) -> str:
        """使用统一AI接口获取搜索结果总结
        
        Args:
            chat_id: 聊天ID
            query: 搜索词
            search_context: 格式化的搜索结果
            model: 强制指定的模型
            
        Returns:
            AI生成的总结
        """
        # 构建系统提示词
        system_prompt = """你是一个专业的搜索助手和信息整合专家。

你的任务：
1. 仔细阅读所有搜索结果，提取最相关、最权威的信息
2. 用清晰、结构化的方式回答用户问题（2-3段）
3. 如果结果中有矛盾信息，指出关键差异
4. 保持客观，必要时引用来源编号 [1], [2] 等
5. **重要**：用与用户提问相同的语言回答（英文问题→英文回答，中文问题→中文回答）

回答要点：
- 学术问题：提供准确定义和清晰解释
- 新闻话题：突出最新信息和关键事件
- 技术问题：给出实用建议和最佳实践"""

        # 构建用户提示词
        user_prompt = f"{search_context}\n\n请基于以上搜索结果，简要但全面地回答用户的问题：{query}"

        try:
            # 使用AI Manager (Layer 2)
            input_data = MultimodalInput(text=user_prompt)
            
            response = await self.ai_manager.get_simple_response(
                input_data=input_data,
                chat_id=chat_id,
                system_prompt=system_prompt,
                model=model
            )
            
            # 返回answer部分（总结不需要thinking）
            return response.display_answer
            
        except Exception as e:
            logger.error(f"AI summary error: {e}", exc_info=True)
            # 降级处理：返回基础格式
            return f"Found {len(search_context)} results for: {query}"

    def _format_final_output(self, summary: str, results: list[dict]) -> str:
        """格式化最终输出（总结+来源链接）
        
        Args:
            summary: AI生成的总结
            results: 原始搜索结果
            
        Returns:
            HTML格式的输出
        """
        output = f"🔍 <b>Search Results</b>\n\n"
        output += f"{summary}\n\n"
        output += f"<b>📚 Sources ({len(results[:8])} of {len(results)}):</b>\n"
        
        for i, result in enumerate(results[:8], 1):
            # Telegram HTML链接格式
            title = result['title'][:50] + "..." if len(result['title']) > 50 else result['title']
            snippet = result['snippet'][:80] + "..." if len(result['snippet']) > 80 else result['snippet']
            output += f"{i}. <a href=\"{result['link']}\">{title}</a>\n"
            output += f"   <i>{snippet}</i>\n\n"
        
        # 添加DuckDuckGo搜索链接
        import urllib.parse
        search_url = f"https://duckduckgo.com/?q={urllib.parse.quote(results[0].get('title', '')[:50])}" if results else ""
        if search_url:
            output += f"\n🌐 <a href=\"{search_url}\">View more on DuckDuckGo</a>"
        
        return output
