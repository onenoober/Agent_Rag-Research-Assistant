"""FastAPI application for Agent."""

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from .routes_health import router as health_router
from .routes_chat import router as chat_router


app = FastAPI(
    title="Research Agent API",
    description="API for the Research Agent",
    version="0.1.0"
)

app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

app.include_router(health_router)
app.include_router(chat_router)


@app.get("/")
async def root():
    """Root endpoint."""
    return {"message": "Research Agent API", "version": "0.1.0"}
