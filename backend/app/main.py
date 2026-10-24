import logging
from contextlib import asynccontextmanager
from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.core.config import settings
from app.db import init_db
from app.api import router as api_router

logging.basicConfig(
    level=logging.INFO if settings.DEBUG else logging.WARNING,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s"
)
logger = logging.getLogger("autonomous_agent")

@asynccontextmanager
async def lifespan(app: FastAPI):
    logger.info("Initializing Autonomous Engineering Agent database...")
    init_db()
    logger.info("Database initialized successfully.")
    yield
    logger.info("Shutting down Autonomous Engineering Agent.")

app = FastAPI(
    title=settings.APP_NAME,
    version=settings.APP_VERSION,
    description="An agentic AI software-engineering system that autonomously analyzes repositories, diagnoses issues, modifies code, executes tests inside isolated sandboxes, reviews changes, and prepares GitHub Pull Requests.",
    lifespan=lifespan,
    docs_url="/docs",
    redoc_url="/redoc"
)

# CORS setup for Web Dashboard
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(api_router, prefix=settings.API_V1_PREFIX)

@app.get("/")
def root():
    return {
        "service": settings.APP_NAME,
        "version": settings.APP_VERSION,
        "status": "operational",
        "docs": "/docs",
        "api_v1": settings.API_V1_PREFIX
    }

if __name__ == "__main__":
    import uvicorn
    uvicorn.run("app.main:app", host=settings.HOST, port=settings.PORT, reload=settings.DEBUG)
