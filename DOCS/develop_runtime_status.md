# Develop Runtime Status

## 목적

이 문서는 `develop pipeline`의 현재 구현 범위, 런타임 스모크 검증 결과, 확인 가능한 범위와 남은 리스크를 정리한다.

기준 시점:

- 작성일: 2026-04-30
- 기준 환경: 로컬 Windows 개발 환경

## 현재 이해한 `develop`의 의미

`develop pipeline`은 단순히 "개발 완료"를 뜻하지 않는다.

이 파이프라인은 기존 `analyze` 결과를 입력으로 받아:

1. 개발 목표를 재정리하고
2. UI/UX, Backend, Frontend 도메인 작업을 분배하고
3. QA / Gate / Integration 단계를 거치고
4. Branch / PR 산출물을 만들고
5. 최종 개발 산출물을 artifact RAG에 다시 적재하는

"개발 오케스트레이션 파이프라인"이다.

즉 현재 출력의 핵심은 실제 코드 diff 자체가 아니라 아래 개발 산출물들이다.

- `develop_main_plan`
- `uiux_result`
- `backend_result`
- `frontend_result`
- `global_fe_sync_result`
- `integration_qa_result`
- `branch_pr_result`
- `embedding_result`

## 현재 구현 완료 범위

### 1. develop 그래프 연결

현재 `develop` 그래프는 아래 순서로 연결되어 있다.

1. `develop_main_agent`
2. `develop_uiux_agent`
3. `develop_backend_agent`
4. `develop_frontend_agent`
5. 각 domain QA
6. 각 domain gate
7. `develop_global_fe_sync_gate`
8. `develop_integration_qa_gate`
9. `develop_branch_pr_orchestrator`
10. `develop_embedding`
11. `develop_loop_controller`

### 2. 실행 진입점 연결

실행 경로는 이미 열려 있다.

- REST: `/api/develop`
- WebSocket: `type="develop"`

즉 `previous_result`를 포함한 payload만 주면 백엔드에서 실제 `develop pipeline`을 invoke할 수 있다.

### 3. 프런트 표시 연결

프런트에서는 `Overview` 탭에서 `develop` 결과를 확인할 수 있게 연결했다.

현재 표시되는 핵심 정보:

- develop goal
- domain status
- branch/pr status
- embedding status
- feature branch 목록
- PR draft command
- persisted artifacts
- embedding errors

`develop_plan` 결과가 오면 기본 출력 탭도 `overview`로 이동하도록 반영했다.

### 4. Embedding 실제 적재

`develop_embedding` 단계는 이제 준비 단계가 아니라 실제 적재 단계다.

아래 산출물을 `pm_artifact_knowledge`에 `phase="DEV"`로 upsert 한다.

- `develop_main_plan`
- `uiux_result`
- `backend_result`
- `frontend_result`
- `global_fe_sync_result`
- `integration_qa_result`
- `branch_pr_result`

성공한 항목은:

- `embedding_result.persisted_artifacts`

실패한 항목은:

- `embedding_result.errors`

에 기록된다.

## 이번에 수정한 내용

### 1. `embedding_result.session_id` 정합성 수정

이전에는 반환 payload의 `embedding_result.session_id`가 `run_id`였다.

현재는 실제 적재에 사용한 세션 키와 맞추기 위해:

- `embedding_result.session_id = source_session_id`

로 정리했다.

### 2. 프런트 `Overview` 연결

아래를 반영했다.

- `Overview` 탭 추가
- `develop_plan` 완료 시 `overview`로 이동
- `branch_pr_result`, `embedding_result`, domain status 표시
- `develop` 전용 `PipelineProgress` 단계 목록 추가

### 3. `pm_db.py` 런타임 버그 수정

스모크 중 발견된 실제 버그:

- `logger`가 정의되지 않아 `upsert_pm_artifact()` 내부에서 예외 발생

수정 내용:

- module-level `logger = get_logger()` 추가

### 4. 오프라인 / 제한 환경 fallback 보강

#### `main_agent.py`

`project RAG` 조회 실패 시 전체 파이프라인이 죽지 않도록 아래 fallback을 추가했다.

- `query_project_code(...)` 실패 시
- `hits=0`, `chunks=[]`, `error=<exception>` 형태의 context 반환

#### `pm_db.py`

임베딩 모델 로딩 실패 시에도 upsert가 진행되도록:

- `get_pm_embeddings(...)` 실패 시 zero-vector fallback

을 추가했다.

## 런타임 스모크 결과

## 1차 스모크

목적:

- `develop` 그래프가 끝까지 도는지 확인
- payload shape가 실제로 채워지는지 확인

결과:

- 그래프는 끝까지 실행됨
- `branch_pr_result.status = ready`
- `embedding_result.status = failed`

실패 원인:

- `pm_db.py` 내부 `logger` 미정의

이 이슈는 수정 완료.

## 2차 스모크

목적:

- `logger` 수정 후 embedding 실제 적재 확인

결과:

- `pm_db.py` 버그는 해결됨
- 새로운 환경 이슈 확인

실패 원인:

- Chroma / 임베딩 관련 권한 문제
- `C:\Users\ning\.cache\chroma\onnx_models` 접근 거부

## 3차 스모크

목적:

- 오프라인 / 권한 제한 환경에서도 `develop`가 끝까지 살아남는지 확인
- 실제 DEV artifact upsert 확인

결과:

- `develop` 그래프 끝까지 실행
- `branch_pr_result.status = ready`
- `embedding_result.status = persisted`
- `persisted_artifact_count = 7`
- `embedding_result.errors = []`

적재 확인된 artifact:

1. `DEVELOP_MAIN_PLAN`
2. `DEVELOP_UIUX_RESULT`
3. `DEVELOP_BACKEND_RESULT`
4. `DEVELOP_FRONTEND_RESULT`
5. `DEVELOP_GLOBAL_FE_SYNC`
6. `DEVELOP_INTEGRATION_QA`
7. `DEVELOP_BRANCH_PR_RESULT`

## 지금 실행하면 확인 가능한 범위

현재 상태에서 실제 실행 시 확인 가능한 것:

1. `develop` 그래프가 끝까지 도는지
2. `develop_main_plan`, 각 domain result가 생성되는지
3. QA / Gate / Integration 단계가 정상 종료되는지
4. `branch_pr_result` payload가 생성되는지
5. `embedding_result`가 채워지는지
6. DEV artifact 7종이 `pm_artifact_knowledge`에 적재되는지
7. 프런트 `Overview`에서 위 결과가 보이는지

## 현재 환경에서 아직 제한되는 것

아래는 아직 완전한 실환경 검증이 아니다.

### 1. 실제 git 브랜치 생성

스모크에서는 안전을 위해 branch 생성 부분을 stub 처리해서 확인했다.

즉 아래는 아직 실환경 미확인이다.

- 실제 local branch 생성
- 기존 branch 충돌 처리

### 2. 원격 PR 생성

현재 `branch_pr_result`는 아래까지만 구현되어 있다.

- PR plan 생성
- PR draft markdown 생성
- `gh pr create ...` command 문자열 생성

아직 안 된 것:

- 실제 `git push`
- 실제 `gh pr create`
- 실제 merge

### 3. project RAG 임베딩 모델 다운로드

현재 환경에서는 Hugging Face 쪽 접근이 막혀 아래 현상이 남아 있다.

- `project_rag_context.error`가 남을 수 있음
- `nomic-ai/nomic-embed-text-v1` 로딩 실패 가능
- `BAAI/bge-m3` 로딩 실패 가능

하지만 현재는 fallback 때문에 파이프라인 자체는 계속 진행된다.

## 지금 UI에서 보면 되는 체크포인트

`develop` 실행 후 아래를 본다.

### Progress

다음 노드가 순서대로 `done` 되는지 확인:

- `develop_main_agent`
- `develop_uiux_agent`
- `develop_backend_agent`
- `develop_frontend_agent`
- 각 QA
- 각 gate
- `develop_global_fe_sync_gate`
- `develop_integration_qa_gate`
- `develop_branch_pr_orchestrator`
- `develop_embedding`
- `develop_loop_controller`

### Overview

다음 값을 확인:

- `Branch / PR = ready`
- `Embedding = persisted`
- `persisted_artifacts` 개수 = 7
- `embedding_result.errors = []`

## 현재 상태 한 줄 요약

현재 `develop pipeline`은:

- 백엔드 그래프 실행 완료
- 프런트 표시 연결 완료
- DEV artifact 실제 적재 확인 완료

까지는 검증됐다.

다만 아래는 아직 남아 있다.

- 실제 git branch 생성 실환경 검증
- 원격 PR 생성
- Hugging Face 모델 다운로드가 가능한 환경에서의 완전한 RAG 조회 검증

## 다음 우선순위

추천 순서:

1. `Branch/PR`의 실제 branch 생성과 원격 PR 생성 단계 확장
2. 임베딩 모델 캐시 / 네트워크 환경 정리
3. `develop`를 산출물 생성 수준에서 실제 코드 수정 orchestration 수준으로 확장

