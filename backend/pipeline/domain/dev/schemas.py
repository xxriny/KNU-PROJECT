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


class IntegrationQAPlanningOutput(BaseModel):
    thinking: str = Field(default="", description="Korean keywords only")
    status: str = "pass"
    reason: str = ""
    findings: List[str] = Field(default_factory=list)
    rework_targets: List[str] = Field(default_factory=list)


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
