"""Agile Layer Pydantic schemas — impact analyzer, task generator & distributor."""
from __future__ import annotations

from typing import Optional, List, Dict
from pydantic import BaseModel, Field, ConfigDict


class ImpactedComponent(BaseModel):
    name: str
    impact_type: str
    description: str
    affected_apis: list[str] = []
    affected_tables: list[str] = []


class ImpactResult(BaseModel):
    change_description: str
    impacted_components: list[ImpactedComponent] = []
    impacted_apis: list[str] = []
    impacted_tables: list[str] = []
    risk_level: str = "medium"
    migration_notes: str = ""
    summary: str = ""


# ── Task Generator ────────────────────────────────────────────

class GeneratedTask(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    task_type: str = Field(alias="tt", description="feature|bugfix|test|infra|doc_sync")
    title: str = Field(alias="tl")
    description: str = Field(alias="ds")
    area: str = Field(alias="ar", description="backend|frontend|devops|fullstack")
    priority: str = Field(alias="pr", description="high|medium|low")
    effort: str = Field(alias="ef", description="S|M|L|XL")
    feature_ref: str = Field(alias="fr", default="", description="RTM FEAT_ID")


class TaskUpdateSuggestion(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    task_id: str = Field(alias="id")
    title: Optional[str] = Field(alias="tl", default=None)
    description: Optional[str] = Field(alias="ds", default=None)
    area: Optional[str] = Field(alias="ar", default=None)
    effort: Optional[str] = Field(alias="ef", default=None)
    task_type: Optional[str] = Field(alias="tt", default=None)
    reason: str = Field(alias="rs", default="")


class TaskGeneratorOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="")
    tasks: List[GeneratedTask] = Field(alias="tk")
    updates: List[TaskUpdateSuggestion] = Field(alias="up", default_factory=list)
    summary: str = Field(alias="sm", default="")


# ── Task Distributor ──────────────────────────────────────────

class TaskAssignment(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    task_id: str = Field(alias="ti")
    assignee_name: str = Field(alias="an")
    reason: str = Field(alias="rs", default="")


class TaskDistributorOutput(BaseModel):
    model_config = ConfigDict(populate_by_name=True)
    thinking: str = Field(alias="th", default="")
    assignments: List[TaskAssignment] = Field(alias="as_")
    workload_summary: Dict[str, int] = Field(alias="ws", default_factory=dict)
    balancing_note: str = Field(alias="bn", default="")
