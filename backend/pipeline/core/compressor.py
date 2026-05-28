import re, os
from typing import List, Optional
from observability.logger import get_logger

_logger = get_logger()

MAX_COMPRESS_CHARS = 24000

class PromptCompressor:
    """
    LLMLingua-2 기반 프롬프트 압축 매니저 (Phase 3)
    도메인 특화 키워드 보존 로직이 포함된 하이브리드 압축을 수행합니다.
    """

    _instance = None

    # 보존해야 할 정규식 패턴 (PM/SA 도메인)
    PRESERVE_PATTERNS = [
        r"MUST", r"SHOULD", r"MAY", r"NOT",         # 요구사항 키워드
        r"[0-9a-f]{8}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{4}-[0-9a-f]{12}", # UUID
        r"Exception", r"Error", r"Fail", r"Success", # 상태 키워드
        r"https?://\S+",                            # URL
        r"/[a-zA-Z0-9/._-]+",                       # 경로
        r"@[a-zA-Z0-9_-]+",                         # 핸들/태그
    ]

    def __new__(cls, *args, **kwargs):
        if not cls._instance:
            cls._instance = super(PromptCompressor, cls).__new__(cls)
            cls._instance._initialized = False
        return cls._instance

    def __init__(self, model_name: str = "microsoft/llmlingua-2-bert-base-multilingual-cased-meetingbank", device: str = "cpu"):
        if self._initialized:
            return

        _logger.info("compressor_init", model=model_name, device=device)
        try:
            # llmlingua는 PyTorch/BERT를 포함하므로 첫 인스턴스 생성 시 지연 로드
            from llmlingua import PromptCompressor as LinguaCompressor
            self.compressor = LinguaCompressor(
                model_name=model_name,
                device_map=device,
                use_llmlingua2=True
            )
            self._initialized = True
            _logger.info("compressor_ready")
        except Exception as e:
            _logger.error("compressor_init_failed", error=str(e))
            self.compressor = None

    def compress_with_preservation(
        self, 
        text: str, 
        target_token_rate: float = 0.5, 
        extra_preserve: Optional[List[str]] = None
    ) -> str:
        """
        핵심 정보를 보존하며 텍스트를 압축합니다.
        """
        if not self.compressor or not text:
            return text

        if len(text) > MAX_COMPRESS_CHARS:
            # author: xxrin
            # LLMLingua-2 내부 BERT 모델은 긴 입력을 그대로 받으면 512 토큰 한계를 넘겨 에러를 낸다.
            # 압축기 호출 전에 보수적으로 앞부분만 잘라 LLM fallback 경로가 전체 파이프라인을 깨지 않게 한다.
            text = text[:MAX_COMPRESS_CHARS] + "\n... [truncated before compression]"

        # 1. 보존할 키워드 추출
        patterns = self.PRESERVE_PATTERNS + (extra_preserve or [])
        
        try:
            # LLMLingua-2 API 호출
            result = self.compressor.compress_prompt(
                [text],
                rate=target_token_rate,
                force_tokens=patterns if patterns else None,
            )
            
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            if isinstance(result, dict):
                compressed_text = result.get("compressed_prompt", text)
            else:
                compressed_text = text
            
            # 압축 효율 계산
            original_len = len(text)
            compressed_len = len(compressed_text)
            savings = (1 - compressed_len / original_len) * 100 if original_len > 0 else 0
            _logger.info("compressor_result", original=original_len, compressed=compressed_len, savings_pct=round(savings, 1))

            return compressed_text
        except Exception as e:
            _logger.warning("compressor_fallback", error=str(e))
            return text

# 싱글톤 인스턴스 지연 생성 함수
_compressor_instance = None

def get_compressor():
    global _compressor_instance
    if _compressor_instance is None:
        _compressor_instance = PromptCompressor()
    return _compressor_instance
