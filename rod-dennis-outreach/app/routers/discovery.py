from fastapi import APIRouter

from app.database import get_db
from app.services import discovery_agent

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


@router.post("/run-now")
async def run_now():
    return await discovery_agent.run_discovery()


@router.get("/log")
def get_log():
    return (
        get_db().table("discovery_log")
        .select("*")
        .order("run_at", desc=True)
        .limit(20)
        .execute()
        .data or []
    )
