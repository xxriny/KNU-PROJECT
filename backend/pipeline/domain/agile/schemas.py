"""Agile Layer Pydantic schemas — verifier & impact analyzer."""
from __future__ import annotations

from enum import Enum
from typing import Optional
from pydantic import BaseModel, Field


class Severity(str, Enum):
    critical = "critical"
    major = "major"
    minor = "minor"


class ViolationItem(BaseModel):
    rule_id: str
    rule_name: str
    severity: Severity
    description: str
    location: str = ""
    suggestion: str = ""


class VerifierResult(BaseModel):
    coherence_score: float = Field(ge=0.0, le=1.0)
    passed: bool
    violations: list[ViolationItem] = []
    summary: str = ""


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
