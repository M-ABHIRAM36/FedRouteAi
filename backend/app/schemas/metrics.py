from pydantic import BaseModel, Field

class DashboardMetrics(BaseModel):
    active_regions: int = Field(..., description="Number of unique active regions", examples=[8])
    total_events: int = Field(..., description="Total active traffic events", examples=[4])
    total_segments: int = Field(..., description="Total monitored road segments", examples=[125])
    system_health: str = Field(..., description="Current system health status", examples=["Optimal"])
