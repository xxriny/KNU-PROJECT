from __future__ import annotations

from typing import List

from pydantic import BaseModel, Field


class DomainTaskSpec(BaseModel):
    domain: str
    goal: str = ""
    requirement_ids: List[str] = Field(default_factory=list)
    focus: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    target_components: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)


class MainAgentBranchItem(BaseModel):
    domain: str
    branch: str


class MainAgentBranchStrategy(BaseModel):
    gitflow: str = "git-flow"
    base_branch: str = "develop"
    epic_branch: str = ""
    domain_branches: List[MainAgentBranchItem] = Field(default_factory=list)


class MainAgentTaskSpec(BaseModel):
    domain: str
    goal: str = ""
    requirement_ids: List[str] = Field(default_factory=list)
    focus: List[str] = Field(default_factory=list)
    inputs: List[str] = Field(default_factory=list)
    target_components: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)


class MainAgentPlanningOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    goal: str = ""
    selected_domains: List[str] = Field(default_factory=list)
    branch_strategy: MainAgentBranchStrategy = Field(default_factory=MainAgentBranchStrategy)
    task_specs: List[MainAgentTaskSpec] = Field(default_factory=list)


class DevelopMainPlan(BaseModel):
    goal: str = ""
    selected_domains: List[str] = Field(default_factory=list)
    project_rag_context: dict = Field(default_factory=dict)
    artifact_rag_context: dict = Field(default_factory=dict)
    branch_strategy: dict = Field(default_factory=dict)
    task_specs: dict = Field(default_factory=dict)


class DomainAgentResult(BaseModel):
    status: str = "draft"
    domain: str
    summary: str = ""
    requirement_ids: List[str] = Field(default_factory=list)
    proposed_changes: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    test_plan: List[str] = Field(default_factory=list)


class DomainAgentPlanningOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    status: str = "draft"
    domain: str
    summary: str = ""
    requirement_ids: List[str] = Field(default_factory=list)
    proposed_changes: List[str] = Field(default_factory=list)
    files: List[str] = Field(default_factory=list)
    dependencies: List[str] = Field(default_factory=list)
    test_plan: List[str] = Field(default_factory=list)


class DomainQAResult(BaseModel):
    status: str = "pass"
    domain: str
    findings: List[str] = Field(default_factory=list)
    fixes_required: List[str] = Field(default_factory=list)


class DomainQAPlanningOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    status: str = "pass"
    domain: str
    findings: List[str] = Field(default_factory=list)
    fixes_required: List[str] = Field(default_factory=list)


class UIUXScreenSpec(BaseModel):
    id: str
    name: str
    purpose: str = ""
    route: str = ""
    requirement_ids: List[str] = Field(default_factory=list)
    acceptance_criteria: List[str] = Field(default_factory=list)
    primary_actions: List[str] = Field(default_factory=list)
    api_dependencies: List[str] = Field(default_factory=list)
    data_dependencies: List[str] = Field(default_factory=list)
    states: List[str] = Field(default_factory=list)


class UIUXUserFlowSpec(BaseModel):
    id: str
    name: str
    requirement_ids: List[str] = Field(default_factory=list)
    steps: List[str] = Field(default_factory=list)
    success_criteria: List[str] = Field(default_factory=list)


class UIUXComponentSpec(BaseModel):
    name: str
    role: str = ""
    source_component: str = ""
    requirement_ids: List[str] = Field(default_factory=list)
    children: List[str] = Field(default_factory=list)
    states: List[str] = Field(default_factory=list)


class UIUXFormStateSpec(BaseModel):
    form: str
    fields: List[str] = Field(default_factory=list)
    data_dependencies: List[str] = Field(default_factory=list)
    validation_rules: List[str] = Field(default_factory=list)
    error_states: List[str] = Field(default_factory=list)


class UIUXFrontendHandoff(BaseModel):
    routes: List[str] = Field(default_factory=list)
    api_client_needs: List[str] = Field(default_factory=list)
    data_contracts: List[str] = Field(default_factory=list)
    state_management_notes: List[str] = Field(default_factory=list)
    implementation_notes: List[str] = Field(default_factory=list)


class UIUXArtifact(BaseModel):
    status: str = "draft"
    screens: List[UIUXScreenSpec] = Field(default_factory=list)
    user_flows: List[UIUXUserFlowSpec] = Field(default_factory=list)
    component_tree: List[UIUXComponentSpec] = Field(default_factory=list)
    form_states: List[UIUXFormStateSpec] = Field(default_factory=list)
    empty_states: List[str] = Field(default_factory=list)
    error_states: List[str] = Field(default_factory=list)
    accessibility_requirements: List[str] = Field(default_factory=list)
    frontend_handoff: UIUXFrontendHandoff = Field(default_factory=UIUXFrontendHandoff)


class DomainGateResult(BaseModel):
    status: str = "pass"
    domain: str
    reason: str = ""
    blocking_findings: List[str] = Field(default_factory=list)


class GlobalFESyncResult(BaseModel):
    status: str = "pass"
    reason: str = ""
    shared_components: List[str] = Field(default_factory=list)
    sync_actions: List[str] = Field(default_factory=list)


class GlobalFESyncPlanningOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    status: str = "pass"
    reason: str = ""
    shared_components: List[str] = Field(default_factory=list)
    sync_actions: List[str] = Field(default_factory=list)


class IntegrationQAResult(BaseModel):
    status: str = "pass"
    reason: str = ""
    findings: List[str] = Field(default_factory=list)
    rework_targets: List[str] = Field(default_factory=list)
    runtime_smoke: dict = Field(default_factory=dict)
    fullstack_runtime_verification: dict = Field(default_factory=dict)


class IntegrationQAPlanningOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    status: str = "pass"
    reason: str = ""
    findings: List[str] = Field(default_factory=list)
    rework_targets: List[str] = Field(default_factory=list)
    runtime_smoke: dict = Field(default_factory=dict)
    fullstack_runtime_verification: dict = Field(default_factory=dict)


class BranchPROrchestratorResult(BaseModel):
    status: str = "ready"
    gitflow: str = "git-flow"
    base_branch: str = "develop"
    resolved_base_ref: str = ""
    feature_branches: List[dict] = Field(default_factory=list)
    branch_execution: List[dict] = Field(default_factory=list)
    pr_plan: List[dict] = Field(default_factory=list)
    pr_drafts: List[dict] = Field(default_factory=list)
    cli: dict = Field(default_factory=dict)
    merge_plan: List[dict] = Field(default_factory=list)
    readiness_checks: List[dict] = Field(default_factory=list)
    merge_ready: bool = False


class EmbeddingResult(BaseModel):
    status: str = "prepared"
    session_id: str = ""
    source_session_id: str = ""
    documents: List[dict] = Field(default_factory=list)
    target_collections: List[str] = Field(default_factory=list)
    persisted_artifacts: List[dict] = Field(default_factory=list)
    errors: List[str] = Field(default_factory=list)


class GeneratedCodeFile(BaseModel):
    path: str
    content: str
    purpose: str = ""


class BackendCodegenOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    language: str = ""
    framework: str = ""
    files: List[GeneratedCodeFile] = Field(default_factory=list)
    test_command: str = ""
    notes: List[str] = Field(default_factory=list)


class BackendCodegenVerificationCheck(BaseModel):
    name: str
    status: str = "skipped"
    command: List[str] = Field(default_factory=list)
    returncode: int | None = None
    stdout_tail: str = ""
    stderr_tail: str = ""
    reason: str = ""


class BackendCodegenVerificationResult(BaseModel):
    status: str = "skipped"
    output_dir: str = ""
    checks: List[BackendCodegenVerificationCheck] = Field(default_factory=list)
    failed_checks: List[str] = Field(default_factory=list)
    skipped_reason: str = ""
    next_actions: List[str] = Field(default_factory=list)
    dependency_install_plan: List[dict] = Field(default_factory=list)
    dependency_install_result: dict = Field(default_factory=dict)


class BackendCodegenRepairOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    summary: str = ""
    files: List[GeneratedCodeFile] = Field(default_factory=list)
    notes: List[str] = Field(default_factory=list)


class FrontendCodegenOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    language: str = ""
    framework: str = ""
    files: List[GeneratedCodeFile] = Field(default_factory=list)
    test_command: str = ""
    notes: List[str] = Field(default_factory=list)
