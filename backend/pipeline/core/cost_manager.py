"""
Gemini 모델별 단가 관리 및 비용 환산 엔진 (REQ-010)
표준화된 단가를 기반으로 토큰 소모량을 USD로 환산합니다.
"""

from typing import Dict, Any

# ─── 단가 정책 (1,000,000 토큰당 달러) ───────────────────
# Vertex AI / AI Studio 표준 단가 데이터 (128k 컨텍스트 이하 기준)
PRICING_MAP = {
    "gemini-2.5-flash": {
        "input": 0.075,
        "output": 0.30
    },
    "gemini-2.1-flash": {
        "input": 0.075,
        "output": 0.30
    },
    "gemini-3.1-pro-preview": {
        "input": 1.25,
        "output": 5.00
    },
    "gemini-1.5-flash": {
        "input": 0.075,
        "output": 0.30
    },
    "gemini-1.5-pro": {
        "input": 1.25,
        "output": 5.00
    }
}

DEFAULT_PRICING = {"input": 0.075, "output": 0.30} # Flash 기준 폴백


def calculate_cost(model_name: str, input_tokens: int, output_tokens: int) -> float:
    """토큰 수와 모델명을 기반으로 USD 비용을 산출합니다."""
    # 하이픈 뒤의 리전이나 옵션 제거 (ex: gemini-2.5-flash-001 -> gemini-2.5-flash)
    base_model = model_name.split("-")[:3]
    if "flash" in model_name.lower():
        pricing = NEXT_IF_EXISTS(model_name, "flash") or DEFAULT_PRICING
    elif "pro" in model_name.lower():
        pricing = NEXT_IF_EXISTS(model_name, "pro") or PRICING_MAP.get("gemini-1.5-pro")
    else:
        pricing = DEFAULT_PRICING

    # 좀 더 정확한 매칭을 위해 완전 일치 먼저 확인
    pricing = PRICING_MAP.get(model_name, pricing)
    
    in_cost = (input_tokens / 1_000_000) * pricing["input"]
    out_cost = (output_tokens / 1_000_000) * pricing["output"]
    
    return round(in_cost + out_cost, 8)


def NEXT_IF_EXISTS(model_name: str, keyword: str):
    """키워드가 포함된 가장 가까운 단가 정책을 반환합니다."""
    for name, price in PRICING_MAP.items():
        if keyword in name.lower():
            if name.lower() in model_name.lower() or model_name.lower() in name.lower():
                return price
    return None


class TokenUsageTracker:
    """파이프라인 실행 중 토큰 및 비용 누적을 관리하는 클래스."""
    
    def __init__(self):
        self.total_input_tokens = 0
        self.total_output_tokens = 0
        self.total_cost_usd = 0.0
        self.usage_history = []

    def add_usage(self, model_name: str, node_name: str, usage: Dict[str, int]):
        """특정 노드의 사용량을 추가하고 비용을 합산합니다."""
        in_t = usage.get("input_tokens", 0)
        out_t = usage.get("output_tokens", 0)
        cost = calculate_cost(model_name, in_t, out_t)
        
        self.total_input_tokens += in_t
        self.total_output_tokens += out_t
        self.total_cost_usd += cost
        
        self.usage_history.append({
            "node": node_name,
            "model": model_name,
            "input": in_t,
            "output": out_t,
            "cost": cost
        })
    
    def get_summary(self) -> Dict[str, Any]:
        return {
            "total_input": self.total_input_tokens,
            "total_output": self.total_output_tokens,
            "total_tokens": self.total_input_tokens + self.total_output_tokens,
            "total_cost_usd": round(self.total_cost_usd, 6),
            "usage_history": self.usage_history
        }
