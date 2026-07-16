"""FastAPI web dashboard for Market Agent."""

from __future__ import annotations

import json
from pathlib import Path
from typing import Optional

from fastapi import FastAPI, Request, Form
from fastapi.responses import HTMLResponse, RedirectResponse
from fastapi.templating import Jinja2Templates

from database.db import Database
from config import settings

app = FastAPI(title="Market Agent Dashboard")
db = Database()
templates = Jinja2Templates(directory=Path(__file__).parent / "templates")


@app.get("/", response_class=HTMLResponse)
async def index(request: Request):
    """SaaS Landing Page."""
    return templates.TemplateResponse(
        "landing.html",
        {"request": request, "config": settings},
    )


@app.get("/dashboard/{telegram_id}", response_class=HTMLResponse)
async def user_dashboard(request: Request, telegram_id: int):
    """Personal multi-user area."""
    user = db.get_user_by_telegram(telegram_id)
    if not user:
        return HTMLResponse(
            "<html><body><h2>Пользователь не найден</h2><p>Пожалуйста, зарегистрируйтесь сначала в Telegram-боте.</p><a href='/'>Назад</a></body></html>",
            status_code=404,
        )

    user_id = user["id"]
    searches = db.get_user_searches(user_id)
    opportunities = db.get_user_opportunities(user_id, limit=50)

    # Calculate total savings across user's opportunities
    total_savings = 0.0
    for opp in opportunities:
        if opp.get("median_price") and opp.get("best_price"):
            diff = opp["median_price"] - opp["best_price"]
            if diff > 0:
                total_savings += diff

    # Fetch alerts count
    recent_alerts = db.get_recent_alerts(user_id, limit=200)
    alerts_count = len(recent_alerts)

    # Fetch latest radar snapshots
    radars = db.get_latest_radar(user_id, limit=10)

    return templates.TemplateResponse(
        "dashboard.html",
        {
            "request": request,
            "user": user,
            "searches": searches,
            "opportunities": opportunities,
            "alerts_count": alerts_count,
            "total_savings": total_savings,
            "radars": radars,
            "json_loads": json.loads,
        },
    )


@app.get("/admin", response_class=HTMLResponse)
async def admin_panel(request: Request):
    """Admin statistics & User management."""
    stats = db.get_admin_stats()
    users = db.get_all_users(limit=100)

    return templates.TemplateResponse(
        "admin.html",
        {
            "request": request,
            "stats": stats,
            "users": users,
        },
    )


@app.get("/admin/ban")
async def admin_ban(telegram_id: int, ban: int):
    """Ban or unban user."""
    db.ban_user(telegram_id, banned=(ban == 1))
    return RedirectResponse("/admin", status_code=303)


@app.post("/admin/update_plan")
async def admin_update_plan(telegram_id: int = Form(...), plan: str = Form(...)):
    """Update user SaaS plan (free, pro, unlimited)."""
    db.set_plan(telegram_id, plan=plan)
    return RedirectResponse("/admin", status_code=303)


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
