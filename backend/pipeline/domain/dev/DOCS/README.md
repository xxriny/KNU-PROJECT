# DEV Pipeline Shared/Schema Comment Guide

이 문서는 DEV 파이프라인의 공통 계약 파일인 `_shared.py`와 `schemas.py`에 주석을 달 때 참고하기 위한 설명이다.

핵심 관점은 다음과 같다.

```text
_shared.py
  PM/SA 결과를 DEV 파이프라인이 쓰기 쉬운 형태로 정리해주는 공통 유틸 파일

schemas.py
  main agent, domain agent, QA, codegen, verifier, repair, integration 단계가 주고받는 데이터 계약 파일
```

## `_shared.py`

위치: `backend/pipeline/domain/dev/nodes/_shared.py`

이 파일은 dev-pipeline의 공통 해석기다. PM/SA 산출물 구조가 조금씩 달라도 DEV 노드들이 안정적으로 `requirements`, `components`, `apis`, `tables`를 가져올 수 있게 한다.

상단 주석 예시:

```python
"""
DEV 파이프라인 공통 유틸.

이 모듈은 PM/SA 산출물과 DEV 노드 사이의 호환 계층이다.
PM/SA 결과 구조가 조금씩 달라도 main_agent, domain_agent, QA,
codegen, integration 단계가 동일한 형태의 계약 데이터를 읽을 수 있도록
requirements/components/apis/tables 등을 정규화한다.
"""
```

### Previous Result / Nested Artifact Lookup

대상 함수:

```text
_previous_result
_first_list_by_keys
_has_sa_payload
_raw_sa_bundle
_bundle_data
```

역할:

```text
- 현재 state와 previous_result에서 PM/SA 산출물을 찾는다.
- 중첩된 dict/list 안에서도 components/apis/tables 같은 리스트를 탐색한다.
- SA 산출물 구조가 바뀌어도 DEV 쪽이 최대한 깨지지 않게 한다.
```

추천 주석:

```python
# PM/SA 산출물 구조가 달라져도 필요한 리스트를 찾기 위한 탐색 유틸.
# DEV 노드가 특정 산출물 경로에 강하게 묶이지 않도록 한다.
```

### `normalize_sa_bundle`

역할:

```text
- 흩어진 SA 산출물을 DEV 파이프라인 표준 형태로 바꾼다.
- 결과 형태는 data.components / data.apis / data.tables 중심이다.
- main_agent와 각 domain agent가 이 결과를 기준 계약으로 사용한다.
```

추천 주석:

```python
# 여러 형태의 SA 산출물을 DEV 파이프라인 표준 계약으로 정규화한다.
# 이후 노드들은 components/apis/tables를 이 표준 구조에서 읽는다.
```

### Public Accessors

대상 함수:

```text
get_requirements
get_components
get_apis
get_tables
get_goal
```

역할:

```text
- dev 노드들이 state 구조를 직접 뒤지지 않게 하는 accessor.
- 현재 state를 먼저 보고, 없으면 previous_result와 nested SA artifact에서 fallback한다.
```

추천 주석:

```python
# DEV 노드용 공통 데이터 접근 함수.
# current state, previous_result, nested artifact 순서로 가장 신뢰할 수 있는 값을 찾는다.
```

### `approved_stack_for_domain`

역할:

```text
- PM stack 결과에서 특정 도메인에 허용된 기술스택을 추출한다.
- backend/frontend/uiux별 alias를 고려한다.
- codegen이 임의 라이브러리나 프레임워크를 선택하지 않도록 제한하는 근거가 된다.
```

추천 주석:

```python
# 도메인별 허용 기술스택을 추출한다.
# codegen/QA 단계에서 승인되지 않은 런타임이나 패키지를 거부하기 위한 기준이다.
```

### Generation Policy

대상 함수:

```text
generation_policy
placeholder_policy_findings
policy_enforcement_result
```

역할:

```text
- 생성 코드에 적용할 공통 정책을 정의한다.
- dummy/mock/placeholder 비즈니스 로직을 금지한다.
- SA에 없는 API 생성을 금지한다.
- PM requirement trace 보존을 요구한다.
```

추천 주석:

```python
# 모든 도메인 생성 작업에 적용되는 공통 정책.
# task_spec과 dev_task를 통해 downstream 노드까지 전달된다.
```

주의:

```text
현재 placeholder_policy_findings()의 blocked_terms는 빈 배열이다.
즉 정책 검사 구조는 있지만 실제 placeholder 단어 탐지는 거의 꺼져 있는 상태다.
```

### `build_dev_task`

역할:

```text
- main_agent가 만든 task_spec을 각 도메인 agent가 실행할 수 있는 DEV_TASK로 변환한다.
- task_info, context, instruction, acceptance_criteria, constraints를 포함한다.
- domain agent는 이 DEV_TASK.context를 source of truth로 봐야 한다.
```

추천 주석:

```python
# Main Agent에서 Domain Agent로 넘기는 표준 작업 지시 payload를 만든다.
# Domain Agent는 PM/SA 결과를 다시 해석하지 말고 DEV_TASK.context를 기준으로 작업한다.
```

### `normalize_api_contract`

역할:

```text
- API 명세를 METHOD + path 형태로 통일한다.
- backend QA, frontend QA, integration QA, codegen이 같은 기준으로 API를 비교하게 한다.
```

추천 주석:

```python
# 느슨한 API 명세를 비교 가능한 표준 API 계약으로 변환한다.
# FE/BE interface check와 codegen에서 같은 기준으로 사용된다.
```

### Small Normalization Helpers

대상 함수:

```text
slugify
requirement_id
requirement_desc
component_name
component_rtms
dedupe
requirement_index
requirement_ids_for_components
fallback_requirement_ids
```

역할:

```text
- PM/SA 산출물의 필드명이 달라도 id/name/description을 안전하게 추출한다.
- requirement trace, branch name, task id 생성에 사용된다.
```

추천 주석:

```python
# requirement/component trace와 안정적인 식별자 생성을 위한 작은 정규화 유틸.
```

## `schemas.py`

위치: `backend/pipeline/domain/dev/schemas.py`

이 파일은 dev-pipeline의 데이터 계약서다. 여기 있는 모델들은 대부분 LLM structured output이나 LangGraph state에 들어가는 payload 형태를 정의한다.

상단 주석 예시:

```python
"""
DEV 파이프라인 Pydantic 계약 모델.

이 파일은 main_agent, domain_agent, QA gate, codegen, verifier,
repair agent, integration QA, branch/PR 단계가 주고받는 데이터 구조를 정의한다.
각 노드는 이 모델을 기준으로 structured output을 생성하거나 state payload를 검증한다.
"""
```

### Main Agent -> Domain Agent Handoff

대상 모델:

```text
DomainTaskSpec
DevTaskInfo
DevTaskContext
DevTaskConstraints
DevTask
```

역할:

```text
- Main Agent가 각 Domain Agent에 넘기는 작업 계약이다.
- DevTaskContext가 가장 중요하다.
- approved_stack, sa_bundle, target_api_specs, target_table_specs, requirements,
  RAG context, rework_instruction이 들어간다.
```

추천 주석:

```python
# Main Agent -> Domain Agent 작업 지시 계약.
# DEV_TASK는 각 도메인 agent가 실행해야 하는 표준 payload다.
```

### Main Agent Planning

대상 모델:

```text
MainAgentBranchItem
MainAgentBranchStrategy
MainAgentTaskSpec
MainAgentPlanningOutput
DevelopMainPlan
```

역할:

```text
- main_agent의 계획 결과 모델이다.
- selected_domains, branch_strategy, task_specs를 담는다.
- DevelopMainPlan은 state에 저장되는 최종 계획 snapshot이다.
```

추천 주석:

```python
# develop_main_agent가 생성하는 전체 개발 계획과 브랜치 전략 계약.
```

### Domain Agent Output

대상 모델:

```text
DomainAgentResult
DomainAgentPlanningOutput
```

역할:

```text
- uiux/backend/frontend agent가 공통적으로 내는 산출물 형식이다.
- proposed_changes, files, dependencies, test_plan 중심이다.
```

추천 주석:

```python
# 도메인 agent의 공통 산출물 계약.
# codegen이나 QA 이전 단계의 계획/구현 범위를 표현한다.
```

### Domain QA / Gate

대상 모델:

```text
DomainQAResult
DomainQAPlanningOutput
DomainGateResult
```

역할:

```text
- QA agent가 pass/rework를 판단한다.
- domain gate가 retry/block/pass 라우팅에 사용할 결과를 만든다.
```

추천 주석:

```python
# 도메인 QA와 gate 라우팅 계약.
# QA 결과는 rework 여부를 결정하고, gate는 retry/block/pass로 변환한다.
```

### UIUX Handoff

대상 모델:

```text
UIUXScreenSpec
UIUXUserFlowSpec
UIUXComponentSpec
UIUXFormStateSpec
UIUXFrontendHandoff
UIUXArtifact
```

역할:

```text
- UIUX agent가 frontend agent에게 넘기는 handoff artifact다.
- 화면, route, 상태, API 의존성, 데이터 의존성, 접근성 요구사항을 담는다.
```

추천 주석:

```python
# UIUX -> Frontend handoff 계약.
# frontend_agent와 global_fe_sync_gate가 이 artifact를 기준으로 구현/검증한다.
```

### Global FE Sync

대상 모델:

```text
GlobalFESyncResult
GlobalFESyncPlanningOutput
```

역할:

```text
- UIUX 결과와 Frontend 결과가 같은 화면, route, API 계약을 보고 있는지 검증한다.
- 문제가 있으면 rework_uiux 또는 rework_frontend로 분기한다.
```

추천 주석:

```python
# UIUX와 Frontend 사이의 정합성 검증 결과 계약.
```

### Integration QA

대상 모델:

```text
IntegrationQAResult
IntegrationQAPlanningOutput
```

역할:

```text
- backend/frontend/UIUX 결과를 통합 관점에서 검증한다.
- FE 호출, BE route, SA API contract가 맞는지 확인한다.
- rework_targets로 다시 돌릴 도메인을 지정한다.
```

추천 주석:

```python
# 전체 통합 QA 결과 계약.
# FE/BE/SA 계약 불일치와 runtime smoke 결과를 바탕으로 rework 대상을 지정한다.
```

### Finalization

대상 모델:

```text
BranchPROrchestratorResult
EmbeddingResult
```

역할:

```text
- branch/PR 준비 상태와 merge readiness를 표현한다.
- embedding result는 최종 산출물을 RAG 저장소에 넣기 위한 결과다.
```

추천 주석:

```python
# 파이프라인 마무리 단계의 PR 준비와 산출물 저장 계약.
```

### Codegen / Verification / Repair

대상 모델:

```text
GeneratedCodeFile
BackendCodegenOutput
BackendCodegenVerificationCheck
BackendCodegenVerificationResult
BackendCodegenRepairOutput
FrontendCodegenOutput
```

역할:

```text
- codegen 결과 파일
- verifier 실행 결과
- failed_checks
- dependency_install_plan
- repair agent가 다시 쓸 파일 목록
```

추천 주석:

```python
# codegen, verifier, repair 단계의 파일 기반 계약.
# frontend도 command 실행 검증 구조가 유사해서 일부 backend verification 모델을 재사용한다.
```

## 주석 작성 기준

이 파일들에는 "이 코드가 뭘 하는지"보다 "파이프라인에서 왜 필요한지"를 써야 한다.

좋은 주석:

```python
# Domain Agent는 PM/SA를 직접 재해석하지 않고 이 DEV_TASK.context를 기준으로 작업한다.
```

덜 좋은 주석:

```python
# 리스트를 반환한다.
# 문자열을 만든다.
```

정리:

```text
_shared.py
  PM/SA 결과를 DEV가 쓸 수 있게 정규화하는 공통 계층

schemas.py
  DEV 파이프라인 노드들이 주고받는 데이터 계약 모음
```
