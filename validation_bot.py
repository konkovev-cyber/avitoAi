#!/usr/bin/env python3
"""
Validation Bot — сбор лидов и обратной связи для Market Intelligence.
Не зависит от основного бота. Работает параллельно.

Запуск:
  cd /opt/market_agent && .venv/bin/python3 validation_bot.py
"""

from __future__ import annotations

from config import settings
import json
import logging
import sqlite3
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters,
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
)
log = logging.getLogger("validation_bot")

# Telegram config
TOKEN = settings.telegram_bot_token
ADMIN_ID = settings.admin_telegram_id or 977966870

# Conversation states
(NICHE, CITY, ROLE, CONTACT, FEEDBACK_COMMENT) = range(5)

# Database
DB_PATH = Path(__file__).parent / "data" / "market_agent.db"

def _init_db():
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_leads (
            id INTEGER PRIMARY KEY,
            telegram_id INTEGER,
            username TEXT,
            niche TEXT,
            city TEXT,
            role TEXT,
            contact_method TEXT,
            status TEXT DEFAULT 'new',
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.execute("""
        CREATE TABLE IF NOT EXISTS customer_feedback (
            id INTEGER PRIMARY KEY,
            lead_id INTEGER,
            rating INTEGER,
            comment TEXT,
            wants_more INTEGER DEFAULT 0,
            created_at TEXT DEFAULT (datetime('now'))
        )
    """)
    conn.commit()
    conn.close()
    log.info("Database initialized")

# ── Menus ─────────────────────────────────────────────────────────────────

NICHES = {
    "phones": "🔧 Ремонт телефонов",
    "appliances": "🛠 Ремонт техники",
    "auto": "🚗 Автосервис",
    "construction": "🏠 Строительство",
    "other": "📦 Другое",
}

ROLES = {
    "owner": "Владелец бизнеса",
    "marketing": "Маркетинг / Продажи",
    "other": "Другое",
}

def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(list(rows))

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

# ── Start ─────────────────────────────────────────────────────────────────

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.message.reply_text(
        "👋 Привет!\n\n"
        "Я тестирую систему анализа рынка для бизнеса.\n\n"
        "Она помогает увидеть:\n"
        "• кто реально работает в нише;\n"
        "• какие компании появляются и растут;\n"
        "• где есть возможности для привлечения клиентов.\n\n"
        "Сейчас я собираю обратную связь от предпринимателей.\n\n"
        "Можно получить пример анализа своей ниши бесплатно "
        "и сказать, насколько он полезен.",
        reply_markup=_kb(
            [_btn("📊 Получить пример анализа", "get_analysis")],
            [_btn("💬 Оставить обратную связь", "leave_feedback")],
        ),
    )

# ── Flow: Get Analysis ────────────────────────────────────────────────────

async def get_analysis(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Выберите вашу сферу:",
        reply_markup=_kb(
            *[[_btn(v, f"niche_{k}")] for k, v in NICHES.items()],
            [_btn("◀ Назад", "back_start")],
        ),
    )
    return NICHE

async def niche_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data
    niche_key = data.replace("niche_", "")
    context.user_data["niche"] = NICHES.get(niche_key, niche_key)

    await update.callback_query.edit_message_text(
        f"Сфера: <b>{context.user_data['niche']}</b>\n\n"
        "Ваш город?",
        parse_mode="HTML",
        reply_markup=_kb([_btn("◀ Назад", "back_niche")]),
    )
    return CITY

async def city_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["city"] = update.message.text.strip()
    await update.message.reply_text(
        "Вы владелец бизнеса или ищете клиентов для компаний?",
        reply_markup=_kb(
            *[[_btn(v, f"role_{k}")] for k, v in ROLES.items()],
            [_btn("◀ Назад", "back_start")],
        ),
    )
    return ROLE

async def role_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data
    role_key = data.replace("role_", "")
    context.user_data["role"] = ROLES.get(role_key, role_key)

    await update.callback_query.edit_message_text(
        "Как удобнее отправить результат?\n"
        "Напишите ваш @username или email:",
        reply_markup=_kb([_btn("◀ Назад", "back_role")]),
    )
    return CONTACT

async def contact_received(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["contact"] = update.message.text.strip()

    # Save lead to DB
    user = update.effective_user
    _save_lead(user.id, user.username, context.user_data)

    await update.message.reply_text(
        "✅ Спасибо!\n\n"
        "Подготовлю небольшой пример анализа рынка.\n\n"
        "В нём будет:\n"
        "✅ карта игроков\n"
        "✅ основные конкуренты\n"
        "✅ найденные возможности\n"
        "✅ изменения на рынке\n\n"
        "После просмотра можно будет сказать, "
        "что полезно улучшить.",
        reply_markup=_kb([_btn("🏠 В начало", "back_start")]),
    )

    # Notify admin
    await _notify_admin(context, update.effective_user, context.user_data)

    context.user_data.clear()
    return ConversationHandler.END

# ── Flow: Feedback ─────────────────────────────────────────────────────────

async def leave_feedback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.callback_query.edit_message_text(
        "Оцените от 1 до 5, насколько полезным был анализ?",
        reply_markup=_kb(
            [InlineKeyboardButton(str(i), callback_data=f"fb_{i}") for i in range(1, 6)],
            [_btn("◀ Назад", "back_start")],
        ),
    )
    return FEEDBACK_COMMENT

async def feedback_rating(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    rating = update.callback_query.data.replace("fb_", "")
    context.user_data["rating"] = rating
    await update.callback_query.edit_message_text(
        f"Оценка: {rating}/5\n\n"
        "Что было бы полезнее? Напишите пару слов.",
        reply_markup=_kb([_btn("◀ Пропустить", "fb_skip")]),
    )
    return FEEDBACK_COMMENT

async def feedback_comment(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["comment"] = update.message.text.strip()
    _save_feedback(update.effective_user.id, context.user_data)
    await update.message.reply_text(
        "✅ Спасибо за обратную связь!",
        reply_markup=_kb([_btn("🏠 В начало", "back_start")]),
    )
    context.user_data.clear()
    return ConversationHandler.END

async def feedback_skip(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data["comment"] = ""
    _save_feedback(update.effective_user.id, context.user_data)
    await update.callback_query.edit_message_text(
        "✅ Спасибо за обратную связь!",
        reply_markup=_kb([_btn("🏠 В начало", "back_start")]),
    )
    context.user_data.clear()
    return ConversationHandler.END

# ── Back buttons ───────────────────────────────────────────────────────────

async def back_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.clear()
    await update.callback_query.edit_message_text(
        "👋 Привет!\n\nЯ тестирую систему анализа рынка для бизнеса.\n\n"
        "Можно получить пример анализа своей ниши бесплатно "
        "и сказать, насколько он полезен.",
        reply_markup=_kb(
            [_btn("📊 Получить пример анализа", "get_analysis")],
            [_btn("💬 Оставить обратную связь", "leave_feedback")],
        ),
    )

async def back_niche(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.clear()
    return await NICHE

# ── Database ──────────────────────────────────────────────────────────────

def _save_lead(telegram_id: int, username: Optional[str], data: dict):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO customer_leads (telegram_id, username, niche, city, role) VALUES (?, ?, ?, ?, ?)",
        (telegram_id, username, data.get("niche", ""), data.get("city", ""), data.get("role", "")),
    )
    conn.commit()
    conn.close()
    log.info("Lead saved: %s %s", data.get("niche"), data.get("city"))

def _save_feedback(telegram_id: int, data: dict):
    conn = sqlite3.connect(str(DB_PATH))
    conn.execute(
        "INSERT INTO customer_feedback (lead_id, rating, comment) VALUES (?, ?, ?)",
        (telegram_id, int(data.get("rating", 0)), data.get("comment", "")),
    )
    conn.commit()
    conn.close()
    log.info("Feedback saved: %s/5", data.get("rating"))

async def _notify_admin(context: ContextTypes.DEFAULT_TYPE, user, data: dict):
    """Отправить уведомление админу о новом лиде."""
    if not ADMIN_ID:
        return
    msg = (
        f"📩 <b>Новый запрос на анализ</b>\n\n"
        f"Ниша: {data.get('niche', '?')}\n"
        f"Город: {data.get('city', '?')}\n"
        f"Роль: {data.get('role', '?')}\n"
        f"Контакт: @{user.username or data.get('contact', '?')}\n"
        f"ID: {user.id}"
    )
    try:
        await context.application.bot.send_message(
            chat_id=ADMIN_ID, text=msg, parse_mode="HTML",
        )
    except Exception as e:
        log.warning("Admin notify failed: %s", e)

# ── Admin command ─────────────────────────────────────────────────────────

async def cmd_leads(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Показать список лидов (только для админа)."""
    if update.effective_user.id != ADMIN_ID:
        await update.message.reply_text("Нет доступа.")
        return
    conn = sqlite3.connect(str(DB_PATH))
    rows = conn.execute(
        "SELECT id, niche, city, role, status, created_at FROM customer_leads "
        "ORDER BY created_at DESC LIMIT 10"
    ).fetchall()
    conn.close()

    if not rows:
        await update.message.reply_text("Лидов пока нет.")
        return

    lines = ["<b>📊 Последние лиды:</b>\n"]
    for r in rows:
        lines.append(
            f"#{r[0]} {r[1]} | {r[2]} | {r[3]} | {r[4]} | {r[5]}"
        )
    await update.message.reply_text("\n".join(lines), parse_mode="HTML")

# ── Build app ─────────────────────────────────────────────────────────────

def build_app() -> Application:
    _init_db()

    http_kwargs = {}
    if settings.proxy_url:
        from telegram.request import HTTPXRequest
        http_kwargs["proxy"] = settings.proxy_url
        request = HTTPXRequest(**http_kwargs)
        app = Application.builder().token(TOKEN).request(request).build()
    else:
        app = Application.builder().token(TOKEN).build()

    conv = ConversationHandler(
        entry_points=[
            CallbackQueryHandler(get_analysis, pattern="^get_analysis$"),
            CallbackQueryHandler(leave_feedback, pattern="^leave_feedback$"),
        ],
        states={
            NICHE: [CallbackQueryHandler(niche_chosen, pattern="^niche_")],
            CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, city_received)],
            ROLE: [CallbackQueryHandler(role_chosen, pattern="^role_")],
            CONTACT: [MessageHandler(filters.TEXT & ~filters.COMMAND, contact_received)],
            FEEDBACK_COMMENT: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, feedback_comment),
                CallbackQueryHandler(feedback_rating, pattern="^fb_"),
                CallbackQueryHandler(feedback_skip, pattern="^fb_skip$"),
            ],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(back_start, pattern="^back_start$"),
        ],
        allow_reentry=True,
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(conv)
    app.add_handler(CommandHandler("leads", cmd_leads))

    return app

# ── Main ──────────────────────────────────────────────────────────────────

def main():
    log.info("Validation Bot starting...")
    app = build_app()
    app.run_polling()

if __name__ == "__main__":
    main()
