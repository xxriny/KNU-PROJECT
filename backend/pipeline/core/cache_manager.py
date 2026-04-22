import time
import hashlib
from typing import Dict, List, Any, Optional
from pipeline.core.cost_manager import calculate_cost
from observability.logger import get_logger

logger = get_logger(__name__)

class TokenCacheManager:
    """
    LLM 토큰 캐싱 및 세션 관리자 (Phase 1)
    Gemini, OpenAI, Anthropic 모델 지원 및 비용 절감 추적.
    """
    def __init__(self, backend_type="gemini"):
        self.backend_type = backend_type
        # {session_id -> {content_hash: str, static_content: str, cached_at: float, ttl: int, hit_count: int, estimated_tokens: int}}
        self.session_pool: Dict[str, Dict[str, Any]] = {}
    
    def _estimate_tokens(self, text: str) -> int:
        """대략적인 토큰 수 추정 (1단어 당 1.3토큰 기준)"""
        if not text: return 0
        return int(len(text.split()) * 1.3)
        
    def cache_static_context(self, session_id: str, static_docs: str, ttl: int = 3600 * 5):
        """
        정적 문서 (PRD, RTM, System Instruction 등)를 세션별로 캐시.
        """
        content_hash = hashlib.sha256(str(static_docs).encode()).hexdigest()
        
        # Gemini / OpenAI / Anthropic 각 모델별 캐시 특성 정의
        # Gemini: Context Caching (Persistent or Auto)
        # OpenAI: Prompt Caching (Automatic for identical prefixes > 1024 tokens)
        
        cache_entry = {
            "content": static_docs,
            "hash": content_hash,
            "cached_at": time.time(),
            "ttl": ttl,
            "hit_count": 0,
            "estimated_tokens": self._estimate_tokens(static_docs),
        }
        
        self.session_pool[session_id] = cache_entry
        logger.info(f"Persistent Cache Created | Session: {session_id} | Hash: {content_hash[:8]} | Est. Tokens: {cache_entry['estimated_tokens']}")
        return content_hash
    
    def get_cache_stats(self, session_id: str, model_name: str, actual_usage: Dict[str, int]) -> Dict[str, Any]:
        """
        캐시 히트 여부 및 절감 비용 계산.
        actual_usage: {"input_tokens": int, "output_tokens": int}
        """
        entry = self.session_pool.get(session_id)
        if not entry:
            return {"cache_hit": False, "savings_usd": 0.0}
        
        entry["hit_count"] += 1
        
        # 실제 캐시된 토큰 계산 (Gemini/OpenAI 등 모델별 실제 응답 메타데이터 기반)
        # 여기서는 entry['estimated_tokens']를 기준으로 절감액 계산 (Quick Win 용)
        # Gemini Context Caching은 보통 입력 토큰 단가의 1/4 ~ 1/10 수준 (또는 90% 할인)
        
        input_tokens = actual_usage.get("input_tokens", 0)
        # 만약 입력 토큰 중 캐시된 비중이 있다면 그만큼의 차액을 savings로 간주
        # (현실적으로는 LLM 응답의 usage_metadata.cached_content_token_count 등을 참조해야 함)
        
        # 임시: 캐시된 토큰의 90% 비용을 절감한 것으로 계산
        cached_tokens = entry["estimated_tokens"]
        savings_usd = calculate_cost(model_name, cached_tokens, 0) * 0.9
        
        return {
            "cache_hit": True,
            "cached_tokens": cached_tokens,
            "savings_usd": round(savings_usd, 8),
            "hit_count": entry["hit_count"]
        }
    
    def cleanup_expired_cache(self):
        """만료된 캐시 정리"""
        current_time = time.time()
        expired_sessions = [
            sid for sid, entry in self.session_pool.items() 
            if current_time - entry["cached_at"] > entry["ttl"]
        ]
        for sid in expired_sessions:
            del self.session_pool[sid]
        return len(expired_sessions)

class VersionedCacheManager(TokenCacheManager):
    """버전 관리 기능을 포함한 확장 캐시 관리자"""
    def cache_static_context_with_version(self, session_id: str, static_docs: str, version_hash: str):
        entry = self.cache_static_context(session_id, static_docs)
        self.session_pool[session_id]["version_hash"] = version_hash
        return entry
    
    def is_cache_valid(self, session_id: str, current_version_hash: str) -> bool:
        entry = self.session_pool.get(session_id)
        if not entry: return False
        return entry.get("version_hash") == current_version_hash

# 글로벌 싱글톤 인스턴스 (pipeline/core/cache_manager.py)
cache_manager = VersionedCacheManager(backend_type="gemini")
