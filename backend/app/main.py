from fastapi import FastAPI
from app.api import jobs, utilities
from app.db import init_db

app = FastAPI(title="OHA Lifecycle API", version="0.1.0")
app.include_router(jobs.router)
app.include_router(utilities.router)


@app.on_event("startup")
def _startup():
    init_db()


@app.get("/health")
async def health():
    return {"ok": True}
