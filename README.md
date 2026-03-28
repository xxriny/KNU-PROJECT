# NAVIGATOR

PM/SA 워크플로우를 지원하는 AI 데스크톱 분석 도구입니다.

Electron + React(Vite) + FastAPI 사이드카 아키텍처로 동작하며, Google Gemini 기반 LangGraph 파이프라인으로 다음 산출물을 생성합니다.

- PM 산출물: 요구사항(RTM), 컨텍스트 요약
- SA 산출물: 아키텍처/보안/위상 정렬, 시스템 다이어그램/플로우차트/UML/인터페이스/의사결정 테이블

## 1. 주요 기능

- 멀티 모드 분석: `CREATE`, `UPDATE`, `REVERSE_ENGINEER`
- 실시간 파이프라인 스트리밍: WebSocket 상태/생각 로그/최종 결과
- SA 시각화 아티팩트 자동 컴파일: 컨테이너 다이어그램, Flowchart, UML 컴포넌트 뷰
- 세션 저장/복원: 프로젝트별 분석 상태 및 UI 탭 상태 유지
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

## 6. 프로젝트 구조

```text
navigator/
├─ electron/
│  ├─ main.js                 # Electron 메인 프로세스, 백엔드 사이드카 관리
│  └─ preload.js              # 렌더러 IPC 브리지
├─ src/
│  ├─ App.jsx
│  ├─ index.css
│  ├─ components/             # Workspace, ResultViewer, SAArtifactGraph 등
│  └─ store/
│     └─ useAppStore.js       # Zustand 전역 상태
├─ backend/
│  ├─ main.py                 # FastAPI 엔트리
│  ├─ transport/              # WS/REST 핸들러
│  ├─ orchestration/          # 파이프라인 실행 오케스트레이션
│  ├─ pipeline/
│  │  ├─ graph.py             # LangGraph 노드 그래프
│  │  └─ nodes/               # PM/SA 단계별 노드
│  ├─ result_shaping/
│  │  ├─ result_shaper.py     # 최종 결과 정형화
│  │  └─ sa_artifact_compiler.py
│  ├─ observability/          # logger, metrics
│  ├─ connectors/             # 파일/결과 저장 연동
│  ├─ Data/                   # 분석 결과 JSON, PROJECT_STATE
│  ├─ test/                   # 백엔드 테스트
│  ├─ requirements.txt
│  └─ .env.example
├─ index.html
├─ package.json
├─ run_v2.bat
└─ vite.config.js
```

## 7. 파이프라인 모드

| Mode | 설명 |
|---|---|
| `CREATE` | 아이디어 기반 신규 요구사항 정형화 + SA 산출물 생성 |
| `UPDATE` | 기존 코드/요구 반영 변경 분석 |
| `REVERSE_ENGINEER` | 코드베이스 역분석 중심 SA 산출물 생성 |

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
- 대규모 리팩터링 시 `backend/test` 회귀 테스트와 `npm run build`를 함께 확인하세요.
