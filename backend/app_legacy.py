from fastapi import FastAPI

from backend.db import init_db
from backend.health import router as health_router
from backend.catalog import router as catalog_router
from backend.stacks import router as stacks_router
from backend.jobs import router as jobs_router
from backend.agents import router as agents_router
from backend.outputs import router as outputs_router

app = FastAPI(title="GenLib Backend", version="1.0.0")

@app.on_event("startup")
def startup():
    init_db()

app.include_router(health_router)
app.include_router(catalog_router, prefix="/catalog")
app.include_router(stacks_router, prefix="/stacks")
app.include_router(jobs_router, prefix="/jobs")
app.include_router(agents_router, prefix="/agent")
app.include_router(outputs_router, prefix="/outputs")
