"""
Token Cache Manager — Google Context Caching 세션 관리
"""
import time
from typing import Dict, Any, Optional
from pipeline.core.cost_manager import calculate_cost
from observability.logger import get_logger

logger = get_logger(__name__)


class TokenCacheManager:
    """
    Google Context Caching 리소스를 세션별로 관리합니다.
    파이프라인 내에서 동일 RTM 데이터를 여러 노드가 재사용할 때 입력 비용을 절감합니다.
    """
    def __init__(self):
        # {session_id -> {google_cache_name, cached_at, estimated_tokens, hit_count}}
        self.session_pool: Dict[str, Dict[str, Any]] = {}

    def cache_google_context(self, session_id: str, cache_name: str, est_tokens: int):
        """Vertex AI / Gemini Context Cache 리소스 이름을 세션에 등록."""
        self.session_pool[session_id] = {
            "google_cache_name": cache_name,
            "cached_at": time.time(),
            "estimated_tokens": est_tokens,
            "hit_count": 0
        }
        logger.info(f"Google Context Cache Registered | Session: {session_id} | Name: {cache_name}")

    def get_google_cache(self, session_id: str) -> Optional[str]:
        """세션에 등록된 구글 캐시 이름 반환"""
        entry = self.session_pool.get(session_id)
        if entry:
            return entry.get("google_cache_name")
        return None

    def get_cache_stats(self, session_id: str, model_name: str, actual_usage: Dict[str, int]) -> Dict[str, Any]:
        """캐시 히트 여부 및 절감 비용 계산."""
        entry = self.session_pool.get(session_id)
        if not entry:
            return {"cache_hit": False, "savings_usd": 0.0}

        entry["hit_count"] += 1
        cached_tokens = entry["estimated_tokens"]
        savings_usd = calculate_cost(model_name, cached_tokens, 0) * 0.9

        return {
            "cache_hit": True,
            "cached_tokens": cached_tokens,
            "savings_usd": round(savings_usd, 8),
            "hit_count": entry["hit_count"]
        }

    def cleanup_expired(self, ttl_seconds: int = 3600):
        """TTL 초과 캐시 정리"""
        now = time.time()
        expired = [sid for sid, e in self.session_pool.items() if now - e["cached_at"] > ttl_seconds]
        for sid in expired:
            del self.session_pool[sid]
        return len(expired)


# 글로벌 싱글톤
cache_manager = TokenCacheManager()
