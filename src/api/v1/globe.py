from fastapi import APIRouter, Path, Query

from src.core.dependencies import DbSession, CurrentActiveUser
from src.services.globe import GlobeService
from src.schemas.globe import GlobeData, IPIntelligence

router = APIRouter(prefix="/globe", tags=["Globe"])


@router.get("/attacks", response_model=GlobeData)
async def get_globe_attacks(
    db: DbSession,
    current_user: CurrentActiveUser,
    hours: int = Query(default=24, ge=1, le=168),
):
    service = GlobeService(db)
    return await service.get_globe_data(hours=hours)


@router.get("/ip/{ip}", response_model=IPIntelligence)
async def get_ip_intelligence(
    db: DbSession,
    current_user: CurrentActiveUser,
    ip: str = Path(..., description="IP address to look up"),
):
    service = GlobeService(db)
    return await service.get_ip_intelligence(ip=ip)
