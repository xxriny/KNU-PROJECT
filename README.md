# NAVIGATOR

PM/SA 워크플로우를 지원하는 AI 데스크톱 분석 도구입니다.

Electron + React(Vite) + FastAPI 사이드카 아키텍처로 동작하며, Google Gemini 기반 LangGraph 파이프라인으로 다음 산출물을 생성합니다.

- PM 산출물: 요구사항(RTM), 컨텍스트 요약
- SA 산출물: 아키텍처/보안/위상 정렬, 시스템 다이어그램/플로우차트/UML/인터페이스/의사결정 테이블

## 1. 주요 기능

- 멀티 모드 분석: `CREATE`, `UPDATE`, `REVERSE_ENGINEER` (REST/WebSocket의 `action_type` 정규화)
- **Agentic Workflow 및 자가 치유(Self-Healing)**: 정보가 부족하거나 기술 스택 맵핑이 불완전하면, 스스로 크롤링하고 검증하는 조건부 루프(Conditional Edge) 동작
- **도메인 주도 설계(DDD)**: PM, SA, RAG 도메인으로 파이프라인 노드와 스키마를 분리하여 응집도를 높임
- **비용 최적화(Cost Management)**: 각 노드 실행 시 사용된 토큰 및 비용을 실시간으로 추적(`core/cost_manager.py`)하고, 통합 실패 시 불필요한 파이프라인 진행을 조기 차단
- 실시간 파이프라인 스트리밍: WebSocket 상태/생각 로그/최종 결과
- SA 시각화 아티팩트 자동 컴파일: 컨테이너 다이어그램(`result_shaping/container_config.py`로 레이어·매핑 조정 가능), Flowchart, UML 컴포넌트 뷰
- **프론트 모듈화**: 결과 뷰를 `components/resultViewer/` 탭 단위로 분리, Zustand는 `store/slices/`(WebSocket·설정) + `useAppStore` 조합
- 세션 저장/복원: 데이터베이스 기반의 영구 저장(로컬 SQLite / Vector 하이브리드) 및 상태 복원
- 보안 기본 원칙: `.env` 분리, 결과 shaping 단계에서 민감 필드 제외

## 2. 기술 스택

| Layer | Stack |
|---|---|
| Desktop Shell | Electron |
| Frontend | React 18, Tailwind CSS, Monaco Editor, React Flow, Zustand |
| Build | Vite 5 |
| Backend API | FastAPI, WebSocket |
| Orchestration | LangGraph, LangChain |
| LLM | Google Gemini (`langchain-google-genai`) |
| Data/Vector | ChromaDB |
| Observability | structlog, Prometheus |

## 3. 사전 요구사항

- Node.js 18+
- Python 3.11+
- Google Gemini API Key
	- 발급: https://aistudio.google.com/app/apikey

## 4. 설치

프로젝트 루트(현재 `navigator/`) 기준입니다.

```bash
# 1) Node 의존성
npm install

# 2) Python 가상환경 + 백엔드 의존성
cd backend
python -m venv .venv
.venv\Scripts\activate      # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3) 환경변수
copy .env.example .env        # Windows
# cp .env.example .env        # macOS / Linux
```

`.env` 파일에 최소한 아래 값을 설정하세요.

```env
GEMINI_API_KEY=YOUR_API_KEY
ENV=dev
```

## 5. 실행

### 5.1 Windows 원클릭 실행 (권장)

```bat
run_v2.bat
```

동작 순서:

1. 기존 `node/python/electron` 프로세스 정리
2. Vite 개발 서버 기동 및 5173 포트 대기
3. Electron 실행 (Electron이 FastAPI 사이드카를 함께 올림)

### 5.2 스크립트 기반 실행

```bash
npm run dev
```

기타 유용한 스크립트:

- `npm run dev:vite`: 프론트 개발 서버
- `npm run dev:electron`: Electron 앱 실행
- `npm run build`: 프론트 프로덕션 빌드
- `npm run build:electron`: 빌드 + 패키징
- `npm run backend`: 백엔드만 단독 기동(개발·디버그용, 기본 포트는 `package.json` 스크립트 참고)

## 6. 프로젝트 구조

### 6.1 디렉터리 개요

```text
navigator/
├─ electron/
│  ├─ main.js                 # Electron 메인 프로세스, 백엔드 사이드카 관리
│  └─ preload.js              # 렌더러 IPC 브리지
├─ src/
│  ├─ App.jsx
│  ├─ index.css
│  ├─ components/
│  │  ├─ Workspace, ChatPanel, SAArtifactGraph, …
│  │  ├─ ResultViewer.jsx     # 결과 셸(탭 라우팅)
│  │  ├─ resultViewer/        # 탭별 UI (Overview, RTM, Context, Topology, SA 전용 탭 등)
│  │  ├─ graphLayout.js       # 그래프 레이아웃
│  │  └─ graphUtils.js        # 그래프 유틸
│  └─ store/
│     ├─ useAppStore.js       # 통합 스토어(파이프라인·UI·세션 등)
│     ├─ storeHelpers.js
│     ├─ debounce.js
│     └─ slices/
│        ├─ wsSlice.js        # WebSocket 관련 액션/상태
│        └─ configSlice.js    # 설정 관련
├─ backend/
│  ├─ main.py                 # FastAPI 엔트리
│  ├─ version.py              # 기본 모델 등 공통 상수
│  ├─ transport/              # WebSocket / REST 핸들러
│  ├─ orchestration/
│  │  ├─ pipeline_runner.py   # 파이프라인 선택·실행 진입
│  │  └─ executor.py          # REST·WS 공통 실행·결과 shaping (PipelineExecutor)
│  ├─ pipeline/
│  │  ├─ core/                # 공통 상태(state), 비용 관리(cost_manager), 모델(gemini, embedding), 유틸리티
│  │  ├─ domain/              # 도메인 주도 설계(DDD) 기반 로직 분리
│  │  │  ├─ pm/               # 기획/요구사항 분석 (benchmark, nodes, schemas, test)
│  │  │  ├─ sa/               # 소프트웨어 아키텍처 분석 (nodes, schemas)
│  │  │  ├─ rag/              # 코드 스캔 및 시스템 컨텍스트
│  │  │  └─ chat/             # 아이디어 발산 및 수정 대화
│  │  └─ orchestration/       # LangGraph 파이프라인 조립 및 제어
│  │     ├─ graph.py          # PM, SA, Scan 서브 그래프 조립 및 라우팅 (조건부 루프)
│  │     └─ facade.py         # 통합 실행 인터페이스
│  ├─ result_shaping/
│  │  ├─ result_shaper.py
│  │  ├─ sa_artifact_compiler.py
│  │  └─ container_config.py  # 컨테이너 다이어그램 그룹·레이어 매핑(프로젝트 커스터마이즈)
│  ├─ observability/
│  ├─ connectors/
│  ├─ Data/                   # 분석 결과 JSON, PROJECT_STATE
│  ├─ test/
│  ├─ requirements.txt
│  └─ .env.example
├─ index.html
├─ package.json
├─ run_v2.bat
└─ vite.config.js
```

### 6.2 백엔드 개발 시 참고

- **파이프라인 그래프**: `pipeline/orchestration/graph.py`에서 `pm_pipeline`, `sa_pipeline` 등의 서브 그래프를 조립합니다. `_route_stack_planning` 같은 조건부 라우팅을 통해 에이전트 루프와 조기 종료를 제어합니다.
- **비용 모니터링**: 새로운 노드를 파이프라인에 추가할 때는 `_wrap_node_with_usage` 데코레이터를 적용하여 LLM 호출 시 발생하는 토큰 비용이 자동으로 `accumulated_cost`에 누적되도록 해야 합니다.
- **새 노드 추가**: `pipeline/domain/` 내의 적절한 하위 도메인 폴더(`pm`, `sa` 등)에 작성하며, `(state: PipelineState) -> dict` 혹은 `(state: PipelineState) -> PipelineState` 형태의 시그니처를 유지합니다.
- **LLM 구조화 스키마**: 각 도메인의 `schemas.py` (`domain/pm/schemas.py` 등)에서 Pydantic 모델로 각각 정의하여 사용합니다.
- **API 키**: 단일 진입점에서 해석되도록 유지(`transport`, `pipeline_runner` 등과 정합).

### 6.3 프론트엔드 개발 시 참고

- **상태**: 도메인별 로직은 `store/slices/`로 나누고 `useAppStore.js`에서 조합하는 패턴을 권장.
- **결과 UI**: 새 탭은 `components/resultViewer/`에 컴포넌트 추가 후 `ResultViewer.jsx`에서 연결.

## 7. 파이프라인 모드

분석 요청의 `action_type`(및 정규화 결과)은 아래 셋 중 하나입니다. (`pipeline/action_type.py` 참고.)

| Mode | 설명 |
|---|---|
| `CREATE` | 아이디어 기반 신규 요구사항 정형화 + SA 산출물 생성 |
| `UPDATE` | 기존 코드/요구 반영 변경 분석 |
| `REVERSE_ENGINEER` | 코드베이스 역분석 중심 SA 산출물 생성 |

SA 등 하위 단계에서는 `Needs_Clarification` 같은 **판정/상태**가 별도로 기록될 수 있으며, 이는 위 세 모드와 동일한 “최상위 모드”가 아닙니다.

## 8. 결과 산출물

주요 출력 키(요약):

- `requirements_rtm`
- `context_spec`
- `sa_phase1..sa_phase8`
- `sa_reverse_context`
- `sa_artifacts`
	- `container_diagram_spec`
	- `flowchart_spec`
	- `uml_component_spec`
	- `interface_definition_doc`
	- `decision_table`
- `pm_overview`, `sa_overview`, `project_overview`

참고: PM Topology 탭은 제거되었고, Topology 시각화는 SA 경로(`sa_topology`, `sa_artifacts`) 중심으로 동작합니다.

## 9. 테스트

### 9.1 권장 (pytest 사용 시)

```bash
cd backend
python -m pytest -q test/
```

### 9.2 pytest 미설치 환경

개별 파일을 직접 실행할 수 있습니다.

```bash
cd backend
python test/test_sa_artifact_compiler.py
```

## 10. 트러블슈팅

### 10.1 시스템 다이어그램 컴포넌트 수가 0으로 보이는 경우

원인 후보:

- `sa_phase1.file_inventory`가 비었거나
- `sa_phase5.mapped_requirements[].file_path`가 비어 있음

현재는 layer 기반 fallback이 있어 최소 컴포넌트가 복원됩니다. 과거 JSON은 소급 적용되지 않으므로 분석을 다시 실행해야 반영됩니다.

### 10.2 포트 5173 대기 실패

- `run_v2.bat` 실행 후 `vite.log` 마지막 40줄 확인
- 로컬 방화벽/포트 충돌 점검

### 10.3 WebSocket 연결 실패

- 백엔드 프로세스 기동 여부 확인
- Electron 콘솔/백엔드 로그에서 `/ws/pipeline` 에러 확인

## 11. 보안 가이드

- `.env`는 절대 커밋하지 마세요.
- `.env.example`만 버전 관리합니다.
- API 키/토큰/개인정보를 `backend/Data/*.json`에 남기지 않도록 주의하세요.
- PR/푸시 전 아래 패턴을 점검하세요.
	- `sk-...`, `ghp_...`, `AIza...`, `BEGIN PRIVATE KEY`

## 12. 환경변수

| 변수 | 필수 | 기본값 | 설명 |
|---|---|---|---|
| `GEMINI_API_KEY` | 예 | - | Google Gemini API 키 |
| `ENV` | 아니오 | `dev` | 실행 환경 (`dev` / `prod`) |

## 13. 라이선스/운영 메모

- 내부 운영/개발용 문서 기준입니다.
- 대규모 변경 후에는 `backend/test` 회귀, `npm run build`, 주요 모드(CREATE/UPDATE/REVERSE) 수동 스모크를 권장합니다.
