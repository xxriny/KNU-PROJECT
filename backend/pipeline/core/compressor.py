import re, os
from typing import List, Optional
from llmlingua import PromptCompressor as LinguaCompressor

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
        
        print(f"--- Initializing PromptCompressor with {model_name} on {device}... ---")
        try:
            self.compressor = LinguaCompressor(
                model_name=model_name,
                device_map=device,
                use_llmlingua2=True
            )
            self._initialized = True
            print("DONE: PromptCompressor initialized successfully.")
        except Exception as e:
            print(f"FAIL: Failed to initialize PromptCompressor: {e}")
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

        # 1. 보존할 키워드 추출
        patterns = self.PRESERVE_PATTERNS + (extra_preserve or [])
        preserved_segments = []
        
        # 간단한 보존 로직: 패턴에 맞는 부분을 임시 토큰으로 치환하거나 
        # LLMLingua-2의 condition_compare/target_token 등을 활용할 수 있으나,
        # LLMLingua-2 자체의 forced_reserve 기능을 우선 시도합니다.
        
        try:
            # LLMLingua-2 API 호출 (지원되지 않는 인자 제거 및 안정화)
            # force_tokens는 리스트 형태로 전달
            result = self.compressor.compress_prompt(
                [text],
                rate=target_token_rate,
                force_tokens=patterns if patterns else None,
                # chunk_end_any_whitespace 제거 (오류 원인)
            )
            
            # 결과 파싱 (리스트 또는 단일 딕셔너리 대응)
            if isinstance(result, list) and len(result) > 0:
                result = result[0]
            
            if isinstance(result, dict):
                compressed_text = result.get("compressed_prompt", text)
            else:
                compressed_text = text
            
            # 압축 효율 계산 및 출력 (디버깅)
            original_len = len(text)
            compressed_len = len(compressed_text)
            savings = (1 - compressed_len / original_len) * 100 if original_len > 0 else 0
            print(f"[PromptCompressor] Compressed: {original_len} -> {compressed_len} chars ({savings:.1f}% saved)")
            
            return compressed_text
        except Exception as e:
            print(f"[PromptCompressor] Compression failed, returning original text: {e}")
            return text

# 싱글톤 인스턴스 생성
prompt_compressor = PromptCompressor()
