"""Telegram Bot — Market Agent v2. Personal AI Marketplace Intelligence Platform.

Architecture:
    Bot UI Layer
          │
    ConversationManager
          │
    Search Intent Parser (AI optional)
          │
    Market Agent Core
          │
    Deal Scoring Engine
          │
    Notification System

UX Principles:
  - Max 2-3 buttons per screen
  - All actions via inline buttons
  - Emoji as visual markers
  - No technical jargon for users
  - Pошаговый диалог вместо команд
  - Commands only for admin (/start, /menu)
"""

from __future__ import annotations

import logging
from typing import Optional

from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ConversationHandler,
    ContextTypes,
    MessageHandler,
    filters,
)

from config import settings
from database.db import Database
from models import SearchQuery
from bot.alerts import format_alert

log = logging.getLogger("market_agent.bot")

# ── Conversation states ────────────────────────────────────────────────────────
(
    WAIT_QUERY,
    WAIT_PRICE,
    WAIT_LOCATION,
    WAIT_CONDITION,
    WAIT_PURPOSE,
    WAIT_AI_KEY,
) = range(6)

DB = Database()


# ═══════════════════════════════════════════════════════════════════════════════
#  HELPERS
# ═══════════════════════════════════════════════════════════════════════════════

def _get_user_id(update: Update) -> int:
    user = update.effective_user
    DB.upsert_user(telegram_id=user.id, username=user.username or user.full_name)
    row = DB.get_user_by_telegram(user.id)
    return row["id"] if row else 0


def _kb(*rows: list) -> InlineKeyboardMarkup:
    """Shorthand keyboard builder."""
    return InlineKeyboardMarkup(rows)


def _btn(text: str, data: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, callback_data=data)


def _url_btn(text: str, url: str) -> InlineKeyboardButton:
    return InlineKeyboardButton(text, url=url)


def _home_row() -> list:
    return [_btn("🏠 В меню", "menu_home")]


async def _edit(update: Update, text: str, kb: InlineKeyboardMarkup):
    """Edit current message safely."""
    msg = update.effective_message
    try:
        await msg.edit_text(text, parse_mode="HTML", reply_markup=kb)
    except Exception:
        await msg.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ═══════════════════════════════════════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Entry point — /start or /menu."""
    _get_user_id(update)
    await show_main_menu(update, context)


async def show_main_menu(update: Update, context: ContextTypes.DEFAULT_TYPE, edit: bool = False):
    user_id = _get_user_id(update)
    stats = DB.get_user_stats(user_id)
    user_settings = DB.get_user_settings(user_id)
    hunter_on = bool(user_settings.get("hunter_enabled", 0))
    hunter_status = "🟢 Агент работает" if hunter_on else "⚪ Агент на паузе"

    ai_provider = user_settings.get("ai_provider", "") or settings.ai_provider
    ai_badge = ""
    if ai_provider:
        from ai.factory import provider_display_name
        ai_badge = f"\n🤖 AI: {provider_display_name(ai_provider)}"

    today_checked = stats.get("today_checked", 0)
    today_good = stats.get("today_good", 0)
    avg_savings = stats.get("avg_savings", 0)

    text = (
        "🤖 <b>Market Agent</b>\n"
        "<i>Ваш личный охотник за выгодными предложениями</i>\n\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"{hunter_status}{ai_badge}\n\n"
        "<b>Сегодня:</b>\n"
        f"🔎 Проверено: <b>{today_checked}</b> объявлений\n"
        f"🔥 Найдено выгодных: <b>{today_good}</b>\n"
        f"📉 Средняя экономия: <b>{avg_savings}%</b>\n\n"
        "<b>━━━━━━━━━━━━━━━━━━━━━━━</b>"
    )

    kb = _kb(
        [_btn("🔍 Новый поиск", "menu_search")],
        [_btn("🎯 Мои охоты", "menu_hunts"), _btn("🔥 Находки", "menu_finds")],
        [_btn("📡 Market Radar", "menu_radar"), _btn("📊 Статистика", "menu_stats")],
        [_btn("⚙️ Настройки", "menu_settings")],
    )

    if edit:
        await _edit(update, text, kb)
    else:
        await update.effective_message.reply_text(text, parse_mode="HTML", reply_markup=kb)


# ═══════════════════════════════════════════════════════════════════════════════
#  CALLBACK DISPATCHER
# ═══════════════════════════════════════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    _get_user_id(update)

    routes = {
        "menu_home":     lambda: show_main_menu(update, context, edit=True),
        "menu_hunts":    lambda: show_hunts(update, context),
        "menu_finds":    lambda: show_finds(update, context),
        "menu_stats":    lambda: show_stats(update, context),
        "menu_radar":    lambda: show_radar(update, context),
        "menu_settings": lambda: show_settings(update, context),
        "hunter_on":     lambda: set_hunter(update, context, True),
        "hunter_off":    lambda: set_hunter(update, context, False),
        "search_cancel": lambda: cancel_search(update, context),
    }

    if data in routes:
        await routes[data]()
        return

    # Parametric routes
    if data.startswith("hunt_open_"):
        await show_hunt_detail(update, int(data[len("hunt_open_"):]))
    elif data.startswith("hunt_pause_"):
        DB.deactivate_search(int(data[len("hunt_pause_"):]))
        await show_hunts(update, context)
    elif data.startswith("hunt_resume_"):
        DB.activate_search(int(data[len("hunt_resume_"):]))
        await show_hunts(update, context)
    elif data.startswith("hunt_delete_"):
        DB.deactivate_search(int(data[len("hunt_delete_"):]))
        await show_hunts(update, context)
    elif data.startswith("find_save_"):
        await save_find(update, context, data)
    elif data.startswith("find_skip_"):
        await query.answer("Пропущено ✓", show_alert=False)
    elif data.startswith("finds_page_"):
        context.user_data["finds_page"] = int(data[len("finds_page_"):])
        await show_finds(update, context)
    elif data.startswith("settings_ai_"):
        await show_ai_settings(update, context, data[len("settings_ai_"):])
    elif data.startswith("set_ai_provider_"):
        await set_ai_provider(update, context, data[len("set_ai_provider_"):])
    elif data == "wormsoft_model_low":
        context.user_data["pending_ai_model"] = "wormsoft/agent/low"
        await _ask_wormsoft_key(update)
    elif data == "wormsoft_model_medium":
        context.user_data["pending_ai_model"] = "wormsoft/agent/medium"
        await _ask_wormsoft_key(update)
    elif data.startswith("set_hunter_interval_"):
        await set_hunter_interval(update, context, int(data[len("set_hunter_interval_"):]))
    elif data.startswith("set_hunter_min_"):
        await set_hunter_min(update, context, float(data[len("set_hunter_min_"):]))
    elif data == "settings_hunter":
        await show_hunter_settings(update, context)
    elif data == "settings_notifications":
        await toggle_notifications(update, context)
    elif data == "menu_saved":
        await show_saved_finds(update, context)


# ═══════════════════════════════════════════════════════════════════════════════
#  SEARCH DIALOG (пошаговый)
# ═══════════════════════════════════════════════════════════════════════════════

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 1: Ask what to search."""
    context.user_data.clear()
    await _edit(
        update,
        "🔍 <b>Новый поиск</b>\n\n"
        "Что будем искать?\n\n"
        "<i>Например: MacBook Pro M2, iPhone 15, RTX 4090, BMW E60</i>",
        _kb([_btn("🚫 Отмена", "search_cancel")]),
    )
    return WAIT_QUERY


async def got_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 2: Got item name, ask price."""
    query_text = update.message.text.strip()
    context.user_data["query"] = query_text

    # Try AI intent parsing in background (non-blocking)
    user_id = _get_user_id(update)
    user_settings = DB.get_user_settings(user_id)
    try:
        from ai.factory import get_user_ai_provider
        ai = get_user_ai_provider(user_settings)
        if ai and ai.is_available:
            intent = await ai.parse_intent(query_text)
            if intent.max_price:
                context.user_data["ai_max_price"] = intent.max_price
            if intent.location:
                context.user_data["ai_location"] = intent.location
            if intent.condition != "any":
                context.user_data["ai_condition"] = intent.condition
    except Exception:
        pass

    price_hint = ""
    if context.user_data.get("ai_max_price"):
        price_hint = f"\n\n<i>AI подсказка: ~{context.user_data['ai_max_price']:,.0f} ₽</i>"

    await update.message.reply_text(
        f"✅ <b>{query_text}</b>\n\n"
        "💰 <b>Максимальная цена</b>\n\n"
        f"Введите сумму в рублях или пропустите.{price_hint}",
        parse_mode="HTML",
        reply_markup=_kb([_btn("⏭ Пропустить", "price_skip")]),
    )
    return WAIT_PRICE


async def got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Step 3: Got price, ask city."""
    try:
        price = int("".join(c for c in update.message.text if c.isdigit()))
        context.user_data["max_price"] = price
    except ValueError:
        pass
    await _ask_location(update)
    return WAIT_LOCATION


async def _ask_location(update: Update):
    await update.effective_message.reply_text(
        "📍 <b>Город</b>\n\nВыберите или введите свой.",
        parse_mode="HTML",
        reply_markup=_kb(
            [_btn("🏙 Москва", "loc_msk"), _btn("🌇 Санкт-Петербург", "loc_spb")],
            [_btn("🌆 Екатеринбург", "loc_ekb"), _btn("🌃 Новосибирск", "loc_nsk")],
            [_btn("🌍 Везде", "loc_skip")],
        ),
    )


async def got_location_text(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """User typed a city name."""
    context.user_data["location"] = update.message.text.strip()
    await _ask_condition(update)
    return WAIT_CONDITION


async def _set_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Location button pressed."""
    await update.callback_query.answer()
    loc_map = {
        "loc_msk": "Москва",
        "loc_spb": "Санкт-Петербург",
        "loc_ekb": "Екатеринбург",
        "loc_nsk": "Новосибирск",
        "loc_skip": None,
    }
    context.user_data["location"] = loc_map.get(update.callback_query.data)
    await _ask_condition(update)
    return WAIT_CONDITION


async def _ask_condition(update: Update):
    await update.effective_message.reply_text(
        "📦 <b>Состояние</b>\n\nКакое состояние вас интересует?",
        parse_mode="HTML",
        reply_markup=_kb(
            [_btn("✨ Новый", "cond_new"), _btn("👍 Как новый", "cond_likenew")],
            [_btn("📦 Б/у", "cond_used"), _btn("⏭ Не важно", "cond_any")],
        ),
    )


async def got_condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Condition selected."""
    await update.callback_query.answer()
    context.user_data["condition"] = update.callback_query.data  # cond_new, etc.
    await _ask_purpose(update)
    return WAIT_PURPOSE


async def _ask_purpose(update: Update):
    await update.effective_message.reply_text(
        "🎯 <b>Цель покупки</b>",
        parse_mode="HTML",
        reply_markup=_kb(
            [_btn("🏠 Для себя", "purp_self")],
            [_btn("💰 Найти дешевле рынка", "purp_deal")],
            [_btn("🔄 Перепродажа", "purp_resale")],
        ),
    )


async def got_purpose(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Purpose selected — final step, create hunt."""
    await update.callback_query.answer()
    purp_map = {"purp_self": "self", "purp_deal": "deal", "purp_resale": "resale"}
    context.user_data["purpose"] = purp_map.get(update.callback_query.data, "self")
    await create_hunt(update, context)
    return ConversationHandler.END


async def create_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Save the search and confirm to user."""
    user = update.effective_user
    user_row = DB.get_user_by_telegram(user.id)
    if not user_row:
        await update.effective_message.reply_text("❌ Ошибка. Попробуйте /start")
        return

    q = context.user_data.get("query", "Поиск")
    max_price = context.user_data.get("max_price")
    location = context.user_data.get("location")
    condition_raw = context.user_data.get("condition", "cond_any")
    purpose = context.user_data.get("purpose", "self")

    cond_map = {
        "cond_new": "new", "cond_likenew": "like_new",
        "cond_used": "used", "cond_any": "any",
    }
    cond_label = {
        "cond_new": "Новый", "cond_likenew": "Как новый",
        "cond_used": "Б/у", "cond_any": "Любое",
    }
    purp_label = {"self": "Для себя", "deal": "Дешевле рынка", "resale": "Перепродажа"}

    query_obj = SearchQuery(
        user_id=user_row["id"],
        query=q,
        keywords=q.split(),
        max_price=float(max_price) if max_price else None,
        location=location,
        condition=cond_map.get(condition_raw, "any"),
        purpose=purpose,
    )
    DB.create_search(query_obj)

    price_line = f"до {max_price:,.0f} ₽" if max_price else "без ограничений"
    loc_line = location or "везде"

    text = (
        "🎯 <b>Охота создана!</b>\n\n"
        f"<b>Товар:</b> <code>{q}</code>\n"
        f"<b>Бюджет:</b> {price_line}\n"
        f"<b>Регион:</b> {loc_line}\n"
        f"<b>Состояние:</b> {cond_label.get(condition_raw, 'Любое')}\n"
        f"<b>Цель:</b> {purp_label.get(purpose, 'Для себя')}\n\n"
        "<i>AI будет проверять рынок автоматически.\n"
        "Пришлю уведомление, когда найду выгодное предложение.</i>"
    )

    await update.effective_message.reply_text(
        text,
        parse_mode="HTML",
        reply_markup=_kb(
            [_btn("🎯 Новая охота", "menu_search")],
            [_btn("📋 Мои охоты", "menu_hunts")],
            _home_row(),
        ),
    )
    context.user_data.clear()


async def _skip_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await _ask_location(update)
    return WAIT_LOCATION


async def cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data.clear()
    await _edit(
        update,
        "🔍 Поиск отменён.",
        _kb([_btn("🔍 Новый поиск", "menu_search")], _home_row()),
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
#  MY HUNTS
# ═══════════════════════════════════════════════════════════════════════════════

async def show_hunts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    searches = DB.get_user_searches(user_id)
    active = [s for s in searches if s["active"]]

    if not active:
        await _edit(
            update,
            "🎯 <b>Мои охоты</b>\n\nУ вас пока нет активных охот.\nСоздайте первую!",
            _kb([_btn("🔍 Создать охоту", "menu_search")], _home_row()),
        )
        return

    lines = ["🎯 <b>Мои охоты</b>\n"]
    buttons = []

    for s in active[:10]:
        price_str = f"до {s['max_price']:,.0f} ₽" if s.get("max_price") else "любая цена"
        loc_str = s.get("location") or "везде"
        st = DB.get_search_stats(s["id"])
        lines.append(
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"🎯 <b>{s['query'][:50]}</b>\n"
            f"   💰 {price_str} · 📍 {loc_str}\n"
            f"   🟢 Активна · 🔥 Находок: {st['good_deals']}\n"
        )
        buttons.append([_btn(f"▶ {s['query'][:28]}", f"hunt_open_{s['id']}")])

    buttons += [
        [_btn("🔍 Новая охота", "menu_search")],
        _home_row(),
    ]

    await _edit(update, "\n".join(lines), _kb(*buttons))


async def show_hunt_detail(update: Update, search_id: int):
    searches = DB.get_active_searches()
    s = next((x for x in searches if x["id"] == search_id), None)
    if not s:
        await _edit(update, "Охота не найдена.", _kb(_home_row()))
        return

    st = DB.get_search_stats(search_id)
    price_str = f"до {s['max_price']:,.0f} ₽" if s.get("max_price") else "любая цена"
    loc_str = s.get("location") or "везде"

    cond_labels = {"new": "Новый", "like_new": "Как новый", "used": "Б/у", "any": "Любое"}
    purp_labels = {"self": "Для себя", "deal": "Дешевле рынка", "resale": "Перепродажа"}

    text = (
        f"🎯 <b>{s['query']}</b>\n\n"
        f"💰 Бюджет: {price_str}\n"
        f"📍 Регион: {loc_str}\n"
        f"📦 Состояние: {cond_labels.get(s.get('condition', 'any'), 'Любое')}\n"
        f"🎯 Цель: {purp_labels.get(s.get('purpose', 'self'), 'Для себя')}\n\n"
        f"<b>━━━━━━━━━━━━━━━━━</b>\n"
        f"🟢 Статус: Активна\n"
        f"🔍 Всего найдено: <b>{st['total']}</b>\n"
        f"🔥 Выгодных: <b>{st['good_deals']}</b>"
    )

    kb = _kb(
        [
            _btn("⏸ Пауза", f"hunt_pause_{search_id}"),
            _btn("❌ Удалить", f"hunt_delete_{search_id}"),
        ],
        [_btn("📋 Все охоты", "menu_hunts")],
        _home_row(),
    )
    await _edit(update, text, kb)


# ═══════════════════════════════════════════════════════════════════════════════
#  BEST FINDS
# ═══════════════════════════════════════════════════════════════════════════════

async def show_finds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    page = context.user_data.get("finds_page", 0)
    alerts = DB.get_recent_alerts(user_id, limit=50)

    if not alerts:
        await _edit(
            update,
            "🔍 <b>Находки</b>\n\nПока нет находок.\nСоздайте охоту — и я начну искать!",
            _kb([_btn("🔍 Новая охота", "menu_search")], _home_row()),
        )
        return

    chunk = alerts[page: page + 3]
    if not chunk:
        context.user_data["finds_page"] = 0
        chunk = alerts[:3]
        page = 0

    # Navigation header
    total_pages = (len(alerts) + 2) // 3
    current_page = page // 3 + 1
    header_text = f"🔥 <b>Лучшие находки</b>  [{current_page}/{total_pages}]\n"
    await _edit(update, header_text, _kb(_home_row()))

    for a in chunk:
        why_good = a.get("ai_why_good") or []
        risks = a.get("ai_risks") or []

        # Fallback why_good from heuristics
        if not why_good:
            if (a.get("price_delta_pct") or 0) < -10:
                why_good.append("цена ниже рынка")
            if a.get("seller_rating") and a["seller_rating"] > 4.5:
                why_good.append("хороший продавец")
            images = a.get("images") or []
            if len(images) >= 3:
                why_good.append("есть реальные фото")

        card = format_alert(
            title=a.get("title", ""),
            price=a.get("price", 0),
            market_price=a.get("market_price") or a.get("price", 0),
            deal_score=a.get("deal_score", 0),
            price_delta_pct=a.get("price_delta_pct", 0),
            risk_score=a.get("risk_score", 50),
            recommendation=a.get("recommendation", "maybe"),
            ai_explanation=a.get("ai_explanation") or "",
            ai_why_good=why_good,
            ai_risks=risks,
        )

        listing_id = a.get("listing_id") or a.get("id", 0)
        analysis_id = a.get("analysis_id", 0)
        url = a.get("url", "")

        kb_rows = []
        if url:
            kb_rows.append([_url_btn("🔗 Открыть объявление", url)])
        kb_rows.append([
            _btn("⭐ Сохранить", f"find_save_{listing_id}_{analysis_id}"),
            _btn("❌ Не интересно", f"find_skip_{listing_id}"),
        ])

        await update.effective_message.reply_text(
            card, parse_mode="HTML",
            reply_markup=_kb(*kb_rows),
            disable_web_page_preview=True,
        )

    # Navigation
    nav_rows = []
    if page > 0:
        nav_rows.append(_btn("◀ Назад", f"finds_page_{max(0, page - 3)}"))
    if page + 3 < len(alerts):
        nav_rows.append(_btn("▶ Ещё", f"finds_page_{page + 3}"))

    footer_kb = _kb(nav_rows, [_btn("⭐ Сохранённые", "menu_saved")], _home_row()) if nav_rows else _kb(
        [_btn("⭐ Сохранённые", "menu_saved")], _home_row()
    )
    await update.effective_message.reply_text(
        "Выберите действие:", reply_markup=footer_kb
    )


async def save_find(update: Update, context: ContextTypes.DEFAULT_TYPE, data: str):
    """Save a find to favorites."""
    user_id = _get_user_id(update)
    try:
        _, listing_id, analysis_id = data.rsplit("_", 2)
        ok = DB.save_find(user_id, int(listing_id), int(analysis_id))
        await update.callback_query.answer(
            "⭐ Сохранено!" if ok else "Уже сохранено", show_alert=False
        )
    except Exception:
        await update.callback_query.answer("Ошибка сохранения", show_alert=False)


async def show_saved_finds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    saved = DB.get_saved_finds(user_id, limit=10)

    if not saved:
        await _edit(
            update,
            "⭐ <b>Сохранённые находки</b>\n\nСписок пуст. Сохраняйте интересные предложения!",
            _kb([_btn("🔥 Находки", "menu_finds")], _home_row()),
        )
        return

    lines = ["⭐ <b>Сохранённые находки</b>\n"]
    for s in saved:
        delta = s.get("price_delta_pct", 0)
        lines.append(
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"<b>{s['title'][:60]}</b>\n"
            f"💰 {s['price']:,.0f} ₽ · 📊 {delta:+.0f}% от рынка\n"
        )

    await _edit(
        update, "\n".join(lines),
        _kb([_btn("🔥 Все находки", "menu_finds")], _home_row()),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  MARKET RADAR
# ═══════════════════════════════════════════════════════════════════════════════

async def show_radar(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)

    # Try to get cached radar from DB first
    radar_items = DB.get_latest_radar(user_id, limit=6)

    if not radar_items:
        # Check if user has any searches
        searches = DB.get_user_searches(user_id)
        if not searches:
            await _edit(
                update,
                "📡 <b>Market Radar</b>\n\n"
                "Создайте хотя бы одну охоту — и я начну отслеживать рынок по вашим категориям.",
                _kb([_btn("🔍 Создать охоту", "menu_search")], _home_row()),
            )
            return
        await _edit(
            update,
            "📡 <b>Market Radar</b>\n\n⏳ Данные ещё накапливаются...\n\n"
            "<i>Радар заработает после первых проверок рынка.</i>",
            _kb(_home_row()),
        )
        return

    lines = ["📡 <b>Market Radar</b>\n<i>Ваш рынок прямо сейчас</i>\n"]

    for item in radar_items:
        emoji = item.get("trend_emoji", "→")
        category = item.get("category", "")
        avg_price = item.get("avg_price", 0)
        trend_pct = item.get("trend_pct", 0)
        hot = item.get("hot_deals_count", 0)
        comment = item.get("ai_comment", "")

        price_str = f"~{avg_price:,.0f} ₽" if avg_price else ""
        trend_str = f"{trend_pct:+.1f}%" if trend_pct != 0 else ""
        hot_str = f"🔥 {hot} горячих" if hot else ""

        meta = " · ".join(x for x in [price_str, trend_str, hot_str] if x)

        lines.append(
            f"<b>━━━━━━━━━━━━━━━━━</b>\n"
            f"{emoji} <b>{category[:40]}</b>\n"
            f"   {meta}\n"
            + (f"   <i>{comment}</i>\n" if comment else "")
        )

    lines.append("\n<i>Обновляется каждый час</i>")

    await _edit(
        update, "\n".join(lines),
        _kb([_btn("🔄 Обновить", "menu_radar")], _home_row()),
    )


# ═══════════════════════════════════════════════════════════════════════════════
#  STATISTICS
# ═══════════════════════════════════════════════════════════════════════════════

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    stats = DB.get_user_stats(user_id)

    text = (
        "📊 <b>Ваша статистика</b>\n\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n\n"
        f"🔎 Всего найдено: <b>{stats['total_alerts']}</b>\n"
        f"🔥 Выгодных сделок: <b>{stats['good_deals']}</b>\n"
        f"⭐ Сохранено: <b>{stats['saved_finds']}</b>\n"
        f"🎯 Активных охот: <b>{stats['active_searches']}</b>\n"
        f"📉 Средняя экономия: <b>{stats['avg_savings']}%</b>\n\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<b>Сегодня:</b>\n"
        f"🔎 Проверено: <b>{stats['today_checked']}</b>\n"
        f"🔥 Выгодных: <b>{stats['today_good']}</b>\n\n"
        "<i>Чем больше охот — тем точнее AI рекомендации.</i>"
    )

    kb = _kb(
        [_btn("🎯 Включить Hunter Mode", "hunter_on")],
        [_btn("📡 Market Radar", "menu_radar")],
        _home_row(),
    )
    await _edit(update, text, kb)


# ═══════════════════════════════════════════════════════════════════════════════
#  HUNTER MODE
# ═══════════════════════════════════════════════════════════════════════════════

async def set_hunter(update: Update, context: ContextTypes.DEFAULT_TYPE, enabled: bool):
    user_id = _get_user_id(update)
    DB.upsert_user_settings(user_id, hunter_enabled=1 if enabled else 0)

    if enabled:
        text = (
            "🎯 <b>Hunter Mode включён!</b>\n\n"
            "Я буду самостоятельно искать выгодные предложения\n"
            "и присылать только лучшие.\n\n"
            "<i>Работаю над вашими активными охотами...</i>"
        )
        kb = _kb(
            [_btn("⚙️ Настройки охоты", "settings_hunter")],
            [_btn("🔕 Отключить", "hunter_off")],
            _home_row(),
        )
    else:
        text = (
            "🔕 <b>Hunter Mode отключён.</b>\n\n"
            "Я больше не буду присылать автоматические уведомления."
        )
        kb = _kb(
            [_btn("🎯 Включить", "hunter_on")],
            _home_row(),
        )

    await _edit(update, text, kb)


# ═══════════════════════════════════════════════════════════════════════════════
#  SETTINGS
# ═══════════════════════════════════════════════════════════════════════════════

async def show_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    s = DB.get_user_settings(user_id)

    hunter_status = "🟢 Вкл" if s.get("hunter_enabled") else "⚪ Выкл"
    notif_status = "🔔 Вкл" if s.get("notifications_enabled", 1) else "🔕 Выкл"

    ai_prov = s.get("ai_provider", "") or settings.ai_provider
    from ai.factory import provider_display_name
    ai_status = provider_display_name(ai_prov) if ai_prov else "⚙️ Не настроен"

    interval_min = s.get("hunter_interval_sec", 300) // 60
    min_savings = s.get("hunter_min_savings_pct", 10)

    text = (
        "⚙️ <b>Настройки</b>\n\n"
        "<b>━━━━━━━━━━━━━━━━━</b>\n\n"
        f"🎯 Hunter Mode: <b>{hunter_status}</b>\n"
        f"⏱ Частота проверки: <b>каждые {interval_min} мин</b>\n"
        f"📉 Мин. выгода: <b>{min_savings:.0f}%</b>\n\n"
        f"🤖 AI провайдер: <b>{ai_status}</b>\n\n"
        f"🔔 Уведомления: <b>{notif_status}</b>\n\n"
        "<b>━━━━━━━━━━━━━━━━━</b>"
    )

    kb = _kb(
        [_btn("🎯 Hunter Mode", "settings_hunter")],
        [_btn("🤖 AI провайдер", "settings_ai_menu")],
        [_btn(f"🔔 Уведомления ({notif_status})", "settings_notifications")],
        _home_row(),
    )
    await _edit(update, text, kb)


async def show_hunter_settings(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    s = DB.get_user_settings(user_id)

    interval_sec = s.get("hunter_interval_sec", 300)
    min_savings = s.get("hunter_min_savings_pct", 10)
    enabled = bool(s.get("hunter_enabled", 0))

    text = (
        "🎯 <b>Настройки Hunter Mode</b>\n\n"
        f"Статус: {'🟢 Активен' if enabled else '⚪ Выключен'}\n\n"
        "<b>Частота проверки:</b>"
    )

    interval_kb = [
        _btn(f"{'✅ ' if interval_sec == 300 else ''}5 мин", "set_hunter_interval_300"),
        _btn(f"{'✅ ' if interval_sec == 900 else ''}15 мин", "set_hunter_interval_900"),
        _btn(f"{'✅ ' if interval_sec == 3600 else ''}1 час", "set_hunter_interval_3600"),
    ]

    text += "\n\n<b>Минимальная выгода для уведомления:</b>"

    savings_kb = [
        _btn(f"{'✅ ' if min_savings == 10 else ''}10%", "set_hunter_min_10"),
        _btn(f"{'✅ ' if min_savings == 20 else ''}20%", "set_hunter_min_20"),
        _btn(f"{'✅ ' if min_savings == 30 else ''}30%", "set_hunter_min_30"),
    ]

    toggle_label = "🔕 Выключить" if enabled else "🎯 Включить"
    toggle_action = "hunter_off" if enabled else "hunter_on"

    kb = _kb(
        interval_kb,
        savings_kb,
        [_btn(toggle_label, toggle_action)],
        [_btn("◀ Назад", "menu_settings")],
        _home_row(),
    )
    await _edit(update, text, kb)


async def set_hunter_interval(update: Update, context: ContextTypes.DEFAULT_TYPE, sec: int):
    user_id = _get_user_id(update)
    DB.upsert_user_settings(user_id, hunter_interval_sec=sec)
    await update.callback_query.answer(f"✅ Интервал: {sec // 60} мин", show_alert=False)
    await show_hunter_settings(update, context)


async def set_hunter_min(update: Update, context: ContextTypes.DEFAULT_TYPE, pct: float):
    user_id = _get_user_id(update)
    DB.upsert_user_settings(user_id, hunter_min_savings_pct=pct)
    await update.callback_query.answer(f"✅ Мин. выгода: {pct:.0f}%", show_alert=False)
    await show_hunter_settings(update, context)


async def toggle_notifications(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    s = DB.get_user_settings(user_id)
    current = s.get("notifications_enabled", 1)
    new_val = 0 if current else 1
    DB.upsert_user_settings(user_id, notifications_enabled=new_val)
    status = "включены 🔔" if new_val else "выключены 🔕"
    await update.callback_query.answer(f"Уведомления {status}", show_alert=False)
    await show_settings(update, context)


# ── AI Settings ───────────────────────────────────────────────────────────────

async def show_ai_settings(update: Update, context: ContextTypes.DEFAULT_TYPE, sub: str = "menu"):
    user_id = _get_user_id(update)
    s = DB.get_user_settings(user_id)
    current = s.get("ai_provider", "") or settings.ai_provider
    current_model = s.get("ai_model", "") or settings.ai_model

    from ai.factory import provider_display_name, provider_model_hint

    model_hint = provider_model_hint(current) if current else ""
    model_line = f"\nМодель: <code>{current_model}</code>" if current_model else ""

    text = (
        "🤖 <b>AI Провайдер</b>\n\n"
        f"Текущий: <b>{provider_display_name(current) if current else 'Не настроен'}</b>"
        f"{model_line}\n\n"
        "Выберите AI провайдера для анализа объявлений.\n"
        "<i>Без AI система работает на эвристиках.</i>\n\n"
        "<b>Что даёт AI:</b>\n"
        "✅ Объяснение каждой находки\n"
        "✅ Оценка рисков продавца\n"
        "✅ Market Radar с комментариями\n"
        "✅ Умный парсинг ваших запросов"
        + (f"\n\n<i>{model_hint}</i>" if model_hint else "")
    )

    def mark(p: str) -> str:
        return "✅ " if current == p else ""

    kb = _kb(
        [_btn(f"{mark('wormsoft')}🦾 WormSoft AI", "set_ai_provider_wormsoft")],
        [_btn(f"{mark('openai')}🤖 OpenAI GPT", "set_ai_provider_openai")],
        [_btn(f"{mark('gemini')}✨ Google Gemini", "set_ai_provider_gemini")],
        [_btn(f"{mark('anthropic')}🔮 Claude", "set_ai_provider_anthropic")],
        [_btn(f"{mark('')}⚙️ Без AI", "set_ai_provider_none")],
        [_btn("◀ Назад", "menu_settings")],
    )
    await _edit(update, text, kb)


async def _ask_wormsoft_key(update: Update):
    """Show the API key input prompt for WormSoft."""
    await update.effective_message.edit_text(
        "🔑 <b>API ключ WormSoft</b>\n\n"
        "Введите ваш API ключ.\n\n"
        "<i>Где получить: ai.wormsoft.ru</i>",
        parse_mode="HTML",
        reply_markup=_kb([_btn("🚫 Отмена", "settings_ai_menu")]),
    )


async def set_ai_provider(update: Update, context: ContextTypes.DEFAULT_TYPE, provider: str):
    user_id = _get_user_id(update)

    if provider == "none":
        DB.upsert_user_settings(user_id, ai_provider="", ai_api_key="", ai_model="")
        await update.callback_query.answer("AI отключён", show_alert=False)
        await show_ai_settings(update, context)
        return

    # WormSoft: ask model first, then API key
    if provider == "wormsoft":
        context.user_data["pending_ai_provider"] = provider
        await _edit(
            update,
            "🦾 <b>WormSoft AI</b>\n\n"
            "Выберите модель:\n\n"
            "<b>Low</b> — быстрая и дешёвая (рекомендуется)\n"
            "<b>Medium</b> — точнее, подходит для сложных анализов",
            _kb(
                [_btn("⚡ Low (быстрая)", "wormsoft_model_low")],
                [_btn("🎯 Medium (точная)", "wormsoft_model_medium")],
                [_btn("🚫 Отмена", "settings_ai_menu")],
            ),
        )
        return WAIT_AI_KEY

    # Other providers: ask for API key
    context.user_data["pending_ai_provider"] = provider

    provider_names = {
        "openai": "OpenAI",
        "gemini": "Google Gemini",
        "anthropic": "Anthropic Claude",
    }
    name = provider_names.get(provider, provider)

    instructions = {
        "openai": "platform.openai.com → API Keys",
        "gemini": "aistudio.google.com → Get API Key",
        "anthropic": "console.anthropic.com → API Keys",
    }

    await _edit(
        update,
        f"🔑 <b>API ключ для {name}</b>\n\n"
        f"Введите ваш API ключ.\n\n"
        f"<i>Где получить: {instructions.get(provider, '')}</i>",
        _kb([_btn("🚫 Отмена", "settings_ai_menu")]),
    )
    return WAIT_AI_KEY


async def got_ai_key(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Received AI API key from user."""
    user_id = _get_user_id(update)
    provider = context.user_data.pop("pending_ai_provider", "")
    api_key = update.message.text.strip()

    if not provider or not api_key:
        await update.message.reply_text(
            "❌ Ошибка. Попробуйте ещё раз.",
            reply_markup=_kb([_btn("◀ Настройки", "menu_settings")]),
        )
        return ConversationHandler.END

    # Validate key format (basic check)
    if len(api_key) < 20:
        await update.message.reply_text(
            "❌ Ключ слишком короткий. Проверьте и попробуйте снова.",
            reply_markup=_kb([_btn("◀ Назад", "settings_ai_menu")]),
        )
        return WAIT_AI_KEY

    DB.upsert_user_settings(user_id, ai_provider=provider, ai_api_key=api_key, ai_model=model)

    from ai.factory import get_user_ai_provider, provider_display_name
    s = DB.get_user_settings(user_id)

    # Test the key
    test_ok = False
    try:
        prov = get_user_ai_provider(s)
        if prov and prov.is_available:
            test_ok = True
    except Exception:
        pass

    status = "✅ Ключ сохранён и проверен!" if test_ok else "✅ Ключ сохранён."

    await update.message.reply_text(
        f"{status}\n\n"
        f"🤖 AI провайдер: <b>{provider_display_name(provider)}</b>\n\n"
        "Теперь все находки будут анализироваться с помощью AI.",
        parse_mode="HTML",
        reply_markup=_kb([_btn("◀ Настройки", "menu_settings")], _home_row()),
    )
    return ConversationHandler.END


# ═══════════════════════════════════════════════════════════════════════════════
#  PUBLIC NOTIFICATION API (called by collector/scheduler)
# ═══════════════════════════════════════════════════════════════════════════════

async def send_deal_alert(
    app: "Application",
    telegram_id: int,
    alert_data: dict,
):
    """Send a deal alert to a user. Called externally by the scheduler."""
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
    confidence = alert_data.get("ai_score") or deal_score

    card = format_alert(
        title=title, price=price, market_price=market_price,
        deal_score=deal_score, price_delta_pct=price_delta_pct,
        risk_score=risk_score, recommendation=recommendation,
        ai_explanation=ai_explanation, ai_why_good=ai_why_good,
        ai_risks=ai_risks,
    )

    header = (
        "🔥 <b>Новая находка!</b>\n\n"
        f"Уверенность: <b>{confidence:.0f}%</b>\n"
        f"Рекомендация: {'🟢 Стоит посмотреть' if recommendation == 'buy' else '🟡 Интересно'}\n\n"
    )

    kb_rows = []
    if url:
        kb_rows.append([_url_btn("🔗 Открыть объявление", url)])
    kb_rows.append([_btn("🏠 В меню", "menu_home")])

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


# ═══════════════════════════════════════════════════════════════════════════════
#  CONVERSATION HANDLERS
# ═══════════════════════════════════════════════════════════════════════════════

search_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_search, pattern="^menu_search$")],
    states={
        WAIT_QUERY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_query),
            CallbackQueryHandler(cancel_search, pattern="^search_cancel$"),
        ],
        WAIT_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_price),
            CallbackQueryHandler(_skip_price, pattern="^price_skip$"),
        ],
        WAIT_LOCATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_location_text),
            CallbackQueryHandler(_set_location, pattern="^loc_"),
        ],
        WAIT_CONDITION: [
            CallbackQueryHandler(got_condition, pattern="^cond_"),
        ],
        WAIT_PURPOSE: [
            CallbackQueryHandler(got_purpose, pattern="^purp_"),
        ],
    },
    fallbacks=[CallbackQueryHandler(cancel_search, pattern="^search_cancel$")],
    per_message=False,
)

ai_key_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(set_ai_provider, pattern="^set_ai_provider_(?!none)")],
    states={
        WAIT_AI_KEY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_ai_key),
            CallbackQueryHandler(show_ai_settings, pattern="^settings_ai_menu$"),
        ],
    },
    fallbacks=[CallbackQueryHandler(show_settings, pattern="^menu_settings$")],
    per_message=False,
)


# ═══════════════════════════════════════════════════════════════════════════════
#  BOT RUNNER
# ═══════════════════════════════════════════════════════════════════════════════

class MarketAgentBot:
    """Market Agent Telegram Bot runner."""

    def __init__(self, db: Database = DB):
        self.db = db
        self._app: Optional[Application] = None

    def build_app(self) -> Application:
        if not settings.telegram_bot_token:
            raise ValueError("MA_TELEGRAM_BOT_TOKEN not set")

        app = Application.builder().token(settings.telegram_bot_token).build()

        # Commands (admin only — users see inline buttons)
        app.add_handler(CommandHandler("start", cmd_start))
        app.add_handler(CommandHandler("menu", cmd_start))

        # Conversations (order matters — more specific first)
        app.add_handler(ai_key_conversation)
        app.add_handler(search_conversation)

        # Generic callback fallback
        app.add_handler(CallbackQueryHandler(handle_callback))

        self._app = app
        return app

    def start(self):
        app = self.build_app()
        log.info("Market Agent Bot v2 started — polling...")
        app.run_polling(allowed_updates=Update.ALL_TYPES)

    @property
    def app(self) -> Optional[Application]:
        return self._app
