# NAVIGATOR

PM 요구사항을 자동으로 분석·정형화하는 AI 데스크톱 앱.

**Electron + React(Vite) + FastAPI(Python) 사이드카** 구조로 동작하며, Google Gemini 기반 LangGraph 멀티 페이즈 파이프라인으로 PM/SA 결과물을 생성합니다.

## Tech Stack

| Layer | Stack |
|---|---|
| Desktop Shell | Electron |
| UI | React 18, Tailwind CSS, Monaco Editor |
| Build | Vite 5 |
| Backend | FastAPI, LangGraph, LangChain |
| LLM | Google Gemini (`langchain-google-genai`) |
| Vector DB | ChromaDB |
| Observability | structlog, Prometheus |

## Prerequisites

- Node.js 18+
- Python 3.11+
- Google Gemini API Key → [발급 링크](https://aistudio.google.com/app/apikey)

## Setup

```bash
# 1. Node 의존성 설치
npm install

# 2. Python 가상환경 생성 및 의존성 설치
cd backend
python -m venv .venv
.venv\Scripts\activate        # Windows
# source .venv/bin/activate   # macOS / Linux
pip install -r requirements.txt

# 3. 환경변수 설정
cp .env.example .env
# .env 파일을 열어 GEMINI_API_KEY 값 입력
```

## Run

```bash
# Windows — 루트 디렉터리에서 실행
run_v2.bat
```

실행 순서: Vite dev server 시작 → 포트 5173 대기 → Electron 실행 (FastAPI 백엔드 자동 스핀업)

## Project Structure

```
pm_agent_pipeline_v2/
├── electron/               # Electron main / preload
│   ├── main.js             # 백엔드 프로세스 스핀업, BrowserWindow 생성
│   └── preload.js          # IPC bridge
├── src/                    # React 프론트엔드
│   ├── components/         # UI 컴포넌트 (ChatPanel, Workspace, ...)
│   ├── store/              # Zustand 전역 상태
│   ├── App.jsx
│   └── main.jsx
├── backend/
│   ├── main.py             # FastAPI 앱 진입점
│   ├── transport/          # WebSocket & REST 핸들러
│   ├── orchestration/      # 파이프라인 실행 로직
│   ├── pipeline/           # LangGraph 노드 / 그래프 정의
│   │   └── nodes/          # PM 페이즈 1~5, SA 페이즈 1~8
│   ├── result_shaping/     # 결과 정형화 (schema-driven)
│   ├── observability/      # 로깅, Prometheus 메트릭
│   ├── connectors/         # 폴더 스캔, 결과 저장
│   ├── test/               # 테스트 코드
│   ├── .env.example        # 환경변수 템플릿
│   └── requirements.txt
├── index.html
├── package.json
├── run_v2.bat              # 원클릭 실행 스크립트 (Windows)
└── vite.config.js
```

## Test

```bash
cd backend
python -m pytest test/ -v
```

## Pipeline Modes

| 모드 | 설명 |
|---|---|
| `CREATE` | 아이디어 → PM 요구사항 정형화 (RTM, 시맨틱 그래프) |
| `UPDATE` | 기존 코드 분석 후 요구사항 갱신 |
| `REVERSE_ENGINEER` | 기존 코드베이스 역분석으로 SA 문서 생성 |

## Environment Variables

| 변수 | 필수 | 설명 |
|---|---|---|
| `GEMINI_API_KEY` | ✅ | Google Gemini API 키 |
| `ENV` | - | 실행 환경 (`dev` / `prod`, 기본값 `dev`) |
