"""Market Agent Bot v3 — SaaS Multi-User.

Всё настраивается через бота. .env нужен только для MA_TELEGRAM_BOT_TOKEN и MA_ADMIN_TELEGRAM_ID.

Разделы:
  /start   → онбординг (настройка города, AI, источников)
  Главное меню → Мои поиски / Радар / Находки / Настройки
  Настройки → Город | Источники | AI | Уведомления | Режим охотника | Пороги
  /admin   → Панель администратора (только для admin_telegram_id)
"""

from __future__ import annotations

import asyncio
import logging
import os
from typing import Optional

from telegram import (
    Update, InlineKeyboardButton, InlineKeyboardMarkup,
    ReplyKeyboardRemove,
)
from telegram.ext import (
    Application, CallbackQueryHandler, CommandHandler,
    ContextTypes, ConversationHandler, MessageHandler, filters,
)

from config import settings
from database.db import Database

log = logging.getLogger("market_agent.bot")

DB = Database()

# ── ConversationHandler states ─────────────────────────────────────────────────
(
    ST_ONBOARD_CITY,
    ST_ONBOARD_AI_CHOOSE,
    ST_ONBOARD_AI_MODEL,
    ST_ONBOARD_AI_KEY,
    ST_SEARCH_TEXT,
    ST_SEARCH_CITY,
    ST_SEARCH_PRICE_MIN,
    ST_SEARCH_PRICE_MAX,
    ST_SEARCH_CONDITION,
    ST_WAIT_CITY,
    ST_WAIT_AI_KEY,
    ST_WAIT_THRESHOLD,
    ST_WAIT_INTERVAL,
    ST_WAIT_QUIET,
    ST_ADMIN_BROADCAST,
    ST_ADMIN_BAN_ID,
    ST_ADMIN_PLAN_ID,
    ST_ADMIN_PLAN_TYPE,
) = range(18)

# ── Helpers ────────────────────────────────────────────────────────────────────

def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)

def _kb(*rows) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(list(rows))

def _get_user_id(update: Update) -> int:
    """Get Telegram user ID."""
    return update.effective_user.id


def _db_uid(tg_id: int) -> int:
    """Convert Telegram ID to internal database user_id."""
    row = DB.get_user_by_telegram(tg_id)
    return row["id"] if row else 0

async def _edit(update: Update, text: str, markup=None):
    msg = update.callback_query.message if update.callback_query else None
    if msg:
        try:
            await msg.edit_text(text, parse_mode="HTML", reply_markup=markup)
        except Exception:
            await update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=markup)
    else:
        await update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=markup)

async def _send(update: Update, text: str, markup=None):
    await update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=markup)

def _check_ban(func):
    """Decorator: block banned users."""
    async def wrapper(update: Update, context: ContextTypes.DEFAULT_TYPE):
        uid = _get_user_id(update)
        if DB.is_banned(uid):
            if update.callback_query:
                await update.callback_query.answer("❌ Доступ заблокирован", show_alert=True)
            else:
                await _send(update, "❌ Ваш аккаунт заблокирован.")
            return ConversationHandler.END
        return await func(update, context)
    wrapper.__name__ = func.__name__
    return wrapper

def _ensure_user(update: Update):
    """Register/update user in DB on each interaction."""
    u = update.effective_user
    if u:
        DB.upsert_user(u.id, username=u.username, first_name=u.first_name)

# ── Main menu ──────────────────────────────────────────────────────────────────

def _main_menu_kb(user_id: int) -> InlineKeyboardMarkup:
    """user_id = Telegram ID."""
    internal = DB.get_internal_user_id(user_id)
    searches = DB.get_user_searches(internal) if internal else []
    has_any = any(s["active"] for s in searches)
    search_btn = _btn("🔍 Найти товар", "new_search") if not has_any else _btn("🔍 Мои поиски", "menu_searches")
    rows = [
        [search_btn, _btn("📡 Радар рынка", "menu_radar")],
        [_btn("💾 Находки", "menu_finds"), _btn("⚙️ Настройки", "menu_settings")],
    ]
    if settings.is_admin(user_id) or DB.is_admin(user_id):
        rows.append([_btn("👑 Админ-панель", "menu_admin")])
    return InlineKeyboardMarkup(rows)

async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, text: str = ""):
    uid = _get_user_id(update)
    user = DB.get_user_by_telegram(uid)
    s = DB.get_user_settings_by_tg(uid)

    city = s.get("city") or "не задан"
    ai = s.get("ai_provider") or "без AI"
    plan = (user or {}).get("plan", "free")
    plan_badge = {"free": "🆓", "pro": "⭐", "unlimited": "💎"}.get(plan, "🆓")

    greeting = text or (
        f"🏠 <b>Market Agent</b> {plan_badge}\n\n"
        f"🏙 Регион: <code>{city}</code>\n"
        f"🤖 AI: <code>{ai}</code>\n\n"
        "Выберите раздел:"
    )
    await _edit(update, greeting, _main_menu_kb(uid))

# ── /start + Onboarding ────────────────────────────────────────────────────────

@_check_ban
async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_user(update)
    uid = _get_user_id(update)
    user = DB.get_user_by_telegram(uid)

    if user and user.get("onboarded"):
        # Already set up → show main menu
        await _send(update, "👋 С возвращением!", _main_menu_kb(uid))
        return ConversationHandler.END

    # Start onboarding
    name = update.effective_user.first_name or "друг"
    await _send(update,
        f"👋 Привет, <b>{name}</b>!\n\n"
        "Я <b>Market Agent</b> — твой личный AI-охотник за лучшими сделками на Авито и Юле. 🚀\n\n"
        "В отличие от простых парсеров, я ищу не просто объявления, а <b>реально выгодные возможности</b>:\n"
        "✨ <b>Группирую дубликаты</b> — ты не увидишь 100 одинаковых объявлений от перекупщиков.\n"
        "📈 <b>Рассчитываю честную рыночную цену</b> и оцениваю точный размер выгоды.\n"
        "🧠 <b>AI Router</b> — нейросети анализируют описание, выявляют скрытые риски и дают оценку сделки (Score).\n"
        "💧 <b>Определяю ликвидность</b> — оцениваю, насколько быстро товар уходит с рынка.\n\n"
        "Давайте настроим бота за 2 шага.\n\n"
        "🏙 <b>Шаг 1/2: Твой регион</b>\n"
        "Город, край или страна (например: <code>Москва</code>, <code>Краснодарский край</code>, <code>Россия</code>):",
        ReplyKeyboardRemove(),
    )
    return ST_ONBOARD_CITY

async def onboard_got_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = _get_user_id(update)
    city = update.message.text.strip()
    DB.upsert_user_settings_by_tg(tg_id, city=city)
    context.user_data["onboard_city"] = city

    await _send(update,
        f"✅ Регион: <b>{city}</b>\n\n"
        "🤖 <b>Шаг 2/2: AI-анализ</b>\n\n"
        "AI объясняет каждую находку и оценивает риски.\n"
        "<i>Без AI бот работает, но без объяснений.</i>",
        _kb(
            [_btn("🦾 WormSoft AI (рекомендуется)", "ob_ai_wormsoft")],
            [_btn("🤖 OpenAI GPT", "ob_ai_openai")],
            [_btn("✨ Google Gemini", "ob_ai_gemini")],
            [_btn("🔮 Anthropic Claude", "ob_ai_anthropic")],
            [_btn("⏭ Пропустить (без AI)", "ob_ai_skip")],
        ),
    )
    return ST_ONBOARD_AI_CHOOSE

async def onboard_ai_choose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data
    provider = data.replace("ob_ai_", "")

    if provider == "skip":
        return await _finish_onboarding(update, context)

    context.user_data["onboard_ai_provider"] = provider

    if provider == "wormsoft":
        await _edit(update,
            "🦾 <b>WormSoft AI</b>\n\nВыберите модель:",
            _kb(
                [_btn("⚡ Low — быстрая и дешёвая (рекомендуется)", "ob_model_low")],
                [_btn("🎯 Medium — точнее для сложных анализов", "ob_model_medium")],
            ),
        )
        return ST_ONBOARD_AI_MODEL

    info = {
        "openai": ("OpenAI", "platform.openai.com → API Keys"),
        "gemini": ("Google Gemini", "aistudio.google.com → Get API Key"),
        "anthropic": ("Claude", "console.anthropic.com → API Keys"),
    }
    name, where = info.get(provider, (provider, ""))
    await _edit(update,
        f"🔑 <b>API ключ {name}</b>\n\n"
        f"Введите ваш API ключ:\n"
        f"<i>Где получить: {where}</i>",
        _kb([_btn("⏭ Пропустить", "ob_ai_skip_key")]),
    )
    return ST_ONBOARD_AI_KEY

async def onboard_ai_model(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    model_map = {"ob_model_low": "wormsoft/agent/low", "ob_model_medium": "wormsoft/agent/medium"}
    model = model_map.get(update.callback_query.data, "wormsoft/agent/low")
    context.user_data["onboard_ai_model"] = model

    await _edit(update,
        "🔑 <b>API ключ WormSoft</b>\n\n"
        "Введите ваш API ключ:\n"
        "<i>Где получить: ai.wormsoft.ru</i>",
        _kb([_btn("⏭ Пропустить", "ob_ai_skip_key")]),
    )
    return ST_ONBOARD_AI_KEY

async def onboard_got_ai_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    key = update.message.text.strip()
    provider = context.user_data.get("onboard_ai_provider", "")
    model = context.user_data.get("onboard_ai_model", "")

    DB.upsert_user_settings_by_tg(uid, ai_provider=provider, ai_api_key=key, ai_model=model)
    return await _finish_onboarding(update, context)

async def onboard_skip_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    return await _finish_onboarding(update, context)

async def _finish_onboarding(update: Update, context: ContextTypes.DEFAULT_TYPE):
    tg_id = update.effective_user.id
    DB.mark_onboarded(tg_id)
    city = context.user_data.get("onboard_city", "")
    provider = context.user_data.get("onboard_ai_provider", "")
    ai_line = f"🤖 AI: <b>{provider}</b>" if provider else "🤖 AI: <i>без AI (эвристики)</i>"

    text = (
        "✅ <b>Настройка завершена!</b>\n\n"
        f"🏙 Регион: <b>{city or 'не задан'}</b>\n"
        f"{ai_line}\n\n"
        "Теперь создайте первый поиск — нажмите <b>«🔍 Найти товар»</b> ниже.\n"
        "<i>Всё можно изменить в любой момент.</i>"
    )
    if update.callback_query:
        await _edit(update, text, _main_menu_kb(tg_id))
    else:
        await _send(update, text, _main_menu_kb(tg_id))
    return ConversationHandler.END

# ── Callback dispatcher ────────────────────────────────────────────────────────

@_check_ban
async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_user(update)
    await update.callback_query.answer()
    data = update.callback_query.data

    # Main menu
    if data == "menu_main":
        await show_main_menu(update, context)
    elif data == "menu_searches":
        await show_searches(update, context)
    elif data == "menu_radar":
        await show_radar(update, context)
    elif data == "menu_finds":
        await show_finds(update, context)
    elif data == "menu_settings":
        await show_settings(update, context)
    elif data == "menu_admin":
        await show_admin(update, context)

    # Settings
    elif data == "settings_city":
        await ask_city(update, context)
    elif data == "settings_sources":
        await show_sources(update, context)
    elif data.startswith("toggle_source_"):
        await toggle_source(update, context, data[len("toggle_source_"):])
    elif data == "settings_ai":
        await show_ai_settings(update, context)
    elif data.startswith("set_ai_"):
        await set_ai_provider_cb(update, context, data[len("set_ai_"):])
    elif data == "settings_notifications":
        await show_notifications(update, context)
    elif data.startswith("toggle_notif_"):
        await toggle_notification(update, context, data[len("toggle_notif_"):])
    elif data == "settings_thresholds":
        await show_thresholds(update, context)
    elif data.startswith("set_threshold_"):
        await set_threshold_cb(update, context, data[len("set_threshold_"):])
    elif data == "settings_hunter":
        await show_hunter(update, context)
    elif data.startswith("set_hunter_"):
        await set_hunter_cb(update, context, data[len("set_hunter_"):])

    # Admin
    elif data == "admin_stats":
        await show_admin_stats(update, context)
    elif data == "admin_users":
        await show_admin_users(update, context)
    elif data == "admin_broadcast":
        await ask_broadcast(update, context)
    elif data.startswith("admin_ban_"):
        tgid = int(data[len("admin_ban_"):])
        DB.ban_user(tgid, True)
        await update.callback_query.answer(f"Пользователь {tgid} заблокирован", show_alert=True)
        await show_admin_users(update, context)
    elif data.startswith("admin_unban_"):
        tgid = int(data[len("admin_unban_"):])
        DB.ban_user(tgid, False)
        await update.callback_query.answer(f"Пользователь {tgid} разблокирован", show_alert=True)
        await show_admin_users(update, context)
    elif data.startswith("admin_setplan_"):
        parts = data[len("admin_setplan_"):].split("_")
        tgid, plan = int(parts[0]), parts[1]
        DB.set_plan(tgid, plan)
        await update.callback_query.answer(f"План {plan} установлен", show_alert=True)
        await show_admin_users(update, context)

# ── Searches ───────────────────────────────────────────────────────────────────

async def show_searches(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    user = DB.get_user_by_telegram(uid)
    if not user:
        return
    searches = DB.get_user_searches(user["id"])

    if not searches:
        text = (
            "🔍 <b>Мои поиски</b>\n\n"
            "Пока ничего не ищете. 👀\n\n"
            "Нажмите <b>«➕ Создать поиск»</b> и напишите, что хотите найти.\n"
            "<i>Пример: iPhone 15 Pro до 80000</i>"
        )
        kb = _kb(
            [_btn("➕ Создать поиск", "new_search")],
            [_btn("◀ Назад", "menu_main")],
        )
    else:
        lines = []
        for s in searches[:10]:
            icon = "🟢" if s["active"] else "🔴"
            price_str = f" до {int(s['max_price'])}₽" if s.get("max_price") else ""
            lines.append(f"{icon} <b>{s['query']}</b>{price_str}")

        text = f"🔍 <b>Мои поиски</b> ({len(searches)})\n\n" + "\n".join(lines)
        kb = _kb(
            [_btn("➕ Добавить поиск", "new_search")],
            [_btn("◀ Назад", "menu_main")],
        )

    await _edit(update, text, kb)

# ── Radar ──────────────────────────────────────────────────────────────────────

async def show_radar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    user = DB.get_user_by_telegram(uid)
    if not user:
        return
    snapshots = DB.get_latest_radar(user["id"])

    if not snapshots:
        text = (
            "📡 <b>Радар рынка</b>\n\n"
            "Данных пока нет.\n"
            "<i>Радар обновляется каждый час после первых поисков.</i>"
        )
    else:
        lines = []
        for snap in snapshots:
            lines.append(
                f"{snap['trend_emoji']} <b>{snap['category']}</b> — "
                f"~{int(snap['avg_price']):,}₽ "
                f"({snap['trend_pct']:+.1f}%)\n"
                f"<i>{snap['ai_comment'][:80] if snap.get('ai_comment') else ''}</i>"
            )
        text = "📡 <b>Радар рынка</b>\n\n" + "\n\n".join(lines)

    await _edit(update, text, _kb([_btn("◀ Назад", "menu_main")]))

# ── Finds ──────────────────────────────────────────────────────────────────────

async def show_finds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    user = DB.get_user_by_telegram(uid)
    if not user:
        return
    finds = DB.get_saved_finds(user["id"])

    if not finds:
        text = (
            "💾 <b>Сохранённые находки</b>\n\n"
            "Здесь будут объявления, которые вы сохранили."
        )
    else:
        lines = []
        for f in finds[:10]:
            lines.append(
                f"📌 <b>{f['title'][:60]}</b>\n"
                f"   {int(f['price']):,}₽ · Скор: {int(f['deal_score'])}%"
            )
        text = f"💾 <b>Находки</b> ({len(finds)})\n\n" + "\n\n".join(lines)

    await _edit(update, text, _kb([_btn("◀ Назад", "menu_main")]))

# ── Settings main ──────────────────────────────────────────────────────────────

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)

    city = s.get("city") or "не задан"
    ai = s.get("ai_provider") or "без AI"
    hunter = "🟢 вкл" if s.get("hunter_enabled") else "🔴 выкл"
    notif = "🔔 вкл" if s.get("notifications_enabled") else "🔕 выкл"
    avito = "✅" if s.get("sources_avito", 1) else "❌"
    youla = "✅" if s.get("sources_youla", 1) else "❌"

    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🏙 Регион: <b>{city}</b>\n"
        f"📦 Источники: Авито {avito} · Юла {youla}\n"
        f"🤖 AI: <b>{ai}</b>\n"
        f"🔔 Уведомления: {notif}\n"
        f"🎯 Режим охотника: {hunter}"
    )
    await _edit(update, text, _kb(
        [_btn("🏙 Регион", "settings_city"), _btn("📦 Источники", "settings_sources")],
        [_btn("🤖 AI провайдер", "settings_ai")],
        [_btn("🔔 Уведомления", "settings_notifications")],
        [_btn("📊 Пороги сделок", "settings_thresholds")],
        [_btn("🎯 Режим охотника", "settings_hunter")],
        [_btn("◀ Назад", "menu_main")],
    ))

# ── City ───────────────────────────────────────────────────────────────────────

async def ask_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    current = s.get("city") or "не задан"
    await _edit(update,
        f"🏙 <b>Ваш регион</b>\n\n"
        f"Текущий: <code>{current}</code>\n\n"
        "Город, край или страна.\n"
        "<i>Примеры: Москва, Краснодарский край, Россия</i>",
        _kb([_btn("◀ Отмена", "menu_settings")]),
    )
    context.user_data["wait_for"] = "city"
    return ST_WAIT_CITY

async def got_city(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    city = update.message.text.strip()
    DB.upsert_user_settings_by_tg(uid, city=city)
    await _send(update, f"✅ Регион сохранён: <b>{city}</b>")
    await show_settings_msg(update, context)
    return ConversationHandler.END

async def show_settings_msg(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    city = s.get("city") or "не задан"
    ai = s.get("ai_provider") or "без AI"
    hunter = "🟢 вкл" if s.get("hunter_enabled") else "🔴 выкл"
    notif = "🔔 вкл" if s.get("notifications_enabled") else "🔕 выкл"
    avito = "✅" if s.get("sources_avito", 1) else "❌"
    youla = "✅" if s.get("sources_youla", 1) else "❌"
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🏙 Регион: <b>{city}</b>\n"
        f"📦 Источники: Авито {avito} · Юла {youla}\n"
        f"🤖 AI: <b>{ai}</b>\n"
        f"🔔 Уведомления: {notif}\n"
        f"🎯 Режим охотника: {hunter}"
    )
    await update.effective_chat.send_message(text, parse_mode="HTML", reply_markup=_kb(
        [_btn("🏙 Регион", "settings_city"), _btn("📦 Источники", "settings_sources")],
        [_btn("🤖 AI провайдер", "settings_ai")],
        [_btn("🔔 Уведомления", "settings_notifications")],
        [_btn("📊 Пороги сделок", "settings_thresholds")],
        [_btn("🎯 Режим охотника", "settings_hunter")],
        [_btn("◀ Назад", "menu_main")],
    ))

# ── Sources ────────────────────────────────────────────────────────────────────

async def show_sources(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    avito = bool(s.get("sources_avito", 1))
    youla = bool(s.get("sources_youla", 1))

    await _edit(update,
        "📦 <b>Источники объявлений</b>\n\n"
        "Выберите площадки для поиска:",
        _kb(
            [_btn(f"{'✅' if avito else '❌'} Авито", "toggle_source_avito")],
            [_btn(f"{'✅' if youla else '❌'} Юла", "toggle_source_youla")],
            [_btn("◀ Назад", "menu_settings")],
        ),
    )

async def toggle_source(update: Update, context: ContextTypes.DEFAULT_TYPE, source: str):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    key = f"sources_{source}"
    current = bool(s.get(key, 1))
    DB.upsert_user_settings_by_tg(uid, **{key: 0 if current else 1})
    await show_sources(update, context)

# ── AI Settings ────────────────────────────────────────────────────────────────

async def show_ai_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    current = s.get("ai_provider") or ""
    model = s.get("ai_model") or ""

    def mark(p): return "✅ " if current == p else ""

    model_line = f"\nМодель: <code>{model}</code>" if model else ""
    await _edit(update,
        "🤖 <b>AI Провайдер</b>\n\n"
        f"Текущий: <b>{'без AI' if not current else current}</b>{model_line}\n\n"
        "<b>Что даёт AI:</b>\n"
        "✅ Объяснение каждой находки\n"
        "✅ Оценка рисков продавца\n"
        "✅ Анализ рынка с комментариями",
        _kb(
            [_btn(f"{mark('wormsoft')}🦾 WormSoft AI (рекомендуется)", "set_ai_wormsoft")],
            [_btn(f"{mark('openai')}🤖 OpenAI GPT", "set_ai_openai")],
            [_btn(f"{mark('gemini')}✨ Google Gemini", "set_ai_gemini")],
            [_btn(f"{mark('anthropic')}🔮 Claude", "set_ai_anthropic")],
            [_btn(f"{mark('')}⚙️ Без AI", "set_ai_none")],
            [_btn("◀ Назад", "menu_settings")],
        ),
    )

async def set_ai_provider_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, provider: str):
    uid = _get_user_id(update)

    if provider == "none":
        DB.upsert_user_settings_by_tg(uid, ai_provider="", ai_api_key="", ai_model="")
        await update.callback_query.answer("AI отключён", show_alert=False)
        await show_ai_settings(update, context)
        return ConversationHandler.END

    context.user_data["pending_ai_provider"] = provider

    if provider == "wormsoft":
        await _edit(update,
            "🦾 <b>WormSoft AI</b>\n\nВыберите модель:",
            _kb(
                [_btn("⚡ Low — быстрая и дешёвая", "set_ai_model_wormsoft_agent_low")],
                [_btn("🎯 Medium — точнее", "set_ai_model_wormsoft_agent_medium")],
                [_btn("◀ Отмена", "settings_ai")],
            ),
        )
        return ST_WAIT_AI_KEY

    info = {
        "openai": ("OpenAI GPT", "platform.openai.com → API Keys"),
        "gemini": ("Google Gemini", "aistudio.google.com → Get API Key"),
        "anthropic": ("Anthropic Claude", "console.anthropic.com → API Keys"),
    }
    name, where = info.get(provider, (provider, ""))
    await _edit(update,
        f"🔑 <b>API ключ {name}</b>\n\n"
        f"Введите ваш API ключ:\n"
        f"<i>Где получить: {where}</i>",
        _kb([_btn("◀ Отмена", "settings_ai")]),
    )
    return ST_WAIT_AI_KEY

async def ai_model_selected(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data  # set_ai_model_wormsoft_agent_low
    model = data.replace("set_ai_model_", "").replace("_", "/", 2)
    # wormsoft/agent/low or wormsoft/agent/medium
    context.user_data["pending_ai_model"] = model
    await _edit(update,
        "🔑 <b>API ключ WormSoft</b>\n\n"
        "Введите ваш API ключ:\n"
        "<i>Где получить: ai.wormsoft.ru</i>",
        _kb([_btn("◀ Отмена", "settings_ai")]),
    )
    return ST_WAIT_AI_KEY

async def got_ai_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    key = update.message.text.strip()
    provider = context.user_data.pop("pending_ai_provider", "")
    model = context.user_data.pop("pending_ai_model", "")

    DB.upsert_user_settings_by_tg(uid, ai_provider=provider, ai_api_key=key, ai_model=model)

    # Quick test
    from ai.factory import get_user_ai_provider, provider_display_name
    s = DB.get_user_settings_by_tg(uid)
    prov = get_user_ai_provider(s)
    if prov:
        await _send(update,
            f"✅ <b>{provider_display_name(provider)}</b> подключён!\n"
            f"Модель: <code>{model or 'по умолчанию'}</code>"
        )
    else:
        await _send(update, "⚠️ Ключ сохранён, но провайдер не инициализировался. Проверьте ключ.")

    await show_settings_msg(update, context)
    return ConversationHandler.END

# ── Notifications ──────────────────────────────────────────────────────────────

async def show_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    notif = bool(s.get("notifications_enabled", 1))
    buy = bool(s.get("notify_on_buy", 1))
    maybe = bool(s.get("notify_on_maybe", 0))
    qh_start = s.get("notify_quiet_hours_start", 23)
    qh_end = s.get("notify_quiet_hours_end", 8)

    def t(v): return "✅" if v else "❌"

    await _edit(update,
        "🔔 <b>Уведомления</b>\n\n"
        f"Уведомления: {t(notif)}\n"
        f"🔥 Отличные сделки (≥70%): {t(buy)}\n"
        f"👍 Хорошие сделки (≥50%): {t(maybe)}\n"
        f"🌙 Тихие часы: <code>{qh_start:02d}:00–{qh_end:02d}:00</code>",
        _kb(
            [_btn(f"{t(notif)} Уведомления вкл/выкл", "toggle_notif_enabled")],
            [_btn(f"{t(buy)} 🔥 Отличные сделки", "toggle_notif_buy")],
            [_btn(f"{t(maybe)} 👍 Хорошие сделки", "toggle_notif_maybe")],
            [_btn("🌙 Тихие часы", "settings_quiet_hours")],
            [_btn("◀ Назад", "menu_settings")],
        ),
    )

async def toggle_notification(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    field_map = {
        "enabled": "notifications_enabled",
        "buy": "notify_on_buy",
        "maybe": "notify_on_maybe",
    }
    field = field_map.get(key)
    if field:
        current = bool(s.get(field, 1))
        DB.upsert_user_settings_by_tg(uid, **{field: 0 if current else 1})
    await show_notifications(update, context)

# ── Thresholds ─────────────────────────────────────────────────────────────────

async def show_thresholds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    buy = s.get("threshold_buy", 70.0)
    maybe = s.get("threshold_maybe", 50.0)

    await _edit(update,
        "📊 <b>Пороги сделок</b>\n\n"
        f"🔥 Порог «Отличная сделка»: <b>{int(buy)}%</b>\n"
        f"👍 Порог «Хорошая сделка»: <b>{int(maybe)}%</b>\n\n"
        "<i>Чем выше порог — тем меньше уведомлений, но лучше качество.</i>",
        _kb(
            [
                _btn("🔥 Порог «Купить»", "set_threshold_buy"),
                _btn("👍 Порог «Возможно»", "set_threshold_maybe"),
            ],
            [
                _btn("Стандарт (70/50)", "set_threshold_preset_standard"),
                _btn("Строгий (80/65)", "set_threshold_preset_strict"),
                _btn("Мягкий (60/40)", "set_threshold_preset_soft"),
            ],
            [_btn("◀ Назад", "menu_settings")],
        ),
    )

async def set_threshold_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    uid = _get_user_id(update)

    presets = {
        "preset_standard": {"threshold_buy": 70.0, "threshold_maybe": 50.0},
        "preset_strict": {"threshold_buy": 80.0, "threshold_maybe": 65.0},
        "preset_soft": {"threshold_buy": 60.0, "threshold_maybe": 40.0},
    }
    if key in presets:
        DB.upsert_user_settings_by_tg(uid, **presets[key])
        await update.callback_query.answer("Пресет применён ✅", show_alert=False)
        await show_thresholds(update, context)
        return ConversationHandler.END

    context.user_data["threshold_type"] = key
    label = "🔥 «Купить»" if key == "buy" else "👍 «Возможно»"
    await _edit(update,
        f"📊 <b>Порог {label}</b>\n\n"
        "Введите значение от 30 до 95 (число):",
        _kb([_btn("◀ Отмена", "settings_thresholds")]),
    )
    return ST_WAIT_THRESHOLD

async def got_threshold(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    try:
        val = float(update.message.text.strip())
        val = max(30.0, min(95.0, val))
    except ValueError:
        await _send(update, "❌ Введите число от 30 до 95")
        return ST_WAIT_THRESHOLD

    t_type = context.user_data.pop("threshold_type", "buy")
    field = "threshold_buy" if t_type == "buy" else "threshold_maybe"
    DB.upsert_user_settings_by_tg(uid, **{field: val})
    await _send(update, f"✅ Порог сохранён: <b>{int(val)}%</b>")
    await show_settings_msg(update, context)
    return ConversationHandler.END

# ── Hunter Mode ────────────────────────────────────────────────────────────────

async def show_hunter(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    enabled = bool(s.get("hunter_enabled", 0))
    interval = s.get("hunter_interval_sec", 300)
    min_score = s.get("hunter_min_score", 50.0)
    min_savings = s.get("hunter_min_savings_pct", 10.0)

    interval_str = {60: "1 мин", 120: "2 мин", 300: "5 мин",
                    600: "10 мин", 1800: "30 мин", 3600: "1 час"}.get(interval, f"{interval//60} мин")

    await _edit(update,
        "🎯 <b>Режим Охотника</b>\n\n"
        f"Статус: {'🟢 Активен' if enabled else '🔴 Выключен'}\n"
        f"Интервал проверки: <b>{interval_str}</b>\n"
        f"Мин. скор: <b>{int(min_score)}%</b>\n"
        f"Мин. экономия: <b>{int(min_savings)}%</b>\n\n"
        "<i>Охотник автоматически ищет выгодные объявления по вашим запросам.</i>",
        _kb(
            [_btn("🟢 Включить" if not enabled else "🔴 Выключить", "set_hunter_toggle")],
            [
                _btn("⏱ 1 мин", "set_hunter_int_60"),
                _btn("5 мин", "set_hunter_int_300"),
                _btn("30 мин", "set_hunter_int_1800"),
            ],
            [_btn("◀ Назад", "menu_settings")],
        ),
    )

async def set_hunter_cb(update: Update, context: ContextTypes.DEFAULT_TYPE, key: str):
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)

    if key == "toggle":
        current = bool(s.get("hunter_enabled", 0))
        DB.upsert_user_settings_by_tg(uid, hunter_enabled=0 if current else 1)
    elif key.startswith("int_"):
        interval = int(key[4:])
        DB.upsert_user_settings_by_tg(uid, hunter_interval_sec=interval)

    await show_hunter(update, context)

# ── Admin Panel ────────────────────────────────────────────────────────────────

async def show_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    if not (settings.is_admin(uid) or DB.is_admin(uid)):
        await update.callback_query.answer("❌ Нет доступа", show_alert=True)
        return

    await _edit(update,
        "👑 <b>Панель администратора</b>\n\n"
        "Управление системой и пользователями.",
        _kb(
            [_btn("📊 Статистика", "admin_stats")],
            [_btn("👥 Пользователи", "admin_users")],
            [_btn("📢 Рассылка", "admin_broadcast")],
            [_btn("◀ Назад", "menu_main")],
        ),
    )

async def show_admin_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    if not (settings.is_admin(uid) or DB.is_admin(uid)):
        return

    st = DB.get_admin_stats()
    text = (
        "📊 <b>Статистика системы</b>\n\n"
        f"👥 Всего пользователей: <b>{st['total_users']}</b>\n"
        f"✅ Активных: <b>{st['active_users']}</b>\n"
        f"🆕 Сегодня новых: <b>{st['today_new_users']}</b>\n"
        f"⭐ Pro/Unlimited: <b>{st['pro_users']}</b>\n\n"
        f"🔍 Активных поисков: <b>{st['active_searches']}</b>\n"
        f"🔔 Алертов сегодня: <b>{st['today_alerts']}</b>\n"
        f"📦 Объявлений в БД: <b>{st['total_listings']:,}</b>"
    )
    await _edit(update, text, _kb(
        [_btn("🔄 Обновить", "admin_stats")],
        [_btn("◀ Назад", "menu_admin")],
    ))

async def show_admin_users(update: Update, context: ContextTypes.DEFAULT_TYPE, page: int = 0):
    uid = _get_user_id(update)
    if not (settings.is_admin(uid) or DB.is_admin(uid)):
        return

    users = DB.get_all_users(limit=20)
    if not users:
        await _edit(update, "👥 Пользователей нет.", _kb([_btn("◀ Назад", "menu_admin")]))
        return

    rows = []
    for u in users[:10]:
        uname = u.get("username") or u.get("first_name") or "Аноним"
        plan = u.get("plan", "free")
        active = "✅" if u.get("is_active", 1) else "🚫"
        plan_badge = {"free": "🆓", "pro": "⭐", "unlimited": "💎"}.get(plan, "")
        rows.append(f"{active} {plan_badge} <code>{u['telegram_id']}</code> @{uname}")

    text = f"👥 <b>Пользователи</b> ({len(users)})\n\n" + "\n".join(rows)

    # Build action buttons for first 5 users
    btn_rows = []
    for u in users[:5]:
        tgid = u["telegram_id"]
        uname = (u.get("username") or "user")[:10]
        is_banned = not bool(u.get("is_active", 1))
        ban_btn = _btn("✅ Разбан" if is_banned else "🚫 Бан", f"admin_unban_{tgid}" if is_banned else f"admin_ban_{tgid}")
        pro_btn = _btn("⭐ Pro", f"admin_setplan_{tgid}_pro")
        free_btn = _btn("🆓 Free", f"admin_setplan_{tgid}_free")
        btn_rows.append([InlineKeyboardButton(f"@{uname}", callback_data="noop"), ban_btn, pro_btn, free_btn])

    btn_rows.append([_btn("◀ Назад", "menu_admin")])
    await _edit(update, text, InlineKeyboardMarkup(btn_rows))

async def ask_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    if not (settings.is_admin(uid) or DB.is_admin(uid)):
        return

    await _edit(update,
        "📢 <b>Рассылка</b>\n\nНапишите сообщение для всех пользователей:",
        _kb([_btn("◀ Отмена", "menu_admin")]),
    )
    return ST_ADMIN_BROADCAST

async def do_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE):
    uid = _get_user_id(update)
    msg_text = update.message.text
    users = DB.get_all_users(limit=10000)
    app = context.application
    sent = 0
    for u in users:
        if not u.get("is_active", 1):
            continue
        try:
            await app.bot.send_message(u["telegram_id"], msg_text, parse_mode="HTML")
            sent += 1
            await asyncio.sleep(0.05)  # rate limit
        except Exception:
            pass

    await _send(update, f"✅ Рассылка завершена. Отправлено: <b>{sent}</b> пользователям.")
    return ConversationHandler.END

# ── /admin command (alias) ─────────────────────────────────────────────────────

async def cmd_admin(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_user(update)
    uid = _get_user_id(update)
    if not (settings.is_admin(uid) or DB.is_admin(uid)):
        await _send(update, "❌ Нет доступа.")
        return
    await _send(update,
        "👑 <b>Панель администратора</b>",
        _kb(
            [_btn("📊 Статистика", "admin_stats")],
            [_btn("👥 Пользователи", "admin_users")],
            [_btn("📢 Рассылка", "admin_broadcast")],
            [_btn("◀ Главное меню", "menu_main")],
        ),
    )

# ── /settings command (shortcut) ──────────────────────────────────────────────

async def cmd_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    _ensure_user(update)
    uid = _get_user_id(update)
    s = DB.get_user_settings_by_tg(uid)
    city = s.get("city") or "не задан"
    ai = s.get("ai_provider") or "без AI"
    hunter = "🟢 вкл" if s.get("hunter_enabled") else "🔴 выкл"
    notif = "🔔 вкл" if s.get("notifications_enabled") else "🔕 выкл"
    avito = "✅" if s.get("sources_avito", 1) else "❌"
    youla = "✅" if s.get("sources_youla", 1) else "❌"
    text = (
        "⚙️ <b>Настройки</b>\n\n"
        f"🏙 Регион: <b>{city}</b>\n"
        f"📦 Источники: Авито {avito} · Юла {youla}\n"
        f"🤖 AI: <b>{ai}</b>\n"
        f"🔔 Уведомления: {notif}\n"
        f"🎯 Режим охотника: {hunter}"
    )
    await _send(update, text, _kb(
        [_btn("🏙 Регион", "settings_city"), _btn("📦 Источники", "settings_sources")],
        [_btn("🤖 AI провайдер", "settings_ai")],
        [_btn("🔔 Уведомления", "settings_notifications")],
        [_btn("📊 Пороги сделок", "settings_thresholds")],
        [_btn("🎯 Режим охотника", "settings_hunter")],
        [_btn("◀ Главное меню", "menu_main")],
    ))

# ── Alert push API (called by scheduler) ─────────────────────────────────────

_app_ref: Optional[Application] = None

def set_app(app: Application):
    global _app_ref
    _app_ref = app

async def push_alert(telegram_id: int, text: str):
    if _app_ref:
        try:
            await _app_ref.bot.send_message(telegram_id, text, parse_mode="HTML")
        except Exception as e:
            log.warning("push_alert failed for %s: %s", telegram_id, e)

async def send_deal_alert(
    app: Application,
    telegram_id: int,
    alert_data: dict,
):
    """Send a deal alert to a user. Called externally by the scheduler."""
    from bot.alerts import format_alert

    title = alert_data.get("title", "")
    price = alert_data.get("price", 0)
    market_price = alert_data.get("market_price", price)
    deal_score = alert_data.get("deal_score", 0)
    price_delta_pct = alert_data.get("price_delta_pct", 0)
    risk_score = alert_data.get("risk_score", 50)
    recommendation = alert_data.get("recommendation", "maybe")
    ai_explanation = alert_data.get("ai_explanation") or ""
    ai_why_good = alert_data.get("ai_why_good") or []
    ai_risks = alert_data.get("ai_risks") or []
    url = alert_data.get("url", "")
    confidence = alert_data.get("confidence") or (alert_data.get("ai_score") or deal_score)
    if confidence > 1.0:
        confidence = confidence / 100.0
    market_liquidity = alert_data.get("market_liquidity", "medium")

    card = format_alert(
        title=title, price=price, market_price=market_price,
        deal_score=deal_score, price_delta_pct=price_delta_pct,
        risk_score=risk_score, recommendation=recommendation,
        ai_explanation=ai_explanation, ai_why_good=ai_why_good,
        ai_risks=ai_risks, confidence=confidence, market_liquidity=market_liquidity
    )

    header = (
        "🔥 <b>Новая находка!</b>\n\n"
        f"Уверенность: <b>{confidence * 100:.0f}%</b>\n"
        f"Рекомендация: {'🟢 Стоит посмотреть' if recommendation == 'buy' else '🟡 Интересно'}\n\n"
    )

    kb_rows = []
    if url:
        kb_rows.append([InlineKeyboardButton("🔗 Открыть объявление", url=url)])
    kb_rows.append([_btn("🏠 В меню", "menu_main")])

    try:
        await app.bot.send_message(
            chat_id=telegram_id,
            text=header + card,
            parse_mode="HTML",
            reply_markup=_kb(*kb_rows),
            disable_web_page_preview=True,
        )
    except Exception as e:
        log.warning("Failed to send alert to %s: %s", telegram_id, e)

# ── App builder ────────────────────────────────────────────────────────────────

def build_app() -> Application:
    DB.init_schema()

    # Make owner admin
    if settings.admin_telegram_id:
        try:
            DB.upsert_user(settings.admin_telegram_id)
            DB.set_admin(settings.admin_telegram_id, True)
        except Exception:
            pass

    # Build request with proxy
    from telegram.request import HTTPXRequest
    http_kwargs = {}
    if settings.proxy_url:
        http_kwargs["proxy"] = settings.proxy_url
    request = HTTPXRequest(**http_kwargs)

    app = Application.builder().token(settings.telegram_bot_token).request(request).build()
    set_app(app)

    # Main ConversationHandler
    conv = ConversationHandler(
        entry_points=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(ask_city, pattern="^settings_city$"),
            CallbackQueryHandler(set_ai_provider_cb.__wrapped__ if hasattr(set_ai_provider_cb, '__wrapped__') else lambda u, c: None, pattern="^set_ai_"),
            CallbackQueryHandler(set_threshold_cb.__wrapped__ if hasattr(set_threshold_cb, '__wrapped__') else lambda u, c: None, pattern="^set_threshold_"),
            CallbackQueryHandler(ask_broadcast, pattern="^admin_broadcast$"),
        ],
        states={
            ST_ONBOARD_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_got_city)],
            ST_ONBOARD_AI_CHOOSE: [CallbackQueryHandler(onboard_ai_choose, pattern="^ob_ai_")],
            ST_ONBOARD_AI_MODEL: [CallbackQueryHandler(onboard_ai_model, pattern="^ob_model_")],
            ST_ONBOARD_AI_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, onboard_got_ai_key),
                CallbackQueryHandler(onboard_skip_key, pattern="^ob_ai_skip_key$"),
                CallbackQueryHandler(ai_model_selected, pattern="^set_ai_model_"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_ai_key),
            ],
            ST_WAIT_CITY: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_city)],
            ST_WAIT_AI_KEY: [
                MessageHandler(filters.TEXT & ~filters.COMMAND, got_ai_key),
                CallbackQueryHandler(ai_model_selected, pattern="^set_ai_model_"),
            ],
            ST_WAIT_THRESHOLD: [MessageHandler(filters.TEXT & ~filters.COMMAND, got_threshold)],
            ST_ADMIN_BROADCAST: [MessageHandler(filters.TEXT & ~filters.COMMAND, do_broadcast)],
        },
        fallbacks=[
            CommandHandler("start", cmd_start),
            CallbackQueryHandler(handle_callback),
        ],
        allow_reentry=True,
    )

    app.add_handler(conv)
    app.add_handler(CommandHandler("admin", cmd_admin))
    app.add_handler(CommandHandler("settings", cmd_settings))
    app.add_handler(CallbackQueryHandler(handle_callback))

    log.info("Bot built. Admin ID: %s", settings.admin_telegram_id or "not set")
    return app


class MarketAgentBot:
    """Market Agent Telegram Bot runner."""

    def __init__(self, db: Database = DB):
        self.db = db
        self._app: Optional[Application] = None

    def start(self):
        if not settings.telegram_bot_token:
            raise ValueError("MA_TELEGRAM_BOT_TOKEN not set")
        self._app = build_app()
        log.info("Market Agent Bot starting in polling mode...")
        self._app.run_polling(drop_pending_updates=True)


async def run_bot():
    if not settings.telegram_bot_token:
         raise ValueError("MA_TELEGRAM_BOT_TOKEN not set")
    app = build_app()
    await app.initialize()
    await app.start()
    await app.updater.start_polling(drop_pending_updates=True)
    log.info("Bot polling started")
    try:
        await asyncio.Event().wait()
    finally:
        await app.updater.stop()
        await app.stop()
        await app.shutdown()
