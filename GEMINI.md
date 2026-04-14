# NAVIGATOR Development Context & Mandates

이 파일은 NAVIGATOR 프로젝트의 아키텍처, 개발 원칙 및 주요 가이드라인을 담고 있습니다. 모든 개발 작업 시 이 내용을 최우선으로 준수합니다.

## 1. 프로젝트 정체성 (Project Identity)
- **목표**: 포화된 웹소설 시장에서 질적 완결성(개연성, 텐션, 타겟팅)을 확보하기 위한 유일한 솔루션 "Project Contextor"의 핵심 엔진.
- **핵심 가치**: 아이디어 구체화(PM)부터 시스템 설계(SA)까지의 과정을 AI 파이프라인으로 자동화하고 시각화함.

## 2. 아키텍처 개요 (Architectural Overview)
- **Frontend**: React 18 + Vite + Tailwind CSS + Zustand (상태 관리) + React Flow (시각화).
- **Backend**: FastAPI + LangGraph (워크플로우 제어) + LangChain (LLM 오케스트레이션) + ChromaDB (벡터 DB).
- **Desktop Shell**: Electron (FastAPI 사이드카 관리 및 로컬 파일 시스템 접근).
- **LLM**: Google Gemini (gemini-2.0-flash 기반 구조화 출력 중심).

## 3. 개발 원칙 (Development Mandates)

### 3.1 백엔드 (Python/FastAPI/LangGraph)
- **파이프라인 노드**: 모든 노드는 `backend/pipeline/node_base.py`의 `@pipeline_node` 데코레이터를 사용하며, `PipelineState`를 입출력으로 가짐.
- **구조화 출력**: LLM 응답은 반드시 `backend/pipeline/schemas/core.py`에 정의된 Pydantic 모델을 통해 검증함.
- **상태 관리**: 파이프라인 중간 상태는 `PipelineState`의 TypedDict 필드에 누적하며, `sget` 헬퍼로 안전하게 접근함.
- **AST 스캔**: 소스 코드 분석 시 `backend/pipeline/ast_scanner.py`를 활용하여 언어별 시그니처를 추출함.

### 3.2 프론트엔드 (React/Zustand/Tailwind)
- **상태 분리**: 비즈니스 로직은 `src/store/slices/`에 정의하고 `useAppStore.js`에서 통합함.
- **결과 렌더링**: 새로운 분석 산출물 추가 시 `src/components/resultViewer/`에 탭 단위로 구현하고 `ResultViewer.jsx`에 등록함.
- **시각화**: 복잡한 그래프는 `SAArtifactGraph` 또는 `TopologyGraph`를 재사용하며, 데이터 변환 로직은 `saGraphAdapters.js`에 집중함.

### 3.3 공통 및 보안
- **환경 변수**: `.env` 파일의 `GEMINI_API_KEY`를 필수로 사용하며, 절대 커밋하지 않음.
- **데이터 저장**: 분석 결과는 `backend/Data/`에 JSON 및 MD 형식으로 저장되며, 세션 ID(`run_id`)로 관리됨.

## 4. 주요 경로 및 파일 (Key Paths)
- **파이프라인 배선**: `backend/pipeline/graph.py`
- **PM 노드**: `backend/pipeline/nodes/pm_phase1~5.py`
- **SA 노드**: `backend/pipeline/nodes/sa_phase1~8.py`
- **산출물 컴파일**: `backend/result_shaping/sa_artifact_compiler.py`
- **메인 스토어**: `src/store/useAppStore.js`

## 5. 작업 프로세스 (Workflow)
1. **Research**: 변경 전 `backend/test/` 내 관련 테스트 코드를 실행하여 기존 로직을 확인한다.
2. **Strategy**: `PipelineState` 필드 변경이 필요한 경우 `state.py`와 `core.py` 스키마를 먼저 업데이트한다.
3. **Execution**: 노드 로직 수정 후 반드시 `pytest`를 통해 회귀 테스트를 수행한다.
4. **Validation**: 프론트엔드 탭의 데이터 매핑 정합성을 `spreadResultData` 헬퍼와 비교하여 검증한다.

---
*이 가이드는 프로젝트의 성장에 따라 지속적으로 업데이트됩니다.*
