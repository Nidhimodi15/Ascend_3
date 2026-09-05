import os
from dotenv import load_dotenv
from fastapi import FastAPI
from fastapi.staticfiles import StaticFiles
from fastapi.responses import FileResponse
from fastapi.middleware.cors import CORSMiddleware

# Load environment variables from .env file
load_dotenv()

from app.api.routes import router

app = FastAPI(
    title="KillPoint",
    description="Bounded Crash-Point Recovery Verification Engine with Production-Inspired Security Layer",
    version="1.1.0",
)

# CORS — allow dashboard to call API from same origin
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_methods=["*"],
    allow_headers=["*"],
)

# Register API routes
app.include_router(router, prefix="/api")

# Serve static frontend files
app.mount("/static", StaticFiles(directory="static"), name="static")


@app.get("/", include_in_schema=False)
async def serve_index():
    """Serve the main dashboard page."""
    return FileResponse("static/index.html")
