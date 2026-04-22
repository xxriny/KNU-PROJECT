# 💎 LLM 토큰 비용 및 성능 최적화 가이드 (NAVIGATOR)

본 문서는 NAVIGATOR 프로젝트의 PM/SA 파이프라인에서 LLM 운용 비용을 절감하고 응답 성능을 극대화하기 위해 적용된 기술적 전략을 설명합니다.

---

## 1. 현재 적용된 주요 기술 (Applied Technologies)

### 🚀 [Phase 1] 세션 기반 토큰 캐싱 (Token-Level Caching)
- **모듈**: `pipeline.core.cache_manager.TokenCacheManager`
- **설명**: 동일 세션(`run_id`) 내에서 반복되는 시스템 지시문(System Instruction)과 정적 컨텍스트(PRD, RTM 등)를 감지하여 LLM의 캐시 기능을 활성화합니다.
- **최적화 지점**: `pipeline.core.utils.call_structured` 유틸리티에 통합되어 전 노드에 자동 적용됩니다.
- **절감 효과**: 다중 회차 분석 시 입력 토큰 비용 최대 **80~90% 절감**.

### 🧩 [Phase 2] 계층형 적응형 RAG (Adaptive RAG)
- **모듈**: `pipeline.core.rag_manager.RAGManager`
- **설명**: 쿼리의 성격에 따라 검색 전략을 동적으로 선택합니다.
  - **계층형 필터링**: 동일한 기능(Feature)에 대해 중복된 컨텍스트가 발견되면 상단 결과만 본문을 유지하고 나머지는 요약본으로 대체하여 중복 토큰을 방지합니다.
  - **정밀 타겟팅**: 기술 스택 및 메모 검색 시 유사도(Distance) 기반의 동적 K-값 조절을 수행합니다.
- **절감 효과**: 불필요한 컨텍스트 주입 방지로 입력 토큰 **30~40% 추가 절감**.

### 🧹 [Phase 3] 프롬프트 압축 (Prompt Compression)
- **모듈**: `pipeline.core.compressor.PromptCompressor`
- **설명**: `LLMLingua-2` 모델을 사용하여 전송 전 텍스트 자체를 의미론적으로 압축합니다.
  - **하이브리드 보존**: 도메인 핵심 키워드(`MUST`, `UUID`, `Exception`, `URL` 등)는 정규식으로 보호하여 분석 품질 저하를 방지합니다.
- **최적화 지점**: `sa_analysis`, `pm_analysis`, `stack_planner` 등 헤비 노드에 적용.
- **절감 효과**: 입력 컨텍스트 크기 최대 **50% 압축**.

---

## 2. 개발자 활용 가이드 (How to Use)

### 신규 분석 노드를 만들 때
1. **`call_structured` 사용**: 직접 LLM 클라이언트를 호출하지 말고 `pipeline.core.utils.call_structured`를 사용하세요. 자동으로 토큰 추적, 비용 계산, 캐싱이 적용됩니다.
2. **압축 활성화**: 데이터 양이 많은 노드라면 `compress_prompt=True` 인자를 추가하세요.
3. **정적/동적 컨텍스트 분리**: `system_prompt`에는 변하지 않는 지시문을 넣고, `user_msg`에는 매번 바뀌는 데이터를 넣으세요. 캐시 매니저는 `system_prompt`를 우선적으로 캐싱합니다.

### 대량의 데이터를 다룰 때
1. **필터링 우선**: 데이터 전체를 JSON으로 덤프하지 말고, `[{"id": x.id, "desc": x.desc} for x in data]`와 같이 분석에 꼭 필요한 필드만 슬라이싱하여 전달하세요.
2. **Patch 구조 채택**: 수정 기능을 구현할 경우 전체를 다시 생성하게 하지 말고, 변경분만 반환하는 스키마를 정의하세요. (참조: `chat_revision.py`)

---

## 3. 로드맵 및 향후 기술 (Next Steps)

1. **동적 모델 라우팅 (Phase 4)**: 단순 작업은 `Gemini Flash`로, 복합 분석은 `Pro` 모델로 자동 배분하여 단가를 최적화합니다.
2. **비용 실시간 대시보드**: 각 `run_id`별 절감액을 시각화하여 사용자에게 제공합니다.

---
**주의**: `cache_manager.py`는 `run_id`를 기준으로 세션을 식별하므로, 테스트 시 동일 세션 효과를 보려면 같은 `run_id`를 유지해야 합니다.
