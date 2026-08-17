"""Scenario-control contracts; ground truth is metadata, never model input."""
from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field, model_validator

from app.core.constants import EventType


class ScenarioItemIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    type: EventType
    segment_id: str = Field(min_length=1, max_length=30)
    severity: float = Field(default=0.7, gt=0, le=1)
    duration_seconds: int = Field(default=300, gt=0, le=86400)
    start_time: datetime | None = None

    @model_validator(mode="after")
    def reject_normal(self):
        if self.type is EventType.NORMAL:
            raise ValueError("normal is a baseline state, not a scenario event")
        return self


class ScenarioCreateIn(BaseModel):
    model_config = ConfigDict(extra="forbid")

    source_id: str = Field(min_length=1, max_length=60)
    run_id: str = Field(min_length=1, max_length=80)
    scenarios: list[ScenarioItemIn] = Field(min_length=1, max_length=20)


class ScenarioOut(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    event_id: str
    source_id: str
    run_id: str
    event_type: str
    primary_segment_id: str
    region_id: str
    affected_segment_ids: list[str]
    severity: float
    start_time: datetime
    end_time: datetime
    ground_truth_label: str
    status: str
