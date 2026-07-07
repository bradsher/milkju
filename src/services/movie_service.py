"""Movie recommendation service"""

from __future__ import annotations

import logging
import os
import json
from typing import Optional, List, Dict, Any
from urllib.parse import quote

from tmdbv3api import TMDb, Movie, Search

# Clean import from Layer 2 (AI Manager)
from src.ai import AIManager, MultimodalInput
from src.services.anime_service import AnimeService

logger = logging.getLogger(__name__)


class MovieService:
    """电影推荐服务 - AI优先方式
    
    Layer 3 service that depends on Layer 2 (AI Manager).
    """

    def __init__(self, ai_manager: Optional[AIManager] = None):
        """初始化电影服务
        
        Args:
            ai_manager: AI管理器实例
        """
        # TMDB API
        tmdb = TMDb()
        tmdb.api_key = os.getenv('TMDB_API_KEY')
        tmdb.language = 'zh-CN'
        
        if not tmdb.api_key:
            logger.warning("TMDB_API_KEY not set in environment variables")
        
        self.movie_api = Movie()
        self.search_api = Search()
        self.tmdb = tmdb
        self.anime_service = AnimeService()
        
        # AI Manager (no more circular dependency!)
        self.ai_manager = ai_manager or AIManager()

    def _build_ai_first_prompt(self, liked_films: List[str]) -> str:
        """构建AI优先推荐提示词"""
        liked_films_text = '、'.join([f'《{f}》' for f in liked_films])
        
        return f"""你是一位资深影评人，擅长深度理解观众的观影品味并推荐优质作品。

=== 任务 ===
用户喜欢这些作品: {liked_films_text}

请完成以下步骤:

**第一步：深度分析用户口味**
基于你对这些作品的了解，分析:
1. 主题层面: 核心议题、价值观
2. 情感层面: 情感基调、氛围特点
3. 叙事层面: 节奏、结构、视角

**第二步：从你的知识库推荐10部作品**
要求:
- 7部安全推荐（与用户口味高度契合）
- 2部小众佳片（相对冷门但质量出色）
- 1部意外惊喜（跨类型但有深层共鸣）
- 每部作品需要120字内的推荐理由，说明与用户口味的契合点
- 可以推荐电影、电视剧、动画等任何形式
- **标题必须使用中文名称**（如动画使用中文译名，电影使用中文片名）
- 如果作品没有广为人知的中文名，使用日文罗马音或英文原名

**第三步：输出JSON格式**
```json
{{
  "user_analysis": {{
    "core_themes": "主题分析（2-3句话）",
    "emotional_tone": "情感基调（2-3句话）",
    "narrative_style": "叙事风格（2-3句话）"
  }},
  "recommendations": [
    {{
      "title": "作品标题（使用常见的中文或日文罗马音名称）",
      "reason": "推荐理由（120字内，说明契合点）",
      "type": "safe/niche/surprise"
    }}
  ]
}}
```

注意:
- 请确保推荐的作品真实存在
- **标题优先使用中文名称**，这样方便中国用户理解
- 如果用户输入的是动画，请优先推荐动画作品
"""

    async def _validate_and_enrich(self, title: str) -> Optional[Dict[str, Any]]:
        """验证标题并从TMDB/AniList获取元数据"""
        metadata = None
        
        # 尝试TMDB
        try:
            search_results = self.search_api.multi({'query': title})
            if search_results:
                result_list = list(search_results)
                if result_list:
                    first_result = result_list[0]
                    
                    year = "N/A"
                    if hasattr(first_result, 'release_date') and first_result.release_date:
                        year = first_result.release_date[:4]
                    elif hasattr(first_result, 'first_air_date') and first_result.first_air_date:
                        year = first_result.first_air_date[:4]
                    
                    rating = "N/A"
                    if hasattr(first_result, 'vote_average'):
                        rating = round(first_result.vote_average, 1)
                    
                    actual_title = None
                    if hasattr(first_result, 'title'):
                        actual_title = first_result.title
                    elif hasattr(first_result, 'name'):
                        actual_title = first_result.name
                    
                    encoded_title = quote(title)
                    search_url = f"https://www.themoviedb.org/search?query={encoded_title}"
                    
                    metadata = {
                        "year": year,
                        "rating": rating,
                        "search_url": search_url,
                        "source": "TMDB",
                        "actual_title": actual_title
                    }
                    logger.info(f"TMDB found: {title} -> {actual_title} ({year}, {rating}⭐)")
                    
        except Exception as e:
            logger.warning(f"TMDB search failed for '{title}': {e}")
        
        # 如果TMDB失败，尝试AniList
        if not metadata:
            try:
                anime_results = await self.anime_service.search_anime(title)
                if anime_results:
                    first_anime = anime_results[0]
                    
                    year = first_anime.get('seasonYear', 'N/A')
                    rating = first_anime.get('averageScore', 0) / 10.0 if first_anime.get('averageScore') else 'N/A'
                    anime_id = first_anime.get('id')
                    
                    search_url = f"https://anilist.co/anime/{anime_id}"
                    
                    title_obj = first_anime.get('title', {})
                    actual_title = title_obj.get('romaji') or title_obj.get('english') or title_obj.get('native')
                    
                    metadata = {
                        "year": year,
                        "rating": round(rating, 1) if isinstance(rating, (int, float)) else rating,
                        "search_url": search_url,
                        "source": "AniList",
                        "actual_title": actual_title
                    }
                    logger.info(f"AniList found: {title} -> {actual_title} ({year}, {rating}⭐)")
                    
            except Exception as e:
                logger.warning(f"AniList search failed for '{title}': {e}")
        
        # 降级处理
        if not metadata:
            encoded_title = quote(title)
            search_url = f"https://www.themoviedb.org/search?query={encoded_title}"
            metadata = {
                "year": "N/A",
                "rating": "N/A",
                "search_url": search_url,
                "source": "Fallback",
                "actual_title": title
            }
            logger.warning(f"No metadata found for '{title}', using fallback")
        
        return metadata

    async def recommend_films(
        self,
        liked_films: List[str],
        chat_id: int,
        model: Optional[str] = None,
        provider_id: Optional[int] = None
    ) -> Dict[str, Any]:
        """获取电影推荐（AI优先方式）
        
        Args:
            liked_films: 用户喜欢的1-5部影片
            chat_id: 聊天ID（用于选择AI模型）
            
        Returns:
            包含user_analysis和recommendations的字典
            
        Raises:
            ValueError: 输入影片数量不合法
            Exception: AI或API调用失败
        """
        if not liked_films:
            raise ValueError("至少需要输入一部影片")
        
        if len(liked_films) > 5:
            raise ValueError("最多支持5部影片")
        
        try:
            # 1. 构建AI提示词
            logger.info(f"Getting AI recommendations for: {liked_films}")
            prompt = self._build_ai_first_prompt(liked_films)
            
            # 2. 使用AI Manager获取推荐
            logger.info("Calling AI for recommendations...")
            input_data = MultimodalInput(text=prompt)
            
            response = await self.ai_manager.get_simple_response(
                input_data=input_data,
                chat_id=chat_id,
                model=model,
                provider_id=provider_id
            )
            
            # 使用display_answer（可能是thinking或answer）
            ai_response_text = response.display_answer
            
            # 3. 解析JSON响应
            try:
                # 提取JSON
                if "```json" in ai_response_text:
                    json_start = ai_response_text.find("```json") + 7
                    json_end = ai_response_text.find("```", json_start)
                    json_text = ai_response_text[json_start:json_end].strip()
                elif "{" in ai_response_text:
                    json_start = ai_response_text.find("{")
                    json_end = ai_response_text.rfind("}") + 1
                    json_text = ai_response_text[json_start:json_end]
                else:
                    json_text = ai_response_text
                
                result = json.loads(json_text)
                
                if "recommendations" not in result:
                    raise ValueError("Response missing recommendations")
                
                logger.info(f"AI recommended {len(result['recommendations'])} titles")
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse AI response as JSON: {e}")
                logger.error(f"Response was: {ai_response_text[:500]}")
                raise Exception("AI返回格式错误，请重试")
            
            # 4. 验证并丰富每个推荐
            logger.info("Validating and enriching recommendations with API data...")
            enriched_recommendations = []
            
            for rec in result.get("recommendations", []):
                title = rec.get("title", "")
                if not title:
                    continue
                
                # 获取元数据
                metadata = await self._validate_and_enrich(title)
                
                if metadata:
                    rec["metadata"] = metadata
                    enriched_recommendations.append(rec)
                else:
                    logger.warning(f"Skipping '{title}' - could not validate")
            
            # 更新结果
            result["recommendations"] = enriched_recommendations
            
            logger.info(f"Successfully enriched {len(enriched_recommendations)} recommendations")
            return result
            
        except Exception as e:
            logger.error(f"Movie recommendation error: {e}")
            raise
