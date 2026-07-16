"""FastAPI web dashboard for Market Agent."""

from __future__ import annotations

from fastapi import FastAPI, Request
from fastapi.responses import HTMLResponse
from fastapi.templating import Jinja2Templates
from pathlib import Path

from database.db import Database
from config import settings

app = FastAPI(title="Market Agent Dashboard")
db = Database()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    stats = db.get_stats()
    return templates.TemplateResponse(
        "index.html",
        {"request": request, "stats": stats, "config": settings},
    )


@app.get("/api/stats")
async def api_stats():
    return db.get_stats()


@app.get("/api/searches")
async def api_searches():
    return {"searches": db.get_active_searches()}


@app.get("/api/listings")
async def api_listings(limit: int = 20):
    conn = db.connect()
    rows = conn.execute(
        "SELECT * FROM listings ORDER BY parsed_at DESC LIMIT ?",
        (limit,),
    ).fetchall()
    return {"listings": [dict(r) for r in rows]}
