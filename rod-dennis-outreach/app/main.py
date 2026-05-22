import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.database import get_db
from app.routers import dashboard, prospects
from app.routers import discovery as discovery_router
from app.routers import social as social_router
from app.routers import chat as chat_router
from app.routers import inbox as inbox_router
from app.services import discovery_agent, social_generator, tracking_service, inbox_monitor

scheduler = AsyncIOScheduler()


async def _weekly_social_job() -> None:
    trigger = "weekly art market observation"
    context = "classical realism and African American figurative art market"

    result = await social_generator.generate_social_content(trigger, context)
    db = get_db()
    for platform, content in result.items():
        db.table("social_drafts").insert({
            "platform": platform,
            "content": content,
            "trigger_event": trigger,
            "status": "pending",
        }).execute()

    print(f"[weekly_social] saved={list(result.keys()) or 'none'}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    scheduler.add_job(
        discovery_agent.run_discovery,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_discovery",
        replace_existing=True,
    )
    scheduler.add_job(
        _weekly_social_job,
        trigger=CronTrigger(day_of_week="wed", hour=9, minute=0),
        id="weekly_social",
        replace_existing=True,
    )
    scheduler.add_job(
        tracking_service.send_weekly_digest,
        trigger=CronTrigger(day_of_week="mon", hour=8, minute=0),
        id="weekly_digest",
        replace_existing=True,
    )
    scheduler.add_job(
        tracking_service.send_priority_nudge,
        trigger=CronTrigger(hour=9, minute=0),
        id="daily_priority_nudge",
        replace_existing=True,
    )
    scheduler.add_job(
        inbox_monitor.check_inbox,
        trigger="interval",
        minutes=30,
        id="inbox_monitor",
        replace_existing=True,
    )
    scheduler.start()

    yield

    scheduler.shutdown()


app = FastAPI(lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(prospects.router)
app.include_router(dashboard.router)
app.include_router(discovery_router.router)
app.include_router(social_router.router)
app.include_router(chat_router.router)
app.include_router(inbox_router.router)

if os.path.isdir("dashboard-ui"):
    app.mount("/dashboard", StaticFiles(directory="dashboard-ui", html=True), name="dashboard")


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health():
    return {"status": "ok", "project": "rod-dennis-outreach"}
