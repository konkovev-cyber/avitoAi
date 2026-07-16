"""Telegram Bot — personal AI marketplace agent. Premium UX."""

from __future__ import annotations

import logging
from datetime import datetime, timezone
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

# Conversation states
WAIT_QUERY, WAIT_PRICE, WAIT_LOCATION, WAIT_CONDITION = range(4)

DB = Database()


def _get_user_id(update: Update) -> int:
    user = update.effective_user
    DB.upsert_user(telegram_id=user.id, username=user.username or user.full_name)
    row = DB.get_user_by_telegram(user.id)
    return row["id"] if row else 0


# ═══════════════════════════════════════════════
#  MAIN MENU
# ═══════════════════════════════════════════════

async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Show main dashboard."""
    _get_user_id(update)
    await show_main_menu(update, context)


async def show_main_menu(update: Update | None, context, edit: bool = False):
    chat_id = update.effective_chat.id if update else context.user_data.get("chat_id")
    if not chat_id:
        return

    stats = _user_stats(_get_user_id(update))
    text = (
        "🤖 <b>Market Agent</b>\n"
        "Ваш личный охотник за выгодными предложениями\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"🟢 Агент работает\n\n"
        f"<b>Сегодня:</b>\n"
        f"🔎 Проверено: <b>{stats['total_listings']}</b> объявлений\n"
        f"🔥 Найдено выгодных: <b>{stats['good_deals']}</b>\n"
        f"📉 Средняя экономия: <b>{stats['avg_savings']}</b>\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━━━━━</b>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🔍 Новый поиск", callback_data="menu_search")],
        [
            InlineKeyboardButton("🎯 Мои охоты", callback_data="menu_hunts"),
            InlineKeyboardButton("🔥 Находки", callback_data="menu_finds"),
        ],
        [
            InlineKeyboardButton("📊 Статистика", callback_data="menu_stats"),
        ],
    ])

    method = update.message.edit_text if edit else update.message.reply_text
    await method(chat_id=chat_id, text=text, parse_mode="HTML", reply_markup=kb)


# ═══════════════════════════════════════════════
#  BUTTON HANDLER
# ═══════════════════════════════════════════════

async def handle_callback(update: Update, context: ContextTypes.DEFAULT_TYPE):
    query = update.callback_query
    await query.answer()
    data = query.data
    chat_id = update.effective_chat.id
    _get_user_id(update)

    if data == "menu_search":
        await start_search(update, context)

    elif data == "menu_hunts":
        await show_hunts(update, context)

    elif data == "menu_finds":
        await show_finds(update, context)

    elif data == "menu_stats":
        await show_stats(update, context)

    elif data.startswith("hunt_open_"):
        search_id = int(data[len("hunt_open_"):])
        await show_hunt_detail(update, search_id)

    elif data.startswith("hunt_pause_"):
        search_id = int(data[len("hunt_pause_"):])
        DB.deactivate_search(search_id)
        await show_hunts(update, context)

    elif data.startswith("hunt_delete_"):
        search_id = int(data[len("hunt_delete_"):])
        DB.deactivate_search(search_id)
        await show_hunts(update, context)

    elif data.startswith("find_next_"):
        finds = context.user_data.get("finds_page", 0)
        context.user_data["finds_page"] = finds + 5
        await show_finds(update, context)

    elif data == "menu_home":
        await show_main_menu(update, context, edit=True)

    elif data == "search_cancel":
        context.user_data.clear()
        await query.message.edit_text(
            "🔍 Поиск отменён. Чтобы создать новый, нажмите кнопку в меню.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")]
            ]),
        )

    # Hunter mode
    elif data == "hunter_on":
        context.user_data["hunter_mode"] = True
        await query.edit_message_text(
            "🎯 <b>Режим охотника включён!</b>\n\n"
            "Я буду самостоятельно искать выгодные предложения и присылать только лучшие.\n\n"
            "Сейчас работаю над вашими активными охотами.",
            parse_mode="HTML",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔕 Отключить", callback_data="hunter_off")],
                [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
            ]),
        )

    elif data == "hunter_off":
        context.user_data["hunter_mode"] = False
        await query.edit_message_text(
            "🔕 Режим охотника отключён. Я больше не буду присылать автоматические уведомления.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🎯 Включить", callback_data="hunter_on")],
                [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
            ]),
        )


# ═══════════════════════════════════════════════
#  SEARCH DIALOG
# ═══════════════════════════════════════════════

async def start_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.edit_message_text(
        "🔍 <b>Новый поиск</b>\n\n"
        "Что будем искать?\n\n"
        "Например: <i>MacBook Pro M2, iPhone 15, RTX 4090</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🚫 Отмена", callback_data="search_cancel")]
        ]),
    )
    return WAIT_QUERY


async def got_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    context.user_data["query"] = update.message.text
    await update.message.reply_text(
        "💰 <b>Максимальная цена</b>\n\n"
        "Введите сумму в рублях или пропустите.\n\n"
        "Например: <i>90000</i>",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("⏭ Пропустить", callback_data="price_skip")]
        ]),
    )
    return WAIT_PRICE


async def got_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    try:
        price = int("".join(c for c in update.message.text if c.isdigit()))
        context.user_data["max_price"] = price
    except ValueError:
        pass
    await update.message.reply_text(
        "📍 <b>Город</b>\n\n"
        "Укажите город или пропустите для поиска везде.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇷🇺 Москва", callback_data="loc_msk")],
            [InlineKeyboardButton("🇷🇺 Санкт-Петербург", callback_data="loc_spb")],
            [InlineKeyboardButton("🌍 Везде", callback_data="loc_skip")],
        ]),
    )
    return WAIT_LOCATION


async def got_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    loc = update.message.text.strip() if update.message.text else None
    context.user_data["location"] = loc
    await show_condition_picker(update)
    return WAIT_CONDITION


async def got_condition(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Condition callback or text."""
    context.user_data["condition"] = update.callback_query.data if update.callback_query else "any"
    await create_hunt(update, context)
    return ConversationHandler.END


async def show_condition_picker(update: Update):
    """Show condition options."""
    chat_id = update.effective_chat.id if update.message else update.callback_query.message.chat.id
    method = update.effective_message.reply_text
    await method(
        text=(
            "📦 <b>Состояние</b>\n\n"
            "Какое состояние вас интересует?"
        ),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("✨ Новый", callback_data="cond_new")],
            [InlineKeyboardButton("👍 Как новый", callback_data="cond_likenew")],
            [InlineKeyboardButton("📦 Б/у", callback_data="cond_used")],
            [InlineKeyboardButton("⏭ Не важно", callback_data="cond_any")],
        ]),
    )


# ═══════════════════════════════════════════════
#  CREATE HUNT
# ═══════════════════════════════════════════════

async def create_hunt(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user = update.effective_user
    user_row = DB.get_user_by_telegram(user.id)
    if not user_row:
        await update.callback_query.message.edit_text("❌ Ошибка. Попробуйте /start")
        return

    q = context.user_data.get("query", "Поиск")
    max_price = context.user_data.get("max_price")
    location = context.user_data.get("location")
    condition = context.user_data.get("condition", "any")

    query_obj = SearchQuery(
        user_id=user_row["id"],
        query=q,
        keywords=q.split(),
        max_price=float(max_price) if max_price else None,
        location=location or None,
    )
    search_id = DB.create_search(query_obj)

    price_line = f"до {max_price:,.0f} ₽" if max_price else "без ограничений"
    loc_line = location or "везде"
    cond_map = {"cond_new": "Новый", "cond_likenew": "Как новый", "cond_used": "Б/у", "cond_any": "Любое"}
    cond_line = cond_map.get(condition, "Любое")

    cond_obj = {"condition": condition} if condition != "any" else {}

    text = (
        "🎯 <b>Охота создана!</b>\n\n"
        f"Товар: <code>{q}</code>\n"
        f"Бюджет: {price_line}\n"
        f"Регион: {loc_line}\n"
        f"Состояние: {cond_line}\n\n"
        f"<i>Я буду проверять новые объявления автоматически.</i>\n"
        f"<i>Пришлю уведомление, когда найду выгодное предложение.</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Новая охота", callback_data="menu_search")],
        [InlineKeyboardButton("📋 Все охоты", callback_data="menu_hunts")],
        [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
    ])

    await update.callback_query.message.edit_text(
        text=text, parse_mode="HTML", reply_markup=kb,
    )
    context.user_data.clear()


# ═══════════════════════════════════════════════
#  MY HUNTS
# ═══════════════════════════════════════════════

async def show_hunts(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    searches = DB.get_user_searches(user_id)
    active = [s for s in searches if s["active"]]

    if not active:
        await update.callback_query.edit_message_text(
            "🎯 У вас пока нет активных охот.\n\n"
            "Создайте первую — нажмите кнопку ниже.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Создать охоту", callback_data="menu_search")],
                [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
            ]),
        )
        return

    lines = ["🎯 <b>Мои охоты</b>\n"]
    buttons = []

    for s in active[:20]:
        price = f"до {s['max_price']:,.0f}₽" if s.get("max_price") else ""
        lines.append(
            f"<b>━━━━━━━━━━━━━━━━━━━</b>\n"
            f"🎯 <b>{s['query'][:60]}</b>\n"
            f"   {price} | Статус: 🟢 Активна\n"
        )
        buttons.append([
            InlineKeyboardButton(
                f"▶ {s['query'][:30]}",
                callback_data=f"hunt_open_{s['id']}",
            ),
        ])

    buttons.append([InlineKeyboardButton("🔍 Новая охота", callback_data="menu_search")])
    buttons.append([InlineKeyboardButton("🏠 В меню", callback_data="menu_home")])

    await update.callback_query.edit_message_text(
        text="\n".join(lines),
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup(buttons),
    )


async def show_hunt_detail(update: Update, search_id: int):
    searches = DB.get_active_searches()
    s = next((x for x in searches if x["id"] == search_id), None)
    if not s:
        await update.callback_query.edit_message_text("Охота не найдена.")
        return

    alerts = DB.get_recent_alerts(DB.get_user_by_telegram(update.effective_user.id)["id"], limit=3)
    hunting = [a for a in alerts if a.get("search_id") == search_id]

    text = (
        f"🎯 <b>{s['query']}</b>\n\n"
        f"💰 До {s['max_price']:,.0f} ₽\n"
        f"🟢 Активна\n\n"
        f"🔥 Находок: {len(hunting)}\n"
    )

    kb = InlineKeyboardMarkup([
        [
            InlineKeyboardButton("⏸ Пауза", callback_data=f"hunt_pause_{search_id}"),
            InlineKeyboardButton("❌ Удалить", callback_data=f"hunt_delete_{search_id}"),
        ],
        [InlineKeyboardButton("📋 Все охоты", callback_data="menu_hunts")],
        [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
    ])

    await update.callback_query.edit_message_text(
        text=text, parse_mode="HTML", reply_markup=kb,
    )


# ═══════════════════════════════════════════════
#  FINDS
# ═══════════════════════════════════════════════

async def show_finds(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    offset = context.user_data.get("finds_page", 0)
    alerts = DB.get_recent_alerts(user_id, limit=20)

    if not alerts:
        await update.callback_query.edit_message_text(
            "🔍 Пока нет находок.\n\n"
            "Создайте охоту — и я начну искать.",
            reply_markup=InlineKeyboardMarkup([
                [InlineKeyboardButton("🔍 Новая охота", callback_data="menu_search")],
                [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
            ]),
        )
        return

    # Get the requested slice
    page = alerts[offset:offset + 3]
    if not page:
        context.user_data["finds_page"] = 0
        page = alerts[:3]

    for a in page:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🔗 Открыть", url=f"{a.get('url', '')}")],
        ])
        text = _format_find_card(a)
        await update.callback_query.message.reply_text(
            text=text, parse_mode="HTML", reply_markup=kb, disable_web_page_preview=True,
        )

    # Show more button if needed
    if len(alerts) > offset + 3:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("⏩ Ещё", callback_data="find_next")],
            [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
        ])
        await update.callback_query.message.reply_text(
            "Больше находок ниже ⤵", reply_markup=kb,
        )
    else:
        kb = InlineKeyboardMarkup([
            [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
        ])
        await update.callback_query.message.reply_text(
            "Это все находки за сегодня.", reply_markup=kb,
        )


def _format_find_card(a: dict) -> str:
    """Format a single deal card beautifully."""
    title = a.get("title", "Без названия")[:80]
    price = a.get("price", 0)
    deal_score = a.get("deal_score", 0)
    price_delta = a.get("price_delta_pct", 0)
    recommendation = a.get("recommendation", "maybe")
    risk_score = a.get("risk_score", 0)

    emoji = "🔥" if deal_score >= 70 else "✅" if deal_score >= 50 else "ℹ️"
    rec_emoji = "🟢" if recommendation == "buy" else "🟡"

    # Top-level assessment
    if deal_score >= 80:
        assessment = "✦ Отличная цена на фоне рынка. Рекомендую посмотреть прямо сейчас."
    elif deal_score >= 60:
        assessment = "✦ Хороший вариант. Стоит обратить внимание."
    else:
        assessment = "✦ Интересно, но нужно проверить детали."

    return (
        f"{emoji} <b>{title}</b>\n\n"
        f"💰 <b>{price:,.0f} ₽</b>\n"
        f"📊 Рынок: <b>{(price / (1 + price_delta/100)):,.0f} ₽</b>\n"
        f"📉 Отклонение: <b>{price_delta:+.0f}%</b>\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━</b>\n"
        f"⭐ Оценка: <b>{deal_score:.0f}/100</b>\n"
        f"🎯 Риск: <b>{risk_score:.0f}/100</b>\n"
        f"{rec_emoji} {assessment}\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━</b>"
    )


# ═══════════════════════════════════════════════
#  STATS
# ═══════════════════════════════════════════════

async def show_stats(update: Update, context: ContextTypes.DEFAULT_TYPE):
    user_id = _get_user_id(update)
    stats = _user_stats(user_id)

    text = (
        "📊 <b>Ваша история</b>\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"🔎 Найдено предложений: <b>{stats['total_listings']}</b>\n"
        f"🔥 Выгодных находок: <b>{stats['good_deals']}</b>\n"
        f"📉 Средняя экономия: <b>{stats['avg_savings']}</b>\n"
        f"🎯 Активных охот: <b>{stats['active_searches']}</b>\n\n"
        f"<b>━━━━━━━━━━━━━━━━━━━</b>\n\n"
        f"<i>Чем больше данных — тем точнее мои рекомендации.</i>"
    )

    kb = InlineKeyboardMarkup([
        [InlineKeyboardButton("🎯 Включить охоту", callback_data="hunter_on")],
        [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
    ])

    await update.callback_query.edit_message_text(
        text=text, parse_mode="HTML", reply_markup=kb,
    )


def _user_stats(user_id: int) -> dict:
    """Compute user statistics."""
    conn = DB.connect()

    # Active searches
    active = conn.execute(
        "SELECT COUNT(*) FROM searches WHERE user_id = ? AND active = 1",
        (user_id,),
    ).fetchone()[0]

    # Total alerts
    total_alerts = conn.execute(
        "SELECT COUNT(*) FROM alerts WHERE user_id = ?", (user_id,),
    ).fetchone()[0]

    # Good deals (score >= 70)
    good = conn.execute(
        """SELECT COUNT(*) FROM alerts a
        JOIN analysis an ON a.analysis_id = an.id
        WHERE a.user_id = ? AND an.deal_score >= 70""",
        (user_id,),
    ).fetchone()[0]

    # Avg savings
    avg = conn.execute(
        """SELECT AVG(ABS(an.price_delta_pct))
        FROM alerts a
        JOIN analysis an ON a.analysis_id = an.id
        WHERE a.user_id = ? AND an.price_delta_pct < 0""",
        (user_id,),
    ).fetchone()[0] or 0

    return {
        "total_listings": total_alerts,
        "good_deals": good,
        "avg_savings": f"{abs(avg):.0f}%",
        "active_searches": active,
    }


# ═══════════════════════════════════════════════
#  CONVERSATION HELPERS (defined before handler)
# ═══════════════════════════════════════════════

async def _cancel_search(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    context.user_data.clear()
    await update.callback_query.edit_message_text(
        "🔍 Поиск отменён.",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🔍 Новый поиск", callback_data="menu_search")],
            [InlineKeyboardButton("🏠 В меню", callback_data="menu_home")],
        ]),
    )
    return ConversationHandler.END


async def _skip_price(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    await update.effective_message.edit_text(
        "📍 <b>Город</b>\n\nВыберите город для поиска.",
        parse_mode="HTML",
        reply_markup=InlineKeyboardMarkup([
            [InlineKeyboardButton("🇷🇺 Москва", callback_data="loc_msk")],
            [InlineKeyboardButton("🇷🇺 СПб", callback_data="loc_spb")],
            [InlineKeyboardButton("🌍 Везде", callback_data="loc_skip")],
        ]),
    )
    return WAIT_LOCATION


async def _set_location(update: Update, context: ContextTypes.DEFAULT_TYPE):
    await update.callback_query.answer()
    data = update.callback_query.data
    loc_map = {"loc_msk": "Москва", "loc_spb": "Санкт-Петербург", "loc_skip": None}
    context.user_data["location"] = loc_map.get(data)
    await show_condition_picker(update)
    return WAIT_CONDITION


# ═══════════════════════════════════════════════
#  CONVERSATION HANDLER
# ═══════════════════════════════════════════════

search_conversation = ConversationHandler(
    entry_points=[CallbackQueryHandler(start_search, pattern="^menu_search$")],
    states={
        WAIT_QUERY: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_query),
            CallbackQueryHandler(_cancel_search, pattern="^search_cancel$"),
        ],
        WAIT_PRICE: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_price),
            CallbackQueryHandler(_skip_price, pattern="^price_skip$"),
        ],
        WAIT_LOCATION: [
            MessageHandler(filters.TEXT & ~filters.COMMAND, got_location),
            CallbackQueryHandler(_set_location, pattern="^loc_"),
        ],
        WAIT_CONDITION: [
            CallbackQueryHandler(got_condition, pattern="^cond_"),
        ],
    },
    fallbacks=[CallbackQueryHandler(_cancel_search, pattern="^search_cancel$")],
)


# ═══════════════════════════════════════════════
#  RUNNER
# ═══════════════════════════════════════════════

class MarketAgentBot:
    def __init__(self, db: Database = DB):
        self.db = db
        self._app: Optional[Application] = None

    def start(self):
        if not settings.telegram_bot_token:
            log.error("TELEGRAM_BOT_TOKEN not set")
            return

        self._app = Application.builder().token(settings.telegram_bot_token).build()

        # Commands
        self._app.add_handler(CommandHandler("start", cmd_start))
        self._app.add_handler(CommandHandler("menu", cmd_start))

        # Conversation handler for creating a new search
        self._app.add_handler(search_conversation)

        # Callback handler for all inline buttons
        self._app.add_handler(CallbackQueryHandler(handle_callback))

        log.info("Bot v2 started (premium UX), polling...")
        self._app.run_polling(allowed_updates=Update.ALL_TYPES)
