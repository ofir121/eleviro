from fastapi import FastAPI, Request
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from dotenv import load_dotenv
import os
from pathlib import Path

# Load environment variables
load_dotenv()

app = FastAPI(title="Job Application AI Platform")

# Get base directory for absolute paths
BASE_DIR = Path(__file__).resolve().parent

# Mount static files
app.mount("/static", StaticFiles(directory=str(BASE_DIR / "app/static")), name="static")

# Templates
templates = Jinja2Templates(directory=str(BASE_DIR / "app/templates"))

@app.get("/health")
async def health_check():
    return {"status": "ok"}

@app.get("/", response_class=HTMLResponse)
async def read_root(request: Request):
    return templates.TemplateResponse("index.html", {"request": request})

@app.get("/documentation", response_class=HTMLResponse)
async def read_docs(request: Request):
    return templates.TemplateResponse("documentation.html", {"request": request})

# Import and include routers
from app.routers import job_router
app.include_router(job_router.router)
