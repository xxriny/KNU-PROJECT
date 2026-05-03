# Develop Pipeline Status

## 목적

`develop pipeline`은 기존 `analyze` 파이프라인의 후속 단계다.

- 기존 분석 파이프라인: `RAG -> PM -> SA`
- 신규 개발 파이프라인: `Develop`
- 연결 방식: `previous_result`와 RAG 컨텍스트를 입력으로 사용

중요 원칙:

- 기존 `PM / SA / RAG` 본문 로직은 건드리지 않는다.
- `develop pipeline`은 독립 파이프라인으로 유지한다.
- 기존 분석 결과는 `previous_result`와 RAG 조회를 통해 참조한다.

## 기준 아키텍처

사용자가 제공한 설계 기준:

1. `Main Agent`
2. `UI/UX Agent <-> UI/UX QA -> UI/UX Gate`
3. `Backend Agent <-> Backend QA -> Backend Gate`
4. `Frontend Agent <-> Frontend QA -> Frontend Gate`
5. `Global FE Sync`
6. `Integration QA Agent`
7. `Branch/PR`
8. 결과를 다시 RAG에 적재
9. 다음 개발 사이클을 위해 루프 복귀

핵심 흐름:

- Main Agent가 2개 RAG를 읽고 도메인별 작업 분배
- 각 도메인 Agent가 개발 산출물 생성
- 각 도메인 QA가 1차 검증
- Domain Gate가 재시도 여부 판단
- Global FE Sync가 UI/UX와 Frontend 정합성 확인
- Integration QA Agent가 전체 통합 검증
- Branch/PR 단계가 git flow 전략 기준 브랜치 생성과 PR 초안 생성을 수행
- Embedding 단계가 develop 산출물을 artifact RAG에 실제 적재

## 현재 코드 구조

### 진입점 및 배선

- 상태 확장: [backend/pipeline/core/state.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/core/state.py:143)
- develop 그래프: [backend/pipeline/orchestration/aux_graphs.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/orchestration/aux_graphs.py:103)
- facade export: [backend/pipeline/orchestration/facade.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/orchestration/facade.py:20)
- WS 실행: [backend/orchestration/pipeline_runner.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/orchestration/pipeline_runner.py:225)
- REST 실행: [backend/transport/rest_handler.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/transport/rest_handler.py:249)
- 결과 shaping: [backend/result_shaping/result_shaper.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/result_shaping/result_shaper.py:360)

### develop 도메인

- 스키마: [backend/pipeline/domain/dev/schemas.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/schemas.py:1)
- 공통 헬퍼: [backend/pipeline/domain/dev/nodes/_shared.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/_shared.py:1)

## 현재 구현 상태

### LLM 기반 골격 완료

다음 노드들은 `LLM + structured output + fallback` 형태로 올라가 있음:

- `Main Agent`
  - [main_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/main_agent.py:20)
- `UI/UX Agent`
  - [uiux_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/uiux_agent.py:7)
- `Backend Agent`
  - [backend_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/backend_agent.py:7)
- `Frontend Agent`
  - [frontend_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/frontend_agent.py:7)
- `UI/UX QA`
  - [uiux_qa_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/uiux_qa_agent.py:7)
- `Backend QA`
  - [backend_qa_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/backend_qa_agent.py:7)
- `Frontend QA`
  - [frontend_qa_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/frontend_qa_agent.py:7)
- `Global FE Sync`
  - [global_sync_gate.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/global_sync_gate.py:7)
- `Integration QA Agent`
  - [integration_qa_gate.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/integration_qa_gate.py:7)

### 규칙 기반 또는 얇은 게이트 상태

다음 노드들은 현재 규칙 기반/얇은 판정기 상태:

- `UI/UX Gate`
  - [domain_gates.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/domain_gates.py:15)
- `Backend Gate`
  - [domain_gates.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/domain_gates.py:25)
- `Frontend Gate`
  - [domain_gates.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/domain_gates.py:35)

이 세 개는 현재 QA 결과를 보고 `pass/rework` 라우팅만 수행한다.

### 부분 실제화 상태

다음 노드는 로컬 git 기준으로 일부 실제 실행이 들어갔다:

- `Branch/PR`
  - [branch_pr_orchestrator.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/branch_pr_orchestrator.py:8)

현재는 아래를 수행한다:

- `feature_branches`
- `branch_execution`
- `pr_plan`
- `pr_drafts`
- `merge_plan`
- `merge_ready`

현재 실제화된 범위:

- base ref 자동 해석
- 로컬 feature branch 생성 또는 기존 브랜치 재사용
- `DOCS/pr_drafts/`에 PR body 초안 markdown 생성
- `gh pr create ...` 실행용 커맨드 문자열 생성

아직 안 된 것:

- 실제 원격 PR 생성
- 실제 merge 실행

### RAG 관련 현재 상태

`Main Agent`는 현재 실제 2개 RAG를 읽는다.

1. `project_code_knowledge`
   - 조회 함수: `query_project_code(...)`
   - 사용 위치: [main_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/main_agent.py:45)
2. `pm_artifact_knowledge`
   - 컬렉션 직접 조회
   - 사용 위치: [main_agent.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/main_agent.py:71)

현재는:

- project RAG 검색 결과를 `project_rag_context`에 저장
- artifact RAG 결과를 `artifact_rag_context`에 저장
- 이를 메인 planner와 도메인 agent/qa 입력에 사용

### Embedding 단계 현재 상태

- 노드: [embedding.py](/abs/path/C:/Users/ning/Desktop/navigator/KNU-PROJECT/backend/pipeline/domain/dev/nodes/embedding.py:7)

현재는 아래 develop 산출물을 실제로 `pm_artifact_knowledge`에 저장한다:

- `develop_main_plan`
- `uiux_result`
- `backend_result`
- `frontend_result`
- `global_fe_sync_result`
- `integration_qa_result`
- `branch_pr_result`

저장 방식:

- `phase="DEV"`로 artifact RAG에 upsert
- `source_session_id`를 우선 세션 키로 사용
- 저장 성공/실패는 `embedding_result.persisted_artifacts`, `embedding_result.errors`에 기록

즉, 이제는 준비 단계가 아니라 실제 적재 단계다.

## 현재 그래프 구조

현재 `develop pipeline` 라우팅:

1. `develop_main_agent`
2. 병렬 분기
   - `develop_uiux_agent -> develop_uiux_qa_agent -> develop_uiux_domain_gate`
   - `develop_backend_agent -> develop_backend_qa_agent -> develop_backend_domain_gate`
   - `develop_frontend_agent -> develop_frontend_qa_agent -> develop_frontend_domain_gate`
3. `develop_global_fe_sync_gate`
4. `develop_integration_qa_gate`
5. `develop_branch_pr_orchestrator`
6. `develop_embedding`
7. `develop_loop_controller`

조건부 재진입:

- Domain Gate에서 각 도메인 agent로 재시도 가능
- Global FE Sync에서 `uiux` 또는 `frontend` 재작업 가능
- Integration QA에서 `uiux`, `backend`, `frontend` 재작업 가능
- Loop Controller에서 `develop_main_agent`로 복귀 가능

## 현재 한계

아직 안 된 것:

- Domain Gate의 고도화된 품질 기준
- develop 전용 프런트 UI 시각화
- develop 결과를 세션 복원/히스토리에 반영하는 UX

부분적으로만 된 것:

- 메인/도메인/QA는 LLM 기반이지만, 실제 코드 수정 실행은 하지 않음
- 현재는 “개발 계획과 검증 산출물” 중심
- `Branch/PR`는 로컬 브랜치 생성과 PR 초안 생성까지만 수행

## 다음 우선순위

추천 순서:

1. develop 결과를 프런트에 시각화
2. `Branch/PR`의 원격 PR 생성/merge 단계 확장
3. Domain Gate 기준 고도화
4. develop 결과를 세션 복원/히스토리에 반영

## 주의사항

- 기존 `PM / SA / RAG` 파이프라인 본문 로직은 건드리지 않는 방향을 유지한다.
- `develop pipeline`은 독립 후속 단계로만 확장한다.
- `previous_result` 전체를 상태에 싣고 있으므로, develop 단계는 기존 분석 결과 문맥을 그대로 활용한다.
