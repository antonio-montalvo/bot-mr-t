from dotenv import load_dotenv

load_dotenv()

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from app.api.routers.auth_router import router as auth_router
from app.api.routers.broker_router import router as broker_router
from app.api.routers.strategy_router import router as strategy_router
from app.api.routers.bot_router import router as bot_router
from app.api.routers.metrics_router import router as metrics_router
from app.api.routers.dashboard_router import router as dashboard_router
from app.api.deps import get_db
from app.logs import setup_logger
from app.sync import SyncScheduler

setup_logger()

app = FastAPI(
    title="Bot Mr T - API",
    description="API REST para la administración del bot de trading",
    version="1.0.0",
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(auth_router)
app.include_router(broker_router)
app.include_router(strategy_router)
app.include_router(bot_router)
app.include_router(metrics_router)
app.include_router(dashboard_router)

_sync_scheduler: SyncScheduler = None


@app.on_event("startup")
def startup():
    global _sync_scheduler
    db = get_db()
    _sync_scheduler = SyncScheduler(db)
    _sync_scheduler.start()


@app.on_event("shutdown")
def shutdown():
    global _sync_scheduler
    if _sync_scheduler:
        _sync_scheduler.stop()


@app.get("/health", tags=["Health"])
def health():
    return {"status": "ok"}
