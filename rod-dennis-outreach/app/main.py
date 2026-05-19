import os
from contextlib import asynccontextmanager

from apscheduler.schedulers.asyncio import AsyncIOScheduler
from apscheduler.triggers.cron import CronTrigger
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import RedirectResponse
from fastapi.staticfiles import StaticFiles

from app.routers import dashboard, prospects
from app.routers import discovery as discovery_router
from app.routers import social as social_router
from app.routers import chat as chat_router
from app.services import csv_service, discovery_agent, social_generator, tracking_service

scheduler = AsyncIOScheduler()


async def _weekly_social_job() -> None:
    trigger = "weekly art market observation"
    context = "classical realism and African American figurative art market"

    result = await social_generator.generate_social_content(trigger, context)
    for platform, content in result.items():
        csv_service.append_social_draft(
            {"platform": platform, "content": content, "trigger_event": trigger, "status": "pending"}
        )

    saved = list(result.keys())
    print(f"[weekly_social] saved={saved or 'none'}")


@asynccontextmanager
async def lifespan(app: FastAPI):
    os.makedirs("data", exist_ok=True)
    csv_service.ensure_csv_exists()
    csv_service.ensure_drafts_csv_exists()
    csv_service.ensure_inbound_csv_exists()
    csv_service.ensure_discovery_log_exists()
    csv_service.ensure_social_drafts_exists()

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

if os.path.isdir("dashboard-ui"):
    app.mount("/dashboard", StaticFiles(directory="dashboard-ui", html=True), name="dashboard")


@app.get("/")
async def root():
    return RedirectResponse(url="/dashboard")


@app.get("/health")
def health():
    return {"status": "ok", "project": "rod-dennis-outreach"}
