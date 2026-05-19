from fastapi import APIRouter

from app.services import inbox_monitor

router = APIRouter(prefix="/api/v1/inbox", tags=["inbox"])


@router.post("/check-now")
async def check_now():
    """Manually trigger inbox check. Returns counts of new replies found and matched."""
    return await inbox_monitor.check_inbox()
