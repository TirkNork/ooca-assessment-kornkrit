"""Internal service health per region (may differ from the public status page)."""

from enum import StrEnum

from pydantic import AwareDatetime, BaseModel, Field


class HealthState(StrEnum):
    OPERATIONAL = "operational"
    DEGRADED = "degraded"
    OUTAGE = "outage"


class Incident(BaseModel):
    incident_id: str
    started_at: AwareDatetime
    title: str


class RegionStatus(BaseModel):
    region: str
    status: HealthState = Field(description="Actual health from internal monitoring.")
    public_status: HealthState = Field(description="What status.company.com currently shows.")
    active_incidents: list[Incident] = Field(default_factory=list)
