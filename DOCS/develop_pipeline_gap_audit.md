# Develop Pipeline Gap Audit

기준 문서:

- `C:\Users\ning\Downloads\NAVIGATOR (1).drawio`
- `DOCS/develop_pipeline_status.md`
- `DOCS/develop_runtime_status.md`

목적:

- 현재 구현된 `develop pipeline`이 설계 의도와 얼마나 맞는지 점검
- 미구현/부분구현 항목을 우선순위별로 정리

## 결론

현재 구현은 `drawio`에 정의된 `develop pipeline`의 **상위 orchestration 구조**에는 대체로 부합한다.

구현되어 있는 축:

- `project RAG + artifact RAG`를 함께 읽는 `Main Agent`
- `UI/UX / Backend / Frontend` 분기
- 각 도메인별 `QA -> Domain Gate`
- `Global FE Sync`
- `Integration QA`
- `Branch/PR Orchestrator`
- `DEV artifact -> RAG` 재적재

하지만 현재 파이프라인은 **실제 코드 제작/변경 파이프라인**이라기보다 **개발 계획/검토/브랜치 초안 생성 파이프라인**에 가깝다.

즉:

- 설계 방향은 맞다
- 구현 깊이는 아직 부족하다

## 설계 대비 적합한 점

### 1. DEV 진입 구조

설계 의도:

- 분석 결과(`PM/SA`)를 입력으로 받아 후속 개발 단계를 오케스트레이션

현재 구현:

- `previous_result`를 입력으로 받아 `develop pipeline`을 실행
- `project RAG`와 `artifact RAG`를 함께 조회

판정:

- 적합

### 2. 멀티 도메인 분기

설계 의도:

- `Main Agent`가 작업을 나누고 `UI/UX`, `Backend`, `Frontend` 서브 에이전트를 사용

현재 구현:

- `develop_main_agent`
- `develop_uiux_agent`
- `develop_backend_agent`
- `develop_frontend_agent`

판정:

- 적합

### 3. QA 및 게이트 구조

설계 의도:

- 각 도메인 산출물 QA
- 도메인 무결성 검증
- FE/통합 단위 재검증

현재 구현:

- 각 도메인별 QA 노드 존재
- `develop_global_fe_sync_gate`
- `develop_integration_qa_gate`

판정:

- 구조상 적합

### 4. 후속 회차를 위한 RAG 반영

설계 의도:

- DEV 결과를 다시 RAG에 적재하여 다음 회차 개발에 활용

현재 구현:

- `develop_embedding`에서 DEV 결과를 `pm_artifact_knowledge`에 `phase="DEV"`로 적재

판정:

- 적합

## 핵심 갭

### P0. 실제 코드 수정 단계가 없음

설계 의도:

- DEV 단계에서 실제 제작이 일어나고, 변경사항이 이후 검증/브랜치 흐름으로 이어져야 함

현재 상태:

- 각 에이전트 결과는 계획/설명/리포트 중심
- 실제 파일 수정 orchestration 부재
- `source_dir`는 입력으로 전달되지만, 코드 편집 파이프라인으로 이어지지 않음

영향:

- 현재 결과물만으로는 “개발 완료”라고 보기 어려움
- 사용자가 기대하는 자동 구현과 괴리가 큼

필요 작업:

- 도메인별 `task spec -> file target -> patch plan -> code edit -> local verification` 단계 추가
- 최소한 `backend`와 `frontend` 도메인부터 실제 파일 변경 결과를 만들도록 확장

### P0. Branch/PR는 실제 협업 자동화가 아니라 초안 생성에 가까움

설계 의도:

- Git Agent 회귀
- 변경 내역을 다음 제작 루프와 연결

현재 상태:

- 로컬 브랜치 생성은 수행
- PR body markdown 생성
- `gh pr create ...` 명령 문자열만 반환
- 실제 push, PR 생성, merge는 미구현

영향:

- Git 흐름이 반자동 수준에 머무름

필요 작업:

- `git status` 점검
- 변경 파일 수집
- commit 메시지 생성
- 선택적으로 `git push`, `gh pr create`, merge까지 이어지는 실행 모드 추가

### P0. Domain Gate가 너무 약함

설계 의도:

- 도메인 내 논리적/기술적 무결성 검증

현재 상태:

- QA 결과가 `rework`면 1회 재시도
- 이후에는 품질 미충족이어도 `pass`

영향:

- 게이트가 품질 판단이 아니라 루프 제한 장치로 동작
- 설계 의도 대비 신뢰성이 낮음

필요 작업:

- 필수 체크리스트 기반 게이트 규칙 강화
- `pass / blocked / waived` 구분
- 실패 근거를 구조화해서 다음 에이전트 입력으로 전달

### P1. Global FE Sync / Integration QA가 코드 검증보다 문서 검증에 가까움

설계 의도:

- 분야 간 결합 구조 검증

현재 상태:

- LLM 기반 검토 중심
- 실제 빌드/테스트/정적 검사와 직접 연결된 흔적이 약함

영향:

- 통합 품질 보증력이 낮음

필요 작업:

- FE sync: 컴포넌트 이름, props, 라우팅, API contract 정합성 검사 추가
- Integration QA: 실제 테스트 커맨드, schema diff, API spec diff, build 결과를 입력으로 사용

### P1. “최종 QA” 단계가 drawio 표현 대비 약함

설계 의도:

- Domain Gate 이후 2차 결합 검증, 최종 QA, merge 회귀

현재 상태:

- `Integration QA Gate`는 존재
- 하지만 최종 승인/릴리즈 직전 판단 노드로는 약함

영향:

- 통합 검증과 최종 승인이 사실상 같은 단계로 뭉쳐 있음

필요 작업:

- `final_release_gate` 또는 `merge_readiness_gate` 분리
- QA 결과, 테스트 결과, 변경 범위, 브랜치 상태를 종합해 최종 승인

### P1. 프로젝트 RAG 업데이트가 DEV 이후 자동 반영되는 범위가 제한적임

설계 의도:

- 변경사항이 다음 회차에서 반영되어야 함

현재 상태:

- artifact RAG 적재는 있음
- project code RAG는 코드 변경 자체가 없어서 실질 반영이 제한됨

영향:

- “다음 회차시 Git Agent가 업데이트 확인”이라는 설계 효과가 반감됨

필요 작업:

- 실제 코드 변경 후 `project RAG re-index` 단계 추가
- 변경 파일만 증분 반영하는 ingest 루틴 도입

### P2. PM/SA/DEV 우선순위-ID 추적이 실행 단계까지 강하게 이어지지 않음

설계 의도:

- PM/SA의 ID 우선순위와 merge 분석서를 바탕으로 제작 결정

현재 상태:

- planning 입력에는 RTM/요구사항이 들어감
- 하지만 이후 실제 작업 결과가 어떤 requirement ID를 충족하는지 추적이 약함

영향:

- 개발 산출물의 traceability가 불충분함

필요 작업:

- 각 도메인 산출물에 `requirement_ids`, `target_files`, `verification_evidence` 추가
- 최종 `branch_pr_result`에도 requirement coverage 요약 포함

## 권장 구현 순서

### 1단계

- `429`와 과호출 문제 완화
- Domain Gate 강화
- DEV 결과에 requirement traceability 추가

### 2단계

- `backend`/`frontend` 실제 코드 수정 노드 추가
- 수정 파일 목록, patch summary, 검증 결과를 결과물에 포함

### 3단계

- `project RAG` 증분 업데이트
- 실제 Git push / PR 생성 / merge 흐름 추가

### 4단계

- 최종 승인 게이트 분리
- 통합 테스트/빌드 기반 검증 자동화

## 실무 판단

현재 상태의 `develop pipeline`은 아래처럼 보는 것이 정확하다.

- 가능한 표현: `개발 오케스트레이션 파이프라인`
- 애매한 표현: `자동 개발 파이프라인`
- 아직 어려운 표현: `실제 구현 완료 파이프라인`

따라서 다음 개발 목표는 명확하다.

- 문서/계획 중심 산출물 파이프라인에서
- 실제 코드 변경과 검증까지 포함하는 실행 파이프라인으로 확장해야 한다.
