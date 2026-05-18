from fastapi import APIRouter

from app.services import csv_service, discovery_agent

router = APIRouter(prefix="/api/v1/discovery", tags=["discovery"])


@router.post("/run-now")
async def run_now():
    return await discovery_agent.run_discovery()


@router.get("/log")
def get_log():
    return csv_service.get_discovery_log()
