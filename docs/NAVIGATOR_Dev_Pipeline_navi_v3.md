> 이 문서는 기존 codegen 중심 Dev Pipeline을 navi_v3 기준 PR 분석·GAP 검증·PM 승인 파이프라인으로 재정의한 개발문서다.

# NAVIGATOR navi_v3 Dev Pipeline 개발문서

## 1. Dev Pipeline 개요

navi_v3의 Dev Pipeline은 GitHub PR 또는 브랜치 변경사항을 입력으로 받아 실제 구현 상태를 역분석하고, PM/SA 설계 스냅샷과 비교하여 GAP을 탐지하는 개발 추적·검증 파이프라인이다.

Dev Pipeline은 더 이상 "코드 생성기"가 아니다. Dev Pipeline은 "PR 기반 개발 추적·검증 파이프라인"이다. 핵심 가치는 개발 완료 여부 추적, 설계 대비 구현 차이 탐지, 의도된 변경 승인, 비의도 변경 차단이다.

PM은 UI의 `TaskApprovalPanel`에서 PM Report를 확인하고 승인, 거절, 보류, SA 재검토 요청 중 하나를 선택한다. 승인된 변경만 문서, GitHub Wiki, RAG, Agile Task 상태 업데이트로 이어진다.

## 2. navi_v3에서 변경된 핵심 방향

기존 Dev Pipeline은 PM/SA 산출물을 기준으로 UI/UX, Backend, Frontend 코드를 생성하고 QA Gate를 거쳐 Branch/PR을 만드는 구조였다. navi_v3에서는 이 구조를 핵심 흐름에서 폐기한다.

새 구조는 개발자가 이미 만든 PR을 검증한다. PR webhook payload에서 branch명, PR 번호, commit SHA를 추출하고, 브랜치를 checkout한 뒤 실제 코드를 역분석한다. 최신 설계를 무조건 기준으로 쓰지 않고, PR 브랜치 생성 시점의 published snapshot과 비교한다.

구버전 Dev Pipeline의 `Backend Agent`, `Frontend Dev Agent`, `UI/UX Agent`, `Domain Gate`, `Global FE_Sync Gate`, `Integration QA Gate`, `Branch/PR Orchestrator`는 구버전 참고 항목이다. 재사용 가능한 것은 `_run_git`, `_run_gh`, loop controller 분기 개념, embedding 저장 개념, QA gate를 PM 승인 gate로 재해석하는 관점뿐이다.

## 3. 전체 시스템 내 Dev Pipeline 위치

Client Layer는 USER, Electron Desktop(Main + IPC), React 18 / Vite Build로 구성된다. PM은 `TaskApprovalPanel`에서 개발 검증 리포트와 승인 태스크를 본다.

Transport Layer는 `ws_handler`와 REST API(`/api/analyze`, `/api/results`, `/api/tasks`, 향후 `/api/dev-tracking/*`)를 사용한다. Webhook 입력은 REST endpoint로 수신하고, 장기 실행 분석은 WebSocket 또는 비동기 job으로 확장한다.

Auth Layer는 JWT Token payload, `decode_token(role 검증)`, RBAC check, `github_oauth_token`을 사용한다. PR 분석과 승인 액션은 PM 또는 권한 있는 사용자만 실행한다.

Repository Layer는 `connectors.repo_cache.get_local_repo_path()`를 재사용하고, checkout/head SHA 검증은 새 `branch_fetcher`에서 수행한다.

RAG Ingest는 `code_chunker`, `code_embedding`, `project_vector_db`를 보유하지만, Dev Tracking 분석 중에는 임의 upsert를 금지한다. 승인된 GAP Report/PM Report만 metadata를 붙여 저장한다.

PM/SA Pipeline은 Requirement Analyzer, stack planner, MERGE_PROJECT, Component Scheduler, `sa_unified_modeler`, `sa_test_analysis`, `sa_project_structure`를 통해 published snapshot의 기준 데이터를 제공한다.

Agile Pipeline은 `commit_analyzer`, `impact`, `verifier`, `doc_sync`, `wiki_publisher`, `task_coordinator`, `agile_tasks(SQLite)`, `navigator.db`를 제공한다. Dev Tracking은 기존 Agile 노드를 직접 수정하지 않고 public 함수만 호출한다.

## 4. 입력/출력 정의

외부 입력은 GitHub PR/Webhook 중심이다.

```json
{
  "trigger": "GITHUB_PR_WEBHOOK",
  "repository": {
    "owner": "string",
    "repo": "string"
  },
  "pull_request": {
    "pr_number": 12,
    "branch_name": "feature/auth-login",
    "base_branch": "develop",
    "head_sha": "abc123",
    "created_at": "2026-05-19T10:00:00+09:00",
    "title": "feat: implement auth login",
    "description": "string"
  },
  "actor": {
    "github_id": "string",
    "role": "developer"
  }
}
```

최종 출력은 PM 판단이 가능한 분석 결과다.

```json
{
  "status": "PENDING_PM_APPROVAL",
  "pr_context": {},
  "published_spec_snapshot": {},
  "implementation_profile": {},
  "gap_report": [],
  "intent_classification": [],
  "milestone_status": {},
  "pm_report": {},
  "approval_task": {
    "task_id": "uuid",
    "task_type": "dev_gap_approval"
  },
  "pr_comment": {}
}
```

## 5. Pipeline State Schema

새 상태는 기존 `PipelineState`에 독립 필드로 추가하고, 기존 PM/SA/Agile/RAG 필드는 직접 변경하지 않는다.

```json
{
  "trigger": "GITHUB_PR_WEBHOOK",
  "repository": {},
  "pull_request": {},
  "actor": {},
  "pr_context": {},
  "source_dir": "string",
  "project_context": "string",
  "code_inventory": {},
  "published_spec_snapshot": {},
  "spec_outdated": false,
  "latest_snapshot": {},
  "implementation_profile": {},
  "gap_report": [],
  "has_high_gap": false,
  "intent_classification": [],
  "milestone_status": {},
  "pm_report": {},
  "approval_status": "PENDING",
  "pr_comment": {},
  "dev_tracking_next_action": "branch_fetcher",
  "dev_tracking_loop_count": 0
}
```

상태값은 `PENDING_PM_APPROVAL`, `APPROVED_INTENTIONAL_CHANGE`, `REJECTED_UNINTENTIONAL_CHANGE`, `NEEDS_SA_REVIEW`, `BLOCKED`, `COMPLETED`를 사용한다.

## 6. 전체 실행 흐름

```text
GitHub PR Webhook
  -> dev_task_planner
  -> branch_fetcher
  -> reverse_analyzer
  -> code_inventory_builder
  -> forensic_profiler
  -> spec_loader
  -> gap_analyzer
  -> intent_classifier
  -> milestone_tracker
  -> pm_report_generator
  -> pr_comment_notifier
  -> task_coordinator
  -> develop_embedding
  -> develop_loop_controller
     -> next_pr: branch_fetcher
     -> complete: END
```

이 흐름은 `requirements_rtm` 기반 DEV_TASK 생성이 아니다. GAP이 없으면 `milestone_tracker`로 바로 통과한다. HIGH GAP이 있으면 `intent_classifier`로 넘겨 의도된 변경인지 판단한다. PM 승인이 필요한 항목은 `agile_tasks(SQLite)`에 적재한다. PR에는 자동 merge나 새 PR 생성이 아니라 검토 코멘트와 PM 승인 대기 링크를 남긴다.

## 7. GitHub Webhook 처리

Webhook endpoint는 PR opened, synchronize, reopened 이벤트를 처리한다. 입력에서 owner, repo, pr_number, branch_name, base_branch, head_sha, created_at, title, description, actor를 정규화한다.

보안 기준:

- GitHub token은 서버 로그와 PR comment에 노출하지 않는다.
- PM 승인 endpoint는 JWT + RBAC를 통과해야 한다.
- checkout 대상 branch와 head_sha가 webhook payload와 일치하지 않으면 분석을 중단한다.

## 8. dev_task_planner 설계

### 목적

Webhook payload를 PR 분석 작업으로 정규화하고 이후 노드가 사용할 `pr_context`를 만든다.

### 기존 재활용 여부

기존 재활용, 수정 필요. 구버전 `dev_task_planner`의 "작업 컨텍스트 생성" 개념만 재사용하고, `requirements_rtm` 기반 feature queue 생성은 사용하지 않는다.

### 입력

```json
{
  "trigger": "GITHUB_PR_WEBHOOK",
  "repository": {"owner": "org", "repo": "navigator"},
  "pull_request": {
    "pr_number": 12,
    "branch_name": "feature/auth-login",
    "base_branch": "develop",
    "head_sha": "abc123",
    "created_at": "2026-05-19T10:00:00+09:00",
    "title": "feat: implement auth login",
    "description": "login implementation"
  },
  "actor": {"github_id": "dev-a", "role": "developer"}
}
```

### 처리 과정

1. 필수 필드(owner, repo, pr_number, branch_name, head_sha)를 검증한다.
2. `branch_created_at`이 없으면 PR `created_at`을 기준 시간으로 사용한다.
3. PR 중심 분석 컨텍스트를 `pr_context`에 저장한다.
4. 다음 노드를 `branch_fetcher`로 지정한다.

### 출력

```json
{
  "node": "dev_task_planner",
  "status": "PASS",
  "pr_context": {
    "owner": "org",
    "repo": "navigator",
    "branch_name": "feature/auth-login",
    "base_branch": "develop",
    "pr_number": 12,
    "head_sha": "abc123",
    "created_at": "2026-05-19T10:00:00+09:00",
    "title": "feat: implement auth login",
    "description": "login implementation"
  },
  "dev_tracking_next_action": "branch_fetcher"
}
```

### 검증 기준

PASS는 필수 필드가 모두 있고 PR 번호가 정수이며 head SHA가 비어 있지 않은 경우다. FAIL은 payload 누락, repo 정보 누락, PR 번호 형식 오류다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "INVALID_WEBHOOK_PAYLOAD",
  "fallback": "manual_review",
  "dev_tracking_next_action": "blocked"
}
```

### 구현 메모

새 파일 `pipeline/domain/dev_tracking/nodes/dev_task_planner.py`에 구현한다. 기존 `pipeline.domain.agile` 파일은 수정하지 않는다.

## 9. branch_fetcher 설계

### 목적

PR 브랜치를 로컬 repo cache에 준비하고 분석 대상 `source_dir`를 확정한다.

### 기존 재활용 여부

신규. `connectors.repo_cache.get_local_repo_path(owner, repo, token)`를 호출한다.

### 입력

```json
{
  "pr_context": {
    "owner": "org",
    "repo": "navigator",
    "branch_name": "feature/auth-login",
    "head_sha": "abc123"
  },
  "github_oauth_token": "masked"
}
```

### 처리 과정

1. `get_local_repo_path()`로 로컬 저장소 경로를 확보한다.
2. `git fetch origin <branch_name>`을 실행한다.
3. `git checkout <branch_name>` 또는 detached checkout을 수행한다.
4. `git rev-parse HEAD`가 `head_sha`와 일치하는지 검증한다.
5. 성공 시 `source_dir`에 repo path를 저장한다.

### 출력

```json
{
  "node": "branch_fetcher",
  "status": "PASS",
  "source_dir": "backend/storage/repo_cache/org/navigator",
  "checkout": {
    "branch_name": "feature/auth-login",
    "head_sha": "abc123",
    "head_sha_matched": true
  },
  "dev_tracking_next_action": "reverse_analyzer"
}
```

### 검증 기준

PASS는 checkout 성공, `.git` 존재, head SHA 일치다. FAIL은 token 권한 오류, branch 없음, head SHA 불일치, repo path 없음이다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "BRANCH_CHECKOUT_FAILED",
  "fallback": "manual_review",
  "dev_tracking_next_action": "blocked"
}
```

### 구현 메모

기존 dev-pipeline의 `_run_git` 개념을 새 util로 옮긴다. 구버전 `branch_pr_orchestrator`는 복원하지 않는다.

## 10. reverse_analyzer 설계

### 목적

checkout된 실제 코드를 사람이 읽을 수 있는 프로젝트 컨텍스트로 요약한다.

### 기존 재활용 여부

신규 래퍼 노드. `orchestration.pipeline_runner.build_reverse_context(source_dir)`를 그대로 호출한다.

### 입력

```json
{
  "source_dir": "backend/storage/repo_cache/org/navigator"
}
```

### 처리 과정

1. `source_dir`가 존재하는지 확인한다.
2. `build_reverse_context(source_dir)`를 호출한다.
3. 반환 문자열을 `project_context`에 저장한다.

### 출력

```json
{
  "node": "reverse_analyzer",
  "status": "PASS",
  "project_context": "scanned_files: 42\nscanned_functions: 180\n...",
  "dev_tracking_next_action": "code_inventory_builder"
}
```

### 검증 기준

PASS는 context 문자열이 생성되는 경우다. 빈 문자열이면 FAIL이 아니라 `manual_review_required: true`를 붙이고 다음 노드로 진행할 수 있다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "REVERSE_CONTEXT_EMPTY",
  "fallback": "continue_with_inventory",
  "dev_tracking_next_action": "code_inventory_builder"
}
```

### 구현 메모

기존 `pipeline_runner.py`는 수정하지 않는다. import 경계만 사용한다.

## 11. code_inventory_builder 설계

### 목적

PR 브랜치의 실제 코드 구조를 메모리 내 inventory로 만든다.

### 기존 재활용 여부

신규. RAG `code_chunker`의 AST 파싱 로직 또는 `_process_file()` 개념을 재사용한다.

### 입력

```json
{
  "source_dir": "backend/storage/repo_cache/org/navigator",
  "changed_files": ["backend/api/auth.py"]
}
```

### 처리 과정

1. 변경 파일 목록이 있으면 해당 파일만 분석한다.
2. 없으면 repo 전체에서 Python/JS/TS/JSX/TSX 파일을 제한 개수까지 스캔한다.
3. 함수, 클래스, endpoint 후보, component 후보, docstring, line range를 추출한다.
4. ChromaDB 저장 없이 `code_inventory`에만 저장한다.

### 출력

```json
{
  "code_inventory": {
    "backend/api/auth.py": [
      {
        "name": "login",
        "type": "function",
        "docstring": "string",
        "start_line": 10,
        "end_line": 42
      }
    ]
  },
  "dev_tracking_next_action": "forensic_profiler"
}
```

### 검증 기준

PASS는 최소 1개 파일을 분석했거나, 변경 파일이 모두 삭제 파일로 확인된 경우다. FAIL은 source_dir 접근 불가다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "CODE_INVENTORY_FAILED",
  "fallback": "manual_review",
  "dev_tracking_next_action": "blocked"
}
```

### 구현 메모

이 단계에서는 RAG upsert를 금지한다. 분석용 state만 갱신한다.

## 12. forensic_profiler 설계

### 목적

코드 inventory와 reverse context를 바탕으로 구현 프로필을 생성한다.

### 기존 재활용 여부

기존 SA forensic profiler의 역할을 재해석하되 기존 노드는 수정하지 않는다. 새 wrapper가 `code_inventory`를 직접 LLM 입력으로 구성한다.

### 입력

```json
{
  "project_context": "string",
  "code_inventory": {}
}
```

### 처리 과정

1. 파일별 역할, API 후보, component 후보를 inventory에서 추출한다.
2. 구현 의도와 변경 영향도를 요약한다.
3. LLM 사용 가능 시 구조화 출력으로 `implementation_profile`을 생성한다.
4. LLM 실패 시 rule-based profile을 만든다.

### 출력

```json
{
  "implementation_profile": {
    "detected_apis": [],
    "detected_components": [],
    "file_role_map": {},
    "implementation_summary": "로그인 API와 인증 UI 일부가 구현되었습니다."
  },
  "dev_tracking_next_action": "spec_loader"
}
```

### 검증 기준

PASS는 `implementation_profile`이 생성되는 경우다. LLM 실패 후 fallback profile 생성은 WARN이다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "LLM_PROFILE_FALLBACK",
  "fallback": "rule_based_profile",
  "dev_tracking_next_action": "spec_loader"
}
```

### 구현 메모

기존 SA 노드 파일은 건드리지 않는다. 공통 LLM 호출 helper만 public API로 사용한다.

## 13. spec_loader 설계

### 목적

PR 브랜치 생성 시점 기준의 PM/SA 설계 스냅샷을 로드한다.

### 기존 재활용 여부

신규. `storage/publish_service.py`, `auth.shared_models.PublishedSnapshot`, `get_shared_db` 조회 패턴을 참고한다.

### 입력

```json
{
  "pr_context": {
    "created_at": "2026-05-19T10:00:00+09:00"
  },
  "team_id": "team-1"
}
```

### 처리 과정

1. `published_at <= branch_created_at` 조건의 최신 snapshot을 찾는다.
2. 현재 최신 snapshot도 별도로 조회한다.
3. 기준 snapshot보다 최신 snapshot이 있으면 `spec_outdated: true`로 표시한다.
4. PM spec, SA spec, API contract, component contract, milestone/task status를 추출한다.

### 출력

```json
{
  "published_spec_snapshot": {
    "snapshot_id": "31",
    "published_at": "2026-05-18T13:00:00+09:00",
    "pm_spec_version": "v1.3",
    "sa_spec_version": "v1.3",
    "api_contracts": [],
    "component_contracts": []
  },
  "spec_outdated": true,
  "latest_snapshot": {
    "snapshot_id": "35",
    "published_at": "2026-05-19T09:00:00+09:00"
  },
  "dev_tracking_next_action": "gap_analyzer"
}
```

### 검증 기준

PASS는 기준 snapshot을 찾은 경우다. snapshot이 없으면 manual review로 진행하되 GAP 분석은 제한한다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "SPEC_SNAPSHOT_NOT_FOUND",
  "fallback": "manual_review",
  "dev_tracking_next_action": "pm_report_generator"
}
```

### 구현 메모

기존 `published_snapshots` 모델에는 `snapshot_data`, `version`, `published_at`이 있다. 문서의 `project_id`, `snapshot_type`, `artifact_path`, `artifact_hash`는 향후 확장 컬럼으로 둔다.

## 14. gap_analyzer 설계

### 목적

published spec snapshot과 implementation profile을 비교하여 설계 대비 구현 차이를 추출한다.

### 기존 재활용 여부

신규 LLM 노드. 구버전 `integration_qa_gate`의 contract check 관점만 참고한다.

### 입력

```json
{
  "published_spec_snapshot": {},
  "implementation_profile": {},
  "spec_outdated": true
}
```

### 처리 과정

1. API contract와 detected APIs를 비교한다.
2. component contract와 detected components를 비교한다.
3. 권한/RBAC, 응답 스키마, 테스트 누락, 설계 의도 불일치를 확인한다.
4. GAP을 HIGH/MED/LOW로 분류한다.
5. `spec_outdated`로 인한 GAP이면 `spec_outdated_related`를 표시한다.

### 출력

```json
{
  "gap_report": [
    {
      "gap_id": "GAP_001",
      "severity": "HIGH",
      "type": "MISSING_API",
      "spec_target": "POST /api/v1/auth/login",
      "implementation_target": null,
      "description": "설계된 로그인 API가 구현에서 발견되지 않았습니다.",
      "spec_outdated_related": false
    }
  ],
  "has_high_gap": true,
  "dev_tracking_next_action": "intent_classifier"
}
```

### 검증 기준

PASS는 `gap_report`가 list이고 각 item에 `gap_id`, `severity`, `type`, `description`이 있는 경우다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "GAP_ANALYSIS_FAILED",
  "fallback": "manual_review",
  "dev_tracking_next_action": "pm_report_generator"
}
```

### 구현 메모

GAP 없음이면 `has_high_gap: false`, `dev_tracking_next_action: milestone_tracker`를 반환한다.

## 15. intent_classifier 설계

### 목적

GAP이 의도된 변경인지, 비의도 변경인지, 불확실한지 분류한다.

### 기존 재활용 여부

신규 LLM 노드.

### 입력

```json
{
  "gap_report": [],
  "pr_context": {
    "title": "feat: implement auth login",
    "description": "string"
  },
  "implementation_profile": {},
  "spec_outdated": true
}
```

### 처리 과정

1. PR title, description, commit message, 변경 파일을 수집한다.
2. GAP별로 의도 분류 근거를 만든다.
3. `spec_outdated: true`인 GAP은 INTENTIONAL 후보로 우선 보되 근거가 없으면 UNCERTAIN으로 둔다.
4. PM 승인 필요 여부를 계산한다.

### 출력

```json
{
  "intent_classification": [
    {
      "gap_id": "GAP_001",
      "intent": "UNINTENTIONAL",
      "confidence": 0.82,
      "reason": "PR 설명에는 인증 API 구현이 포함되어 있으나 실제 endpoint가 누락되어 있습니다.",
      "recommended_action": "REQUEST_FIX"
    }
  ],
  "requires_pm_approval": true,
  "dev_tracking_next_action": "milestone_tracker"
}
```

### 검증 기준

PASS는 모든 HIGH GAP에 classification이 있는 경우다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "INTENT_UNCERTAIN",
  "fallback": "pm_manual_decision",
  "dev_tracking_next_action": "milestone_tracker"
}
```

### 구현 메모

분류값은 `INTENTIONAL`, `UNINTENTIONAL`, `UNCERTAIN`만 사용한다.

## 16. milestone_tracker 설계

### 목적

GAP과 intent 결과를 반영하여 milestone 진행률과 blocked 상태를 계산한다.

### 기존 재활용 여부

기존 feature queue controller의 상태 집계 개념을 재사용한다. 기존 파일은 수정하지 않고 새 노드로 구현한다.

### 입력

```json
{
  "gap_report": [],
  "intent_classification": [],
  "published_spec_snapshot": {}
}
```

### 처리 과정

1. snapshot의 milestone/task status를 읽는다.
2. 완료 feature, blocked feature, PM 승인 대기 feature를 계산한다.
3. HIGH + UNINTENTIONAL GAP은 blocked로 집계한다.
4. completion rate와 예상 완료일을 계산한다.

### 출력

```json
{
  "milestone_status": {
    "milestone_id": "M1",
    "completion_rate": 72,
    "completed_features": 18,
    "total_features": 25,
    "blocked_features": 2,
    "estimated_completion_date": "2026-05-27"
  },
  "dev_tracking_next_action": "pm_report_generator"
}
```

### 검증 기준

PASS는 completion_rate가 0-100 범위이고 total_features가 음수가 아닌 경우다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "MILESTONE_DATA_MISSING",
  "fallback": "report_without_milestone",
  "dev_tracking_next_action": "pm_report_generator"
}
```

### 구현 메모

`dev_feature_status`라는 이름을 쓰더라도 의미는 PR 분석 상태로 제한한다.

## 17. pm_report_generator 설계

### 목적

PM이 UI에서 승인/거절 판단을 할 수 있는 리포트를 생성한다.

### 기존 재활용 여부

신규. 구버전 `feature_completion_qa_report()`의 report assembly 개념만 참고한다.

### 입력

```json
{
  "pr_context": {},
  "implementation_profile": {},
  "gap_report": [],
  "intent_classification": [],
  "milestone_status": {},
  "spec_outdated": true
}
```

### 처리 과정

1. PR 요약과 구현 요약을 만든다.
2. GAP 중요도별 summary를 만든다.
3. 의도 분류 결과와 recommended action을 묶는다.
4. spec outdated 경고를 문장으로 만든다.
5. PM 액션 후보를 생성한다.

### 출력

```json
{
  "pm_report": {
    "summary": "로그인 기능 PR에서 설계 대비 2개의 GAP이 발견되었습니다.",
    "gap_summary": [],
    "intent_summary": [],
    "milestone_summary": {},
    "spec_outdated_warning": "개발자는 v1.3 기준으로 작업했으나 현재 v1.4 설계가 존재합니다.",
    "recommended_pm_actions": ["APPROVE_AS_INTENTIONAL", "REQUEST_FIX"]
  },
  "approval_status": "PENDING_PM_APPROVAL",
  "dev_tracking_next_action": "pr_comment_notifier"
}
```

### 검증 기준

PASS는 `summary`, `gap_summary`, `recommended_pm_actions`가 존재하는 경우다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "PM_REPORT_GENERATION_FAILED",
  "fallback": "manual_review",
  "dev_tracking_next_action": "task_coordinator"
}
```

### 구현 메모

`TaskApprovalPanel`은 `/api/tasks`를 읽으므로 report 전체를 task payload에 넣는다.

## 18. pr_comment_notifier 설계

### 목적

이미 존재하는 PR에 GAP 요약과 PM 승인 대기 링크를 남긴다.

### 기존 재활용 여부

기존 `branch_pr_orchestrator`의 `_run_gh()`, `_run_git()` 유틸 개념을 새 util로 재작성한다. PR 생성, commit 생성, 자동 merge 기능은 사용하지 않는다.

### 입력

```json
{
  "pr_context": {"pr_number": 12, "owner": "org", "repo": "navigator"},
  "pm_report": {},
  "approval_task_url": "/tasks/approval/PR-12"
}
```

### 처리 과정

1. PM report에서 HIGH/MED/LOW GAP 개수를 계산한다.
2. 승인 대기 링크를 포함한 Markdown comment를 만든다.
3. `gh pr comment 12 --body ...`를 실행한다.
4. 실패해도 task 생성은 계속 진행한다.

### 출력

```json
{
  "pr_comment": {
    "pr_number": 12,
    "comment_created": true,
    "approval_url": "/tasks/approval/PR-12",
    "summary": "HIGH GAP 1건, MED GAP 2건이 발견되었습니다."
  },
  "dev_tracking_next_action": "task_coordinator"
}
```

### 검증 기준

PASS는 comment 생성 성공이다. `gh` 미설치 또는 권한 오류는 WARN이다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "PR_COMMENT_FAILED",
  "fallback": "continue_task_creation",
  "dev_tracking_next_action": "task_coordinator"
}
```

### 구현 메모

자동 merge, 자동 approve, `gh pr create`는 금지한다.

## 19. task_coordinator 설계

### 목적

PM 승인 필요 태스크를 `agile_tasks(SQLite)` 큐에 넣고 `TaskApprovalPanel`에서 볼 수 있게 한다.

### 기존 재활용 여부

기존 Agile `pipeline.domain.agile.task_coordinator.create_task()`와 `update_task_status()`를 호출한다. 기존 파일은 수정하지 않는다.

### 입력

```json
{
  "pm_report": {},
  "approval_status": "PENDING_PM_APPROVAL",
  "pr_context": {}
}
```

### 처리 과정

1. task_type은 `dev_gap_approval`을 사용한다.
2. title은 `PR #12 GAP 승인 요청` 형식으로 만든다.
3. payload에 `pm_report`, `gap_report`, `intent_classification`, `pr_context`를 저장한다.
4. status는 기존 시스템 호환을 위해 우선 `pending`으로 저장하고, payload의 `approval_status`에 상세 상태를 둔다.

### 출력

```json
{
  "approval_task": {
    "task_id": "uuid",
    "task_type": "dev_gap_approval",
    "status": "pending"
  },
  "dev_tracking_next_action": "develop_embedding"
}
```

### 검증 기준

PASS는 task id가 생성되고 `list_tasks(status="pending")`에서 조회 가능한 경우다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "TASK_QUEUE_INSERT_FAILED",
  "fallback": "manual_review",
  "dev_tracking_next_action": "blocked"
}
```

### 구현 메모

향후 기존 task status enum 확장이 가능해지면 `PENDING_PM_APPROVAL` 등을 DB status로 승격한다.

## 20. develop_embedding 설계

### 목적

GAP 분석 결과, PM Report, 승인 결과를 RAG/PM artifact에 저장한다.

### 기존 재활용 여부

기존 dev-pipeline embedding의 저장 개념을 재사용한다. 실제 구현은 새 `dev_tracking` 노드에서 `upsert_pm_artifact()`와 `upsert_code_chunk()` public API만 호출한다.

### 입력

```json
{
  "pm_report": {},
  "gap_report": [],
  "approval_status": "PENDING",
  "pr_context": {}
}
```

### 처리 과정

1. `DEV_GAP_REPORT`, `DEV_PM_REPORT` artifact를 만든다.
2. 실패한 변경사항을 정답 코드처럼 PROJECT_RAG에 저장하지 않는다.
3. 승인 전에는 분석 결과만 metadata로 저장한다.
4. 승인 후 별도 flow에서 문서/Wiki/RAG 최종 반영을 수행한다.

### 출력

```json
{
  "embedding_result": {
    "status": "persisted",
    "metadata": {
      "artifact_type": "DEV_GAP_REPORT",
      "pr_number": 12,
      "branch_name": "feature/auth-login",
      "approval_status": "PENDING",
      "gap_count": 3,
      "has_high_gap": true
    }
  },
  "dev_tracking_next_action": "develop_loop_controller"
}
```

### 검증 기준

PASS는 PM artifact 저장이 성공한 경우다. RAG 저장 실패는 WARN으로 두고 PM 승인 태스크는 유지한다.

### 실패 처리

```json
{
  "status": "WARN",
  "error_type": "DEV_REPORT_EMBEDDING_FAILED",
  "fallback": "continue_without_rag",
  "dev_tracking_next_action": "develop_loop_controller"
}
```

### 구현 메모

metadata에 `approval_status`, `pr_number`, `branch_name`, `gap_count`를 반드시 포함한다.

## 21. develop_loop_controller 설계

### 목적

현재 PR 분석 이후 다음 PR 분석, 완료, blocked, retry를 결정한다.

### 기존 재활용 여부

기존 dev-pipeline loop controller의 분기 개념을 재사용한다.

### 입력

```json
{
  "approval_status": "PENDING_PM_APPROVAL",
  "dev_tracking_loop_count": 0,
  "pending_pr_queue": []
}
```

### 처리 과정

1. PM approval pending이면 `blocked` 또는 `complete_pending_approval`로 종료한다.
2. pending PR queue가 있으면 `NEXT_PR`을 반환한다.
3. 실패 원인이 retry 가능하고 max retry 미만이면 `RETRY_CURRENT_PR`을 반환한다.
4. 아니면 `COMPLETE`로 종료한다.

### 출력

```json
{
  "loop_decision": "NEXT_PR",
  "dev_tracking_next_action": "branch_fetcher"
}
```

### 검증 기준

PASS는 decision이 `NEXT_PR`, `COMPLETE`, `BLOCKED`, `RETRY_CURRENT_PR` 중 하나인 경우다.

### 실패 처리

```json
{
  "status": "FAIL",
  "error_type": "LOOP_DECISION_INVALID",
  "fallback": "manual_review",
  "dev_tracking_next_action": "blocked"
}
```

### 구현 메모

`next_feature`라는 이름은 사용하지 않는다. navi_v3에서는 `next_pr`로 재해석한다.

## 22. PM 승인/거절 플로우

```text
[PM 판단 - TaskApprovalPanel]
  -> 승인(의도된 변경)
     -> doc_updater/doc_sync
     -> 설계 문서와 GitHub Wiki 업데이트
     -> spec_outdated이면 SQLite에 브랜치 기준 설계 버전 고정 기록
     -> RAG metadata 승인 상태 갱신
  -> 거절(비의도 변경)
     -> pr_comment_notifier 재호출
     -> "설계 의도와 불일치, 재검토 필요" 코멘트 추가
     -> merge 차단 상태 유지
  -> 보류
     -> PENDING_PM_APPROVAL 유지
  -> SA 재검토 요청
     -> NEEDS_SA_REVIEW task 생성
```

PM은 `TaskApprovalPanel`에서 GAP 리포트를 확인한다. 승인하면 해당 변경은 의도된 변경으로 간주한다. 승인된 변경은 `doc_sync` 확장 또는 새 `doc_updater`를 통해 설계 문서와 GitHub Wiki에 반영된다. 거절하면 PR에 재검토 코멘트를 남기고 merge를 차단한다.

## 23. SQLite / navigator.db 연동

`published_snapshots`는 기존 shared DB 모델을 우선 사용한다. 현재 모델은 `id`, `run_id`, `team_id`, `published_by`, `title`, `description`, `version`, `snapshot_data`, `published_at`를 가진다. 문서의 `project_id`, `snapshot_type`, `artifact_path`, `artifact_hash`, `created_by`는 다음 단계 마이그레이션 후보로 둔다.

신규 테이블 후보:

```text
dev_pr_analysis
- id
- project_id
- repo_owner
- repo_name
- pr_number
- branch_name
- head_sha
- branch_created_at
- analysis_status
- spec_snapshot_id
- spec_outdated
- created_at
- updated_at

dev_gap_items
- id
- analysis_id
- gap_type
- severity
- spec_target
- implementation_target
- description
- intent
- confidence
- recommended_action
- approval_status
```

`agile_tasks`는 기존 테이블을 재활용한다. 추가 상태는 payload에 먼저 저장하고, DB 마이그레이션 단계에서 `PENDING_PM_APPROVAL`, `APPROVED_INTENTIONAL_CHANGE`, `REJECTED_UNINTENTIONAL_CHANGE`, `NEEDS_SA_REVIEW`, `BLOCKED`를 status enum으로 승격한다.

## 24. GitHub API 연동

GitHub 연동은 세 단계로 제한한다.

1. repo checkout: `repo_cache` + git fetch/checkout
2. PR 정보 조회: GitHub REST 또는 `gh pr view`
3. PR comment: `gh pr comment` 또는 GitHub REST issue comment API

금지 사항:

- 자동 merge 금지
- 자동 approve 금지
- 새 PR 자동 생성 금지
- token 로그 출력 금지

## 25. RAG 저장 정책

분석 중 생성된 inventory는 RAG에 저장하지 않는다. 승인 전에는 GAP Report와 PM Report만 `DEV_GAP_REPORT`, `DEV_PM_REPORT` artifact로 저장한다.

승인된 변경은 문서 업데이트와 함께 별도 metadata로 저장한다. 거절된 PR의 코드는 정답 코드처럼 `project_vector_db`에 반영하지 않는다.

metadata 예시:

```json
{
  "artifact_type": "DEV_GAP_REPORT",
  "pr_number": 12,
  "branch_name": "feature/auth-login",
  "approval_status": "PENDING",
  "gap_count": 3,
  "has_high_gap": true
}
```

## 26. Retry / Fallback 정책

분석 실패는 즉시 코드 변경으로 보정하지 않고 PM이 판단 가능한 상태로 남긴다.

- webhook payload 오류: `INVALID_WEBHOOK_PAYLOAD`, blocked
- checkout 실패: `BRANCH_CHECKOUT_FAILED`, manual review
- spec snapshot 누락: `SPEC_SNAPSHOT_NOT_FOUND`, report_without_spec
- LLM 판단 불확실: `INTENT_UNCERTAIN`, PM manual decision
- PR comment 실패: `PR_COMMENT_FAILED`, task 생성은 계속 진행
- RAG 저장 실패: `DEV_REPORT_EMBEDDING_FAILED`, 분석 결과는 DB task payload에 유지

## 27. 보안 및 권한 정책

PR 분석 실행은 인증된 사용자만 가능하다. PM 승인/거절은 PM role 또는 명시 권한을 가진 사용자만 가능하다.

GitHub token은 DB 저장 정책을 따르며, 로그/LLM prompt/PR comment에 직접 포함하지 않는다. checkout 경로는 repo cache 하위로 제한하고, 파일 분석은 `source_dir` 밖으로 벗어나는 path를 거부한다.

## 28. 테스트 전략

필수 테스트:

1. Webhook payload parsing test
2. branch checkout test
3. reverse_analyzer context generation test
4. code_inventory_builder AST parsing test
5. spec_loader snapshot matching test
6. outdated spec detection test
7. gap_analyzer high gap detection test
8. intent_classifier intentional/unintentional classification test
9. milestone_tracker completion rate calculation test
10. pm_report_generator report schema test
11. pr_comment_notifier gh pr comment test
12. task_coordinator SQLite queue insert test
13. develop_embedding metadata upsert test
14. loop_controller next_pr / complete / blocked routing test
15. PM approval approve/reject E2E test

기존 PM/SA/Agile/RAG 테스트는 수정하지 않는다. 새 테스트는 `backend/test/test_dev_tracking_pipeline.py`처럼 별도 파일에 둔다.

## 29. 구현 우선순위

MVP는 세로 흐름 우선이다.

1. `dev_task_planner`, `branch_fetcher`, `reverse_analyzer`
2. `code_inventory_builder`, rule-based `forensic_profiler`
3. `spec_loader`, rule-based `gap_analyzer`
4. `pm_report_generator`, `task_coordinator`
5. `pr_comment_notifier`
6. `develop_embedding`, `develop_loop_controller`
7. LLM 기반 `intent_classifier` 고도화
8. PM 승인 후 `doc_updater/doc_sync` 확장

## 30. 개발팀 체크리스트

- 기존 PM/SA/Agile/RAG 노드를 직접 수정하지 않았는가?
- 새 코드는 `pipeline.domain.dev_tracking`에 격리되었는가?
- PR checkout 후 head SHA를 검증하는가?
- snapshot 기준 시간이 PR branch 생성 시점인가?
- GAP 없음, HIGH GAP, snapshot outdated, LLM uncertain 케이스가 모두 처리되는가?
- PM 승인 태스크가 `TaskApprovalPanel`에서 보이는가?
- 거절 시 PR comment가 남고 자동 merge가 실행되지 않는가?
- 승인 전 실패 PR 코드가 RAG 정답 데이터로 저장되지 않는가?

## 31. 최종 성공 기준

PR webhook 하나를 입력했을 때 다음이 가능해야 한다.

- PR branch checkout 및 head SHA 검증
- 실제 코드 inventory 생성
- published snapshot과 구현 profile 비교
- GAP Report 및 intent classification 생성
- PM Report 생성
- `agile_tasks`에 승인 태스크 생성
- PR에 승인 대기 comment 생성
- PM 승인/거절 결과에 따른 문서/Wiki/RAG 후속 처리 경로 확보

## 32. 기존 문서 대비 변경 요약

기존 문서의 codegen 중심 설명은 구버전 참고로 축소한다. navi_v3 문서는 PR 분석, GAP 검증, PM 승인, 문서/Wiki/RAG 반영을 핵심으로 둔다.

유지되는 개념은 QA Gate, RAG Update, PROJECT_STATE, Retry/Fallback이다. 단, QA Gate는 GAP 분석 및 PM 승인 gate로, RAG Update는 GAP Report/PM Report/승인 결과 저장으로, PROJECT_STATE는 PR 분석 상태 및 milestone 상태 관리로 재해석한다.

## MVP 구현 우선순위

1. 새 `pipeline.domain.dev_tracking` 패키지 생성
2. Webhook payload -> PR context -> branch checkout -> reverse context 생성
3. code inventory와 snapshot loader 구현
4. rule-based GAP Report와 PM Report 생성
5. `agile_tasks` 승인 태스크 생성
6. PR comment notifier 연결
7. 승인 후 doc_sync/RAG 저장 흐름 확장

## 기존 코드 재활용 목록

- `connectors.repo_cache.get_local_repo_path`
- `orchestration.pipeline_runner.build_reverse_context`
- `pipeline.domain.agile.task_coordinator.create_task`
- `pipeline.domain.agile.task_coordinator.update_task_status`
- `pipeline.domain.agile.nodes.doc_sync.sync_docs`
- `auth.shared_models.PublishedSnapshot`
- RAG `code_chunker`의 AST parsing 개념
- 기존 dev-pipeline-clean의 `_run_git`, `_run_gh`, loop controller, embedding 저장 개념

## Claude Code에게 바로 줄 수 있는 1차 구현 태스크 목록

1. `pipeline.domain.dev_tracking` 패키지를 만들고 `dev_task_planner`, `branch_fetcher`, `reverse_analyzer`를 구현하라.
2. 기존 노드를 수정하지 말고 `repo_cache.get_local_repo_path`와 `build_reverse_context`만 호출하라.
3. `code_inventory_builder`는 RAG upsert 없이 메모리 state만 생성하라.
4. `spec_loader`는 `published_snapshots`에서 PR created_at 이하의 최신 snapshot을 선택하라.
5. MVP `gap_analyzer`는 rule-based로 API/component 누락과 추가를 먼저 감지하라.
6. `pm_report_generator`는 `TaskApprovalPanel` payload에 넣을 JSON을 생성하라.
7. `task_coordinator` adapter는 `create_task(task_type="dev_gap_approval")`만 호출하라.
8. `pr_comment_notifier`는 `gh pr comment`만 실행하고 PR 생성/merge/approve는 금지하라.
9. `develop_embedding`은 GAP Report와 PM Report metadata만 저장하고 실패 코드를 project RAG에 정답처럼 저장하지 마라.
10. `test_dev_tracking_pipeline.py`에 payload parsing, checkout, snapshot matching, GAP report, task queue insert 테스트를 추가하라.
