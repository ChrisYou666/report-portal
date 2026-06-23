from contextlib import asynccontextmanager
from pathlib import Path

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.staticfiles import StaticFiles

from app.api.admin import router as admin_router
from app.api.auth import router as auth_router
from app.api.batches import router as batches_router
from app.api.entry import router as entry_router
from app.api.master_data import router as master_router
from app.api.agri_index import router as agri_index_router
from app.api.index_data import router as index_data_router
from app.api.index_mgmt import router as index_mgmt_router
from app.api.index_notifications import router as index_notifications_router
from app.api.public import router as public_router
from app.api.query import router as query_router
from app.api.reports import router as reports_router
from app.api.scheduled_sync import router as scheduled_sync_router
from app.api.teams_bot import router as teams_bot_router
from app.api.uploads import router as uploads_router
from app.api.users import router as users_router
from app.core.config import settings
from app.db import init_db
from app.services.scheduler import start_scheduler, stop_scheduler


@asynccontextmanager
async def lifespan(app: FastAPI):
    init_db()
    scheduler = start_scheduler()
    yield
    stop_scheduler()


app = FastAPI(title=settings.app_name, lifespan=lifespan)

app.add_middleware(
    CORSMiddleware,
    allow_origins=settings.allowed_origin_list,
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health() -> dict[str, str]:
    return {"status": "ok"}


app.include_router(admin_router, prefix="/api")
app.include_router(auth_router, prefix="/api")
app.include_router(users_router, prefix="/api")
app.include_router(index_mgmt_router, prefix="/api")
app.include_router(index_data_router, prefix="/api")
app.include_router(index_notifications_router, prefix="/api")
app.include_router(agri_index_router, prefix="/api")
app.include_router(public_router, prefix="/api")
app.include_router(uploads_router, prefix="/api")
app.include_router(batches_router, prefix="/api")
app.include_router(entry_router, prefix="/api")
app.include_router(master_router, prefix="/api")
app.include_router(query_router, prefix="/api")
app.include_router(reports_router, prefix="/api")
app.include_router(scheduled_sync_router, prefix="/api")
app.include_router(teams_bot_router, prefix="/api")

Path(settings.storage_dir).mkdir(parents=True, exist_ok=True)
app.mount("/storage", StaticFiles(directory=settings.storage_dir), name="storage")
