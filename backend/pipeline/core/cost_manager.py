"""
Gemini 모델별 단가 관리 및 비용 환산 엔진 (REQ-010)
표준화된 단가를 기반으로 토큰 소모량을 USD로 환산합니다.
"""

from typing import Dict, Any

# ─── 단가 정책 (1,000,000 토큰당 달러) ───────────────────
# 시리즈별 표준 단가 (Flash: $0.1/$0.3, Pro: $1.25/$5.0)
_BASE_PRICING = {
    "flash": {"input": 0.1, "output": 0.3},
    "pro": {"input": 1.25, "output": 5.0},
    "default": {"input": 0.1, "output": 0.3} # 기본값은 Flash 단가 적용
}

def calculate_cost(model: str, input_tokens: int, output_tokens: int) -> float:
    """토큰 사용량을 USD 비용으로 환산 (1M 토큰 기준)"""
    m = model.lower()
    
    # 모델명 패턴에 따라 단가 선택
    if "pro" in m:
        rates = _BASE_PRICING["pro"]
    elif "flash" in m:
        rates = _BASE_PRICING["flash"]
    else:
        rates = _BASE_PRICING["default"]
        
    in_cost = (input_tokens / 1_000_000) * rates["input"]
    out_cost = (output_tokens / 1_000_000) * rates["output"]
    
    return round(in_cost + out_cost, 6)
