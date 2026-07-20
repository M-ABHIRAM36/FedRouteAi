from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.models.segment import Segment
from app.models.event import Event
from app.schemas.metrics import DashboardMetrics

router = APIRouter(prefix="/metrics", tags=["metrics"])

@router.get("", response_model=DashboardMetrics)
def get_dashboard_metrics(db: Session = Depends(get_db)):
    """
    Get aggregated telemetry metrics for the dashboard.
    """
    try:
        # Compute real metrics from database
        total_segments = db.query(Segment).count()
        total_events = db.query(Event).count()
        
        # Count unique regions
        active_regions = db.query(Segment.region_id).distinct().count()
        
        system_health = "Optimal" if total_segments > 0 else "Offline"
        
        return DashboardMetrics(
            active_regions=active_regions,
            total_events=total_events,
            total_segments=total_segments,
            system_health=system_health
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))
