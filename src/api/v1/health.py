from fastapi import APIRouter

router = APIRouter(tags=["Health"])


@router.get("/health")
async def health_check():
    return {"status": "healthy", "service": "api_cyber"}


@router.get("/health/ready")
async def readiness_check():
    return {"status": "ready"}
