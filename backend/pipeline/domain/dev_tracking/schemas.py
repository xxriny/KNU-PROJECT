from __future__ import annotations

from pydantic import BaseModel, Field


class DevImplementationProfile(BaseModel):
    detected_apis: list[dict[str, object]] = Field(default_factory=list)
    detected_components: list[dict[str, object]] = Field(default_factory=list)
    file_role_map: dict[str, str] = Field(default_factory=dict)
    implementation_summary: str = ""


class DevImplementationProfileResponse(BaseModel):
    implementation_profile: DevImplementationProfile


class DevGapItem(BaseModel):
    gap_id: str
    severity: str = Field(pattern="^(HIGH|MED|LOW)$")
    type: str
    spec_target: str | None = None
    implementation_target: str | None = None
    description: str
    spec_outdated_related: bool = False
    preliminary: bool = False


class DevGapReportResponse(BaseModel):
    gaps: list[DevGapItem] = Field(default_factory=list)


class DevGapIntentItem(BaseModel):
    gap_id: str
    intent: str = Field(pattern="^(INTENTIONAL|UNINTENTIONAL|UNCERTAIN)$")
    confidence: float = Field(ge=0.0, le=1.0)
    reason: str
    recommended_action: str = Field(
        pattern="^(APPROVE_AS_INTENTIONAL|REQUEST_FIX|PM_REVIEW)$"
    )


class DevGapIntentResponse(BaseModel):
    classifications: list[DevGapIntentItem]
