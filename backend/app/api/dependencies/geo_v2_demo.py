from fastapi import Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.services.geo_v2.demo_runtime import GeoV2DemoService, build_geo_v2_demo_service


def get_geo_v2_demo_service(db: Session = Depends(get_db)) -> GeoV2DemoService:
    return build_geo_v2_demo_service(db)
