"""Anime recommendation service using AniList GraphQL API."""

from __future__ import annotations

import logging
import aiohttp
import json
from typing import Optional, List, Dict, Any
from functools import lru_cache

# Clean import from Layer 2 (AI Manager)
from src.ai import AIManager, MultimodalInput

logger = logging.getLogger(__name__)


class AnimeService:
    """Service for anime recommendations using AniList GraphQL API."""
    
    ANILIST_API_URL = "https://graphql.anilist.co"
    
    def __init__(self):
        """Initialize anime service with AniList API.
        
        Note: AniList API is completely free and requires no API key.
        """
        pass
    
    @lru_cache(maxsize=100)
    def _cached_search(self, title: str) -> Optional[str]:
        """Cached search to avoid repeated queries.
        
        Returns JSON string for caching compatibility.
        """
        # This will be called by the async search_anime method
        return None
    
    async def search_anime(self, title: str, limit: int = 10) -> List[Dict[str, Any]]:
        """Search anime by title using AniList GraphQL API.
        
        Args:
            title: Anime title (supports Chinese, English, Japanese romaji)
            limit: Maximum number of results to return
            
        Returns:
            List of anime info dicts with id, title, genres, description, score
        """
        query = '''
        query ($search: String, $perPage: Int) {
          Page(page: 1, perPage: $perPage) {
            media(search: $search, type: ANIME, sort: SCORE_DESC) {
              id
              title {
                romaji
                english
                native
              }
              genres
              averageScore
              description(asHtml: false)
              format
              episodes
              seasonYear
              coverImage {
                large
              }
            }
          }
        }
        '''
        
        variables = {
            'search': title,
            'perPage': limit
        }
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ANILIST_API_URL,
                    json={'query': query, 'variables': variables},
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
                ) as response:
                    if response.status != 200:
                        logger.error(f"AniList API error: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if 'errors' in data:
                        logger.error(f"AniList GraphQL errors: {data['errors']}")
                        return []
                    
                    media_list = data.get('data', {}).get('Page', {}).get('media', [])
                    return media_list
                    
        except Exception as e:
            logger.error(f"Error searching AniList for '{title}': {e}")
            return []
    
    async def get_similar_anime(self, media_id: int, limit: int = 20) -> List[Dict[str, Any]]:
        """Get similar anime recommendations from AniList.
        
        Args:
            media_id: AniList media ID
            limit: Maximum number of similar anime to return
            
        Returns:
            List of similar anime info dicts
        """
        query = '''
        query ($id: Int) {
          Media(id: $id) {
            recommendations(perPage: 50, sort: RATING_DESC) {
              edges {
                node {
                  mediaRecommendation {
                    id
                    title {
                      romaji
                      english
                      native
                    }
                    genres
                    averageScore
                    description(asHtml: false)
                    format
                    seasonYear
                  }
                }
              }
            }
          }
        }
        '''
        
        variables = {'id': media_id}
        
        try:
            async with aiohttp.ClientSession() as session:
                async with session.post(
                    self.ANILIST_API_URL,
                    json={'query': query, 'variables': variables},
                    headers={'Content-Type': 'application/json', 'Accept': 'application/json'}
                ) as response:
                    if response.status != 200:
                        logger.error(f"AniList API error: {response.status}")
                        return []
                    
                    data = await response.json()
                    
                    if 'errors' in data:
                        logger.error(f"AniList GraphQL errors: {data['errors']}")
                        return []
                    
                    recommendations = data.get('data', {}).get('Media', {}).get('recommendations', {}).get('edges', [])
                    
                    # Extract media from recommendation nodes
                    similar_media = []
                    for edge in recommendations[:limit]:
                        media_rec = edge.get('node', {}).get('mediaRecommendation')
                        if media_rec:
                            similar_media.append(media_rec)
                    
                    return similar_media
                    
        except Exception as e:
            logger.error(f"Error getting similar anime for ID {media_id}: {e}")
            return []
    
    async def get_anime_candidates(self, liked_anime: List[str]) -> List[Dict[str, Any]]:
        """Get candidate anime for recommendations.
        
        Args:
            liked_anime: List of anime titles user likes
            
        Returns:
            List of candidate anime (deduplicated)
        """
        candidates = []
        seen_ids = set()
        
        for anime_name in liked_anime:
            # Search for the anime
            search_results = await self.search_anime(anime_name, limit=3)
            
            if not search_results:
                logger.warning(f"No AniList results for: {anime_name}")
                continue
            
            # Get the first (best) match
            best_match = search_results[0]
            media_id = best_match.get('id')
            
            if not media_id:
                continue
            
            # Get similar anime
            similar = await self.get_similar_anime(media_id, limit=20)
            
            for anime in similar:
                anime_id = anime.get('id')
                if anime_id and anime_id not in seen_ids:
                    seen_ids.add(anime_id)
                    candidates.append(anime)
        
        logger.info(f"Found {len(candidates)} unique anime candidates from AniList")
        return candidates
    
    def _build_anime_prompt(
        self,
        liked_anime: List[str],
        candidates: List[Dict[str, Any]]
    ) -> str:
        """Build LLM prompt for anime recommendations.
        
        Args:
            liked_anime: List of anime names user likes
            candidates: List of candidate anime dicts from AniList
            
        Returns:
            Formatted prompt string
        """
        # Format candidate list
        candidate_list = []
        for i, anime in enumerate(candidates[:50], 1):  # Limit to 50 to save tokens
            title_info = anime.get('title', {})
            title = title_info.get('romaji', title_info.get('english', '未知'))
            genres = ', '.join(anime.get('genres', [])[:3])  # Top 3 genres
            score = anime.get('averageScore', 0) / 10.0  # Convert to 0-10 scale
            year = anime.get('seasonYear', 'N/A')
            description = anime.get('description', '无简介')
            
            # Clean description (remove special chars, limit length)
            if description:
                description = description.replace('<br>', ' ').replace('\n', ' ')
                description = description[:150]
            
            candidate_list.append(
                f"{i}. 《{title}》- {year}年 - 类型:{genres} - 评分:{score:.1f}/10\n   简介: {description}"
            )
        
        candidates_text = "\n".join(candidate_list)
        liked_anime_text = '、'.join([f'《{a}》' for a in liked_anime])
        
        return f"""你是一位资深动画/漫画评论家，擅长深度理解观众的观看偏好。

=== 第一步：深度分析 ===
用户喜欢这些动画: {liked_anime_text}

请深入分析（基于你对这些作品的了解）:
1. 题材与类型: 日常系/百合/热血/治愈/奇幻等
2. 人物关系: 友情/恋爱/师徒/家庭
3. 氛围与节奏: 轻松/紧张/温馨/激烈
4. 目标受众: 少年/少女/青年/成人向

=== 第二步：候选动画匹配 ===
候选动画列表（已筛选高分作品）:
{candidates_text}

=== 第三步：推荐要求 ===
从候选中选出10部最合适的，要求:
1. 深层共鸣: 不只看类型标签，要理解作品的核心魅力和情感基调
2. 多样性: 7部类似风格 + 2部小众佳作 + 1部意外惊喜
3. 推荐理由: 每部120字内，说明与用户口味的契合点
4. 避免俗套: 不只推最热门的，要推最适合的

请以JSON格式返回:
{{
  "user_analysis": {{
    "core_themes": "题材分析",
    "emotional_tone": "情感基调",
    "target_audience": "受众类型"
  }},
  "recommendations": [
    {{
      "title": "动画名称",
      "reason": "推荐理由（120字内）",
      "type": "safe/niche/surprise"
    }}
  ]
}}"""
    
    async def recommend_anime(
        self,
        liked_anime: List[str],
        chat_id: int,
        ai_manager: Optional[AIManager] = None
    ) -> Dict[str, Any]:
        """Get anime recommendations.
        
        Args:
            liked_anime: List of 1-5 anime titles user likes
            chat_id: Chat ID for AI service context
            ai_manager: AI Manager instance (optional)
            
        Returns:
            Dict with user_analysis and recommendations
        """
        if not liked_anime:
            raise ValueError("至少需要输入一部动画")
        
        if len(liked_anime) > 5:
            raise ValueError("最多支持5部动画")
        
        # Use AI Manager (no more circular dependency!)
        if ai_manager is None:
            ai_manager = AIManager()
        
        try:
            # Get candidates from AniList
            logger.info(f"Getting anime recommendations based on: {liked_anime}")
            candidates = await self.get_anime_candidates(liked_anime)
            
            if not candidates:
                raise Exception("未找到候选动画，请检查动画名称是否正确")
            
            # Build LLM prompt
            prompt = self._build_anime_prompt(liked_anime, candidates)
            
            # Get LLM recommendations using AI Manager
            logger.info("Calling LLM for anime analysis...")
            input_data = MultimodalInput(text=prompt)
            
            response = await ai_manager.get_simple_response(
                input_data=input_data,
                chat_id=chat_id
            )
            
            # 使用display_answer
            llm_response = response.display_answer
            
            # Parse JSON response
            try:
                if "```json" in llm_response:
                    json_start = llm_response.find("```json") + 7
                    json_end = llm_response.find("```", json_start)
                    json_text = llm_response[json_start:json_end].strip()
                elif "{" in llm_response:
                    json_start = llm_response.find("{")
                    json_end = llm_response.rfind("}") + 1
                    json_text = llm_response[json_start:json_end]
                else:
                    json_text = llm_response
                
                result = json.loads(json_text)
                
                if "recommendations" not in result:
                    raise ValueError("Response missing recommendations")
                
                # Add metadata from AniList
                for rec in result.get("recommendations", []):
                    title = rec.get("title", "")
                    # Find matching anime
                    matching_anime = next(
                        (a for a in candidates if title in (
                            a.get('title', {}).get('romaji', ''),
                            a.get('title', {}).get('english', ''),
                            a.get('title', {}).get('native', '')
                        )),
                        None
                    )
                    if matching_anime:
                        rec["metadata"] = {
                            "year": matching_anime.get('seasonYear', 'N/A'),
                            "rating": matching_anime.get('averageScore', 0) / 10.0,
                            "genres": ', '.join(matching_anime.get('genres', [])[:3]),
                            "format": matching_anime.get('format', 'N/A'),
                            "source": "AniList"
                        }
                
                return result
                
            except json.JSONDecodeError as e:
                logger.error(f"Failed to parse LLM response as JSON: {e}")
                logger.error(f"Response was: {llm_response[:500]}")
                raise Exception("AI返回格式错误，请重试")
                
        except Exception as e:
            logger.error(f"Anime recommendation error: {e}")
            raise
