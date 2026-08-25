#!/usr/bin/env python3
"""Interactive Telegram bot that watches Avito search filters for new
listings.

Any chat that talks to the bot can add its own filters (Avito search URLs
with whatever site filters they configured — city, price, category, ...),
each with its own check interval. A background job polls filters that are
due and pushes newly-seen listings to the owning chat.

Run: TELEGRAM_BOT_TOKEN=... python bot.py
"""
from __future__ import annotations

import asyncio
import html
import io
import json
import logging
import os
import re
import time
from pathlib import Path

from telegram import (
    BotCommand,
    InlineKeyboardButton,
    InlineKeyboardMarkup,
    InputFile,
    ReplyKeyboardMarkup,
    Update,
)
from telegram.constants import ParseMode
from telegram.ext import (
    Application,
    CallbackQueryHandler,
    CommandHandler,
    ContextTypes,
    ConversationHandler,
    MessageHandler,
    filters,
)

import avito_categories
import avito_client
from db import Database, Filter

BASE_DIR = Path(__file__).resolve().parent

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
DB_PATH = os.environ.get("AVITO_BOT_DB", str(BASE_DIR / "bot" / "avito_bot.db"))
POLL_INTERVAL_SECONDS = int(os.environ.get("AVITO_BOT_POLL_SECONDS", "60"))
DEFAULT_INTERVAL_MINUTES = int(os.environ.get("AVITO_DEFAULT_INTERVAL_MIN", "15"))
MIN_INTERVAL_MINUTES = int(os.environ.get("AVITO_MIN_INTERVAL_MIN", "5"))
MAX_FILTERS_PER_CHAT = int(os.environ.get("AVITO_MAX_FILTERS_PER_CHAT", "10"))
MAX_NOTIFY_PER_CHECK = int(os.environ.get("AVITO_MAX_NOTIFY_PER_CHECK", "15"))
ALERT_AFTER_FAILURES = int(os.environ.get("AVITO_ALERT_AFTER_FAILURES", "3"))
ALERT_COOLDOWN_SECONDS = int(os.environ.get("AVITO_ALERT_COOLDOWN_SECONDS", str(6 * 3600)))
AUTOPAUSE_AFTER_FAILURES = int(os.environ.get("AVITO_AUTOPAUSE_AFTER_FAILURES", "20"))

_allowed_raw = os.environ.get("AVITO_ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHAT_IDS: set[int] | None = (
    {int(x) for x in _allowed_raw.split(",") if x.strip()} if _allowed_raw else None
)

_admin_raw = os.environ.get("AVITO_ADMIN_CHAT_ID", "").strip()
ADMIN_CHAT_ID: int | None = int(_admin_raw) if _admin_raw else None

(
    ASK_NAME,
    ASK_URL,
    ADD_METHOD,
    PICK_CATEGORY,
    PICK_SUBCAT,
    PICK_CITY,
    ASK_KEYWORD,
    ASK_PRICE,
    PREVIEW,
    ASK_CUSTOM_NAME,
) = range(10)

MENU_ADD = "➕ Добавить фильтр"
MENU_LIST = "📋 Мои фильтры"
MENU_STATUS = "📊 Статус"
MENU_STATS = "📈 Статистика"
MENU_EXPORT = "📤 Экспорт"
MENU_HELP = "❓ Помощь"

# Populated at the bottom of the file, once the cmd_* functions it points
# to actually exist. Used to let a main-menu button tap interrupt an
# in-progress /addfilter wizard instead of being swallowed as free-text
# input for whatever step the wizard is waiting on.
MENU_HANDLERS: dict[str, ContextTypes.DEFAULT_TYPE] = {}


def main_menu_keyboard() -> ReplyKeyboardMarkup:
    return ReplyKeyboardMarkup(
        [[MENU_ADD, MENU_LIST], [MENU_STATUS, MENU_STATS], [MENU_EXPORT, MENU_HELP]],
        resize_keyboard=True,
    )

logging.basicConfig(
    format="%(asctime)s %(levelname)s %(name)s: %(message)s", level=logging.INFO
)
logging.getLogger("httpx").setLevel(logging.WARNING)
logger = logging.getLogger("avito_bot")

db = Database(DB_PATH)


def chat_allowed(chat_id: int) -> bool:
    return ALLOWED_CHAT_IDS is None or chat_id in ALLOWED_CHAT_IDS


async def guard(update: Update) -> bool:
    chat_id = update.effective_chat.id
    if not chat_allowed(chat_id):
        await update.effective_message.reply_text(
            "Этот бот настроен для ограниченного круга пользователей и недоступен вам."
        )
        return False
    return True


# ------------------------------------------------------------------ helpers

def format_listing_message(filter_name: str, listing: avito_client.Listing) -> str:
    title = html.escape(listing.title or "Без названия")
    price = f"{listing.price} ₽" if listing.price else "цена не указана"
    return (
        f"🆕 <b>{title}</b>\n"
        f"💰 {price}\n"
        f"🔎 Фильтр: {html.escape(filter_name)}\n"
        f"{html.escape(listing.url)}"
    )


def format_price_drop_message(filter_name: str, listing: avito_client.Listing, old_price: int) -> str:
    title = html.escape(listing.title or "Без названия")
    return (
        f"📉 <b>{title}</b>\n"
        f"Было: {old_price} ₽ → стало: {listing.price} ₽\n"
        f"🔎 Фильтр: {html.escape(filter_name)}\n"
        f"{html.escape(listing.url)}"
    )


async def send_notification(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, text: str, image: str, url: str
) -> None:
    keyboard = InlineKeyboardMarkup([[InlineKeyboardButton("🔗 Открыть на Avito", url=url)]])
    if image:
        try:
            await context.bot.send_photo(
                chat_id=chat_id,
                photo=image,
                caption=text,
                parse_mode=ParseMode.HTML,
                reply_markup=keyboard,
            )
            return
        except Exception:
            logger.warning("send_photo failed for %s, falling back to text", url)
    await context.bot.send_message(
        chat_id=chat_id,
        text=text,
        parse_mode=ParseMode.HTML,
        reply_markup=keyboard,
    )


async def send_listing(
    context: ContextTypes.DEFAULT_TYPE, chat_id: int, filter_name: str, listing: avito_client.Listing
) -> None:
    text = format_listing_message(filter_name, listing)
    await send_notification(context, chat_id, text, listing.image, listing.url)


async def send_price_drop(
    context: ContextTypes.DEFAULT_TYPE,
    chat_id: int,
    filter_name: str,
    listing: avito_client.Listing,
    old_price: int,
) -> None:
    text = format_price_drop_message(filter_name, listing, old_price)
    await send_notification(context, chat_id, text, listing.image, listing.url)


def filter_keyboard(f: Filter) -> InlineKeyboardMarkup:
    toggle = ("⏸ Пауза", f"pause:{f.id}") if f.active else ("▶️ Возобновить", f"resume:{f.id}")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Проверить сейчас", callback_data=f"check:{f.id}"),
                InlineKeyboardButton(toggle[0], callback_data=toggle[1]),
            ],
            [
                InlineKeyboardButton("⏱ Интервал", callback_data=f"interval:{f.id}"),
                InlineKeyboardButton("🗑 Удалить", callback_data=f"delrequest:{f.id}"),
            ],
        ]
    )


INTERVAL_PRESETS = [5, 15, 30, 60]


def interval_keyboard(f: Filter) -> InlineKeyboardMarkup:
    row = [
        InlineKeyboardButton(
            f"{m} мин" + (" ✓" if f.interval_minutes == m else ""),
            callback_data=f"setiv:{f.id}:{m}",
        )
        for m in INTERVAL_PRESETS
    ]
    return InlineKeyboardMarkup([row, [InlineKeyboardButton("‹ Назад", callback_data=f"back:{f.id}")]])


def describe_filter(f: Filter) -> str:
    if f.auto_paused:
        status = "⏸ автопауза (блокировка сайтом)"
    elif f.active:
        status = "🟢 активен"
    else:
        status = "⏸ на паузе"
    fail_note = ""
    if f.active and not f.auto_paused and f.consecutive_failures >= ALERT_AFTER_FAILURES:
        fail_note = " ⚠️ похоже на блокировку сайтом"
    last_found = (
        time.strftime("%d.%m %H:%M", time.localtime(f.last_found_at))
        if f.last_found_at
        else "пока не было"
    )
    extra = []
    if f.exclude_keyword_list():
        extra.append(f"исключая: {html.escape(', '.join(f.exclude_keyword_list()))}")
    if f.price_min or f.price_max:
        lo = f.price_min or "0"
        hi = f.price_max or "∞"
        extra.append(f"цена: {lo}–{hi} ₽")
    extra_line = f"\n{' · '.join(extra)}" if extra else ""
    return (
        f"<b>{html.escape(f.name)}</b> — {status}{fail_note}\n"
        f"Интервал: {f.interval_minutes} мин · найдено всего: {f.total_found}\n"
        f"Последняя находка: {last_found}{extra_line}\n"
        f"{html.escape(f.url)}"
    )


# ------------------------------------------------------------------ core check logic (shared by job + /check)

async def run_check(context: ContextTypes.DEFAULT_TYPE, f: Filter, notify_baseline: bool = False) -> str:
    """Fetch, diff against seen ids, notify chat about new listings.

    Returns a short human-readable result string.
    """
    loop = asyncio.get_running_loop()
    html_text, status = await loop.run_in_executor(None, avito_client.fetch, f.url)

    if html_text is None:
        db.mark_checked(f.id, success=False)
        updated = db.get_filter_by_id(f.id)
        now = time.time()

        if updated.consecutive_failures >= AUTOPAUSE_AFTER_FAILURES:
            db.set_auto_paused(f.id, True)
            await context.bot.send_message(
                chat_id=f.chat_id,
                text=(
                    f"⏸ Фильтр «{html.escape(f.name)}» автоматически поставлен на паузу "
                    f"после {updated.consecutive_failures} неудачных попыток подряд, "
                    f"чтобы не долбить сайт впустую. Когда решишь проблему (см. README про "
                    f"блокировку антиботом) — включи заново командой /resume {html.escape(f.name)}."
                ),
            )
            return f"автопауза после {updated.consecutive_failures} сбоев"

        if (
            updated.consecutive_failures >= ALERT_AFTER_FAILURES
            and now - updated.last_alert_at > ALERT_COOLDOWN_SECONDS
        ):
            await context.bot.send_message(
                chat_id=f.chat_id,
                text=(
                    f"⚠️ Фильтр «{html.escape(f.name)}» не удаётся загрузить "
                    f"{updated.consecutive_failures} раз подряд (похоже на блокировку "
                    f"антиботом Avito с этого IP). Последний статус ответа: {status}.\n"
                    f"Если это повторяется постоянно — запустите бота на другой машине "
                    f"(см. README)."
                ),
            )
            db.mark_alerted(f.id)
        return f"не удалось загрузить (status={status})"

    all_listings = avito_client.parse_listings(html_text)
    listings = avito_client.apply_client_filters(
        all_listings, f.exclude_keyword_list(), f.price_min, f.price_max
    )
    seen = db.get_seen_ids(f.id)
    prev_prices = db.get_seen_prices(f.id)
    is_first_run = len(seen) == 0
    new_listings = [item for item in listings if item.id not in seen]
    price_drops = [
        (item, int(prev_prices[item.id]))
        for item in listings
        if item.id in seen
        and item.price.isdigit()
        and prev_prices.get(item.id, "").isdigit()
        and int(item.price) < int(prev_prices[item.id])
    ]

    sent = 0
    if not is_first_run:
        to_send = list(reversed(new_listings))
        for item in to_send[:MAX_NOTIFY_PER_CHECK]:
            await send_listing(context, f.chat_id, f.name, item)
            sent += 1
            await asyncio.sleep(1)
        if len(to_send) > MAX_NOTIFY_PER_CHECK:
            await context.bot.send_message(
                chat_id=f.chat_id,
                text=(
                    f"…и ещё {len(to_send) - MAX_NOTIFY_PER_CHECK} новых объявлений по "
                    f"фильтру «{html.escape(f.name)}» — открой поиск на сайте, чтобы "
                    f"увидеть все."
                ),
            )
        for item, old_price in price_drops[:MAX_NOTIFY_PER_CHECK]:
            await send_price_drop(context, f.chat_id, f.name, item, old_price)
            sent += 1
            await asyncio.sleep(1)
    elif notify_baseline:
        await context.bot.send_message(
            chat_id=f.chat_id,
            text=(
                f"Фильтр «{html.escape(f.name)}» подключён, нашёл {len(listings)} "
                f"объявлений сейчас — это базовый срез, уведомлять буду только о новых."
            ),
        )

    db.record_seen(f.id, [(item.id, item.price) for item in all_listings])
    db.mark_checked(f.id, success=True, new_found=sent)
    return (
        f"ok, найдено {len(listings)}, новых отправлено {sent}, "
        f"снижений цены: {len(price_drops)}"
    )


async def poll_due_filters(context: ContextTypes.DEFAULT_TYPE) -> None:
    due = db.list_due_filters()
    if not due:
        return
    logger.info("polling %d due filter(s)", len(due))
    for f in due:
        try:
            result = await run_check(context, f)
            logger.info("[%s/%s] %s", f.chat_id, f.name, result)
        except Exception:
            logger.exception("check failed for filter id=%s", f.id)


# ------------------------------------------------------------------ commands

HELP_TEXT = (
    "Я слежу за поиском на Avito и присылаю новые объявления по твоим фильтрам.\n\n"
    "Основное управление — кнопками внизу экрана:\n"
    f"{MENU_ADD} — добавить фильтр (по категории или по ссылке с Avito)\n"
    f"{MENU_LIST} — список фильтров с кнопками (пауза/возобновить/проверить/интервал/удалить)\n"
    f"{MENU_STATUS} — когда следующая проверка по каждому фильтру\n"
    f"{MENU_STATS} — статистика\n"
    f"{MENU_EXPORT} — выгрузить фильтры в JSON (пришли такой файл боту — импортирую)\n\n"
    "Если кнопки внизу пропали — напиши /start, чтобы вернуть меню.\n\n"
    "<b>Команды для тонкой настройки</b> (не всё вынесено в кнопки):\n"
    "/renamefilter старое новое — переименовать\n"
    "/seturl имя ссылка — заменить ссылку поиска\n"
    "/setkeywords имя слово1,слово2 — скрывать объявления с этими словами в заголовке "
    "(«-» чтобы очистить)\n"
    "/setprice имя мин макс — доп. ограничение цены поверх фильтра Avito (0 — без ограничения)\n"
    "/cancel — отменить текущий диалог\n\n"
    "Кстати, я слежу и за снижением цены: если у уже виденного объявления цена "
    "упала — тоже пришлю уведомление."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await update.message.reply_html("Привет! " + HELP_TEXT, reply_markup=main_menu_keyboard())


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await update.message.reply_html(HELP_TEXT, reply_markup=main_menu_keyboard())


async def _check_menu_escape(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int | None:
    """If the user tapped a main-menu button while an /addfilter wizard step
    was expecting free text, treat it as "cancel the wizard, do that
    instead" rather than swallowing the tap as wizard input.
    """
    text = (update.message.text or "").strip() if update.message else ""
    handler = MENU_HANDLERS.get(text)
    if handler is None:
        return None
    context.user_data.pop("wizard", None)
    context.user_data.pop("new_filter_name", None)
    await handler(update, context)
    return ConversationHandler.END


async def cmd_addfilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    if not await guard(update):
        return ConversationHandler.END

    chat_id = update.effective_chat.id
    if db.count_filters(chat_id) >= MAX_FILTERS_PER_CHAT:
        await update.message.reply_text(
            f"Достигнут лимит фильтров ({MAX_FILTERS_PER_CHAT}). Удали ненужный "
            f"через /removefilter, прежде чем добавлять новый."
        )
        return ConversationHandler.END

    args = context.args or []
    if len(args) >= 2:
        return await _create_filter(update, context, chat_id, args[0], args[1])

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🗂 Выбрать категорию", callback_data="addmethod:category")],
            [InlineKeyboardButton("🔗 Вставить ссылку с Avito", callback_data="addmethod:url")],
            [InlineKeyboardButton("❌ Отмена", callback_data="wizcancel")],
        ]
    )
    await update.message.reply_text("Как добавим фильтр?", reply_markup=kb)
    return ADD_METHOD


async def addmethod_chosen(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wizcancel":
        await query.edit_message_text("Ок, отменил.")
        return ConversationHandler.END

    method = query.data.split(":", 1)[1]
    if method == "url":
        await query.edit_message_text(
            "Как назвать фильтр? (короткое имя для команд, например «iphone-msk»)"
        )
        return ASK_NAME

    context.user_data["wizard"] = {}
    await query.edit_message_text("Выбери категорию:", reply_markup=category_keyboard())
    return PICK_CATEGORY


async def addfilter_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    escape = await _check_menu_escape(update, context)
    if escape is not None:
        return escape
    name = update.message.text.strip()
    if not name or " " in name:
        await update.message.reply_text("Имя без пробелов, попробуй ещё раз:")
        return ASK_NAME
    context.user_data["new_filter_name"] = name
    await update.message.reply_text(
        "Пришли ссылку на поиск Avito с уже настроенными фильтрами "
        "(город/цена/категория — как в адресной строке браузера)."
    )
    return ASK_URL


async def addfilter_got_url(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    escape = await _check_menu_escape(update, context)
    if escape is not None:
        return escape
    url = update.message.text.strip()
    name = context.user_data.pop("new_filter_name", None)
    chat_id = update.effective_chat.id
    if not name:
        await update.message.reply_text("Что-то пошло не так, начни заново: /addfilter")
        return ConversationHandler.END
    return await _create_filter(update, context, chat_id, name, url)


async def _create_filter(
    update: Update, context: ContextTypes.DEFAULT_TYPE, chat_id: int, name: str, url: str
) -> int:
    message = update.effective_message
    if not avito_client.is_valid_avito_url(url):
        await message.reply_text(
            "Это не похоже на ссылку avito.ru. Пришли URL страницы поиска Avito."
        )
        return ASK_URL

    if db.filter_exists(chat_id, name):
        await message.reply_text(
            f"Фильтр «{name}» уже есть. Выбери другое имя или удали старый: /removefilter {name}"
        )
        return ConversationHandler.END

    db.add_filter(chat_id, name, url, DEFAULT_INTERVAL_MINUTES)
    await message.reply_text(
        f"Добавил фильтр «{name}», проверяю каждые {DEFAULT_INTERVAL_MINUTES} мин. "
        f"Сейчас сделаю первую проверку — она задаст точку отсчёта, без уведомлений "
        f"о текущих объявлениях, дальше буду слать только новые.",
        reply_markup=main_menu_keyboard(),
    )
    f = db.get_filter(chat_id, name)
    result = await run_check(context, f, notify_baseline=False)
    logger.info("[%s/%s] initial check: %s", f.chat_id, f.name, result)
    return ConversationHandler.END


# ---- guided category/city wizard ----------------------------------------

def category_keyboard() -> InlineKeyboardMarkup:
    rows = [
        [InlineKeyboardButton(label, callback_data=f"cat:{i}")]
        for i, (label, _) in enumerate(avito_categories.CATEGORIES)
    ]
    rows.append([InlineKeyboardButton("❌ Отмена", callback_data="wizcancel")])
    return InlineKeyboardMarkup(rows)


def subcat_keyboard(cat_idx: int) -> InlineKeyboardMarkup:
    _, subcats = avito_categories.CATEGORIES[cat_idx]
    rows = [
        [InlineKeyboardButton(name, callback_data=f"subcat:{i}")]
        for i, (name, _) in enumerate(subcats)
    ]
    rows.append([InlineKeyboardButton("‹ Назад", callback_data="wizback:category")])
    return InlineKeyboardMarkup(rows)


def city_keyboard() -> InlineKeyboardMarkup:
    cities = avito_categories.CITIES
    rows = []
    for i in range(0, len(cities), 2):
        row = [InlineKeyboardButton(cities[i][0], callback_data=f"city:{i}")]
        if i + 1 < len(cities):
            row.append(InlineKeyboardButton(cities[i + 1][0], callback_data=f"city:{i + 1}"))
        rows.append(row)
    rows.append([InlineKeyboardButton("‹ Назад", callback_data="wizback:subcat")])
    return InlineKeyboardMarkup(rows)


async def pick_category(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wizcancel":
        context.user_data.pop("wizard", None)
        await query.edit_message_text("Ок, отменил.")
        return ConversationHandler.END
    idx = int(query.data.split(":", 1)[1])
    label, _ = avito_categories.CATEGORIES[idx]
    context.user_data.setdefault("wizard", {})["cat_idx"] = idx
    await query.edit_message_text(f"{label} → выбери подкатегорию:", reply_markup=subcat_keyboard(idx))
    return PICK_SUBCAT


async def pick_subcat(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wizcancel":
        context.user_data.pop("wizard", None)
        await query.edit_message_text("Ок, отменил.")
        return ConversationHandler.END
    if query.data == "wizback:category":
        await query.edit_message_text("Выбери категорию:", reply_markup=category_keyboard())
        return PICK_CATEGORY

    idx = int(query.data.split(":", 1)[1])
    cat_idx = context.user_data["wizard"]["cat_idx"]
    name, slug = avito_categories.CATEGORIES[cat_idx][1][idx]
    context.user_data["wizard"]["subcat_name"] = name
    context.user_data["wizard"]["subcat_slug"] = slug
    await query.edit_message_text(f"{name} → выбери город:", reply_markup=city_keyboard())
    return PICK_CITY


async def pick_city(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wizcancel":
        context.user_data.pop("wizard", None)
        await query.edit_message_text("Ок, отменил.")
        return ConversationHandler.END
    if query.data == "wizback:subcat":
        cat_idx = context.user_data["wizard"]["cat_idx"]
        await query.edit_message_text("Выбери подкатегорию:", reply_markup=subcat_keyboard(cat_idx))
        return PICK_SUBCAT

    idx = int(query.data.split(":", 1)[1])
    city_name, city_slug = avito_categories.CITIES[idx]
    context.user_data["wizard"]["city_name"] = city_name
    context.user_data["wizard"]["city_slug"] = city_slug
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔎 Добавить ключевое слово", callback_data="wizkw:ask")],
            [InlineKeyboardButton("➡️ Пропустить", callback_data="wizkw:skip")],
        ]
    )
    await query.edit_message_text(
        "Уточнить ключевым словом? Например «iphone 13».", reply_markup=kb
    )
    return ASK_KEYWORD


async def ask_keyword_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    if action == "skip":
        return await _proceed_to_price(update, context)
    await query.edit_message_text("Напиши ключевое слово (или фразу) для поиска:")
    return ASK_KEYWORD


async def ask_keyword_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    escape = await _check_menu_escape(update, context)
    if escape is not None:
        return escape
    context.user_data["wizard"]["keyword"] = update.message.text.strip()
    return await _proceed_to_price(update, context)


async def _proceed_to_price(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("💰 Указать диапазон цены", callback_data="wizprice:ask")],
            [InlineKeyboardButton("➡️ Пропустить", callback_data="wizprice:skip")],
        ]
    )
    text = "Ограничить цену? Пришли потом в формате «мин макс», например «1000 50000»."
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    return ASK_PRICE


async def ask_price_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    action = query.data.split(":", 1)[1]
    if action == "skip":
        return await _show_preview(update, context)
    await query.edit_message_text(
        "Пришли диапазон цены в формате «мин макс» (0 — без ограничения), "
        "например «1000 50000»:"
    )
    return ASK_PRICE


async def ask_price_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    escape = await _check_menu_escape(update, context)
    if escape is not None:
        return escape
    parts = update.message.text.split()
    if len(parts) != 2 or not all(p.isdigit() for p in parts):
        await update.message.reply_text(
            "Не понял. Формат: «мин макс», например «1000 50000» или «0 0» без ограничения."
        )
        return ASK_PRICE
    price_min, price_max = int(parts[0]), int(parts[1])
    if price_max and price_min > price_max:
        await update.message.reply_text("Минимум больше максимума, попробуй ещё раз:")
        return ASK_PRICE
    context.user_data["wizard"]["price_min"] = price_min
    context.user_data["wizard"]["price_max"] = price_max
    return await _show_preview(update, context)


def _suggest_filter_name(chat_id: int, wiz: dict) -> str:
    base = f"{wiz['subcat_slug'].split('_')[0]}-{wiz['city_slug'].split('-')[0]}"
    name, n = base, 2
    while db.filter_exists(chat_id, name):
        name = f"{base}-{n}"
        n += 1
    return name


async def _show_preview(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    wiz = context.user_data["wizard"]
    url = avito_categories.build_search_url(
        wiz["city_slug"],
        wiz["subcat_slug"],
        wiz.get("keyword", ""),
        wiz.get("price_min", 0),
        wiz.get("price_max", 0),
    )
    wiz["url"] = url
    chat_id = update.effective_chat.id
    name = _suggest_filter_name(chat_id, wiz)
    wiz["suggested_name"] = name

    lines = [f"Категория: {wiz['subcat_name']}", f"Город: {wiz['city_name']}"]
    if wiz.get("keyword"):
        lines.append(f"Ключевое слово: {wiz['keyword']}")
    if wiz.get("price_min") or wiz.get("price_max"):
        lo, hi = wiz.get("price_min") or 0, wiz.get("price_max") or "∞"
        lines.append(f"Цена: {lo}–{hi} ₽")
    lines.append(f"\nИмя фильтра: «{name}»")
    lines.append(
        "\n⚠️ Список категорий собран вручную и не проверен на актуальность — "
        "нажми «Проверить на Avito» перед сохранением, чтобы убедиться, что "
        "ссылка открывает именно то, что нужно."
    )

    kb = InlineKeyboardMarkup(
        [
            [InlineKeyboardButton("🔗 Проверить на Avito", url=url)],
            [InlineKeyboardButton(f"✅ Сохранить как «{name}»", callback_data="wizsave:auto")],
            [InlineKeyboardButton("✏️ Своё имя", callback_data="wizsave:custom")],
            [InlineKeyboardButton("❌ Отмена", callback_data="wizcancel")],
        ]
    )
    text = "\n".join(lines)
    if update.callback_query:
        await update.callback_query.edit_message_text(text, reply_markup=kb)
    else:
        await update.message.reply_text(text, reply_markup=kb)
    return PREVIEW


async def preview_action(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    query = update.callback_query
    await query.answer()
    if query.data == "wizcancel":
        context.user_data.pop("wizard", None)
        await query.edit_message_text("Ок, отменил.")
        return ConversationHandler.END

    action = query.data.split(":", 1)[1]
    if action == "custom":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(query.message.chat_id, "Напиши имя фильтра (без пробелов):")
        return ASK_CUSTOM_NAME

    await query.edit_message_reply_markup(reply_markup=None)
    wiz = context.user_data.pop("wizard")
    return await _create_filter(update, context, query.message.chat_id, wiz["suggested_name"], wiz["url"])


async def custom_name_text(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    escape = await _check_menu_escape(update, context)
    if escape is not None:
        return escape
    name = update.message.text.strip()
    if not name or " " in name:
        await update.message.reply_text("Имя без пробелов, попробуй ещё раз:")
        return ASK_CUSTOM_NAME
    chat_id = update.effective_chat.id
    if db.filter_exists(chat_id, name):
        await update.message.reply_text(f"Фильтр «{name}» уже есть, придумай другое имя:")
        return ASK_CUSTOM_NAME
    wiz = context.user_data.pop("wizard", None)
    if not wiz:
        await update.message.reply_text("Что-то пошло не так, начни заново: /addfilter")
        return ConversationHandler.END
    return await _create_filter(update, context, chat_id, name, wiz["url"])


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_filter_name", None)
    context.user_data.pop("wizard", None)
    await update.message.reply_text("Ок, отменил.")
    return ConversationHandler.END


async def cmd_myfilters(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    items = db.list_filters(chat_id)
    if not items:
        await update.message.reply_text("Фильтров пока нет. Добавь: /addfilter")
        return
    for f in items:
        await update.message.reply_html(describe_filter(f), reply_markup=filter_keyboard(f))


def _resolve_target(update: Update, context: ContextTypes.DEFAULT_TYPE) -> tuple[int, str | None]:
    chat_id = update.effective_chat.id
    name = context.args[0] if context.args else None
    return chat_id, name


async def cmd_pause(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id, name = _resolve_target(update, context)
    if not name:
        await update.message.reply_text("Использование: /pause имя_фильтра")
        return
    ok = db.set_active(chat_id, name, False)
    await update.message.reply_text("Поставил на паузу." if ok else "Такого фильтра нет.")


async def cmd_resume(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id, name = _resolve_target(update, context)
    if not name:
        await update.message.reply_text("Использование: /resume имя_фильтра")
        return
    ok = db.set_active(chat_id, name, True)
    await update.message.reply_text("Возобновил." if ok else "Такого фильтра нет.")


async def cmd_removefilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id, name = _resolve_target(update, context)
    if not name:
        await update.message.reply_text("Использование: /removefilter имя_фильтра")
        return
    ok = db.delete_filter(chat_id, name)
    await update.message.reply_text("Удалил." if ok else "Такого фильтра нет.")


async def cmd_setinterval(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /setinterval имя_фильтра минуты")
        return
    name, minutes_raw = context.args[0], context.args[1]
    try:
        minutes = int(minutes_raw)
    except ValueError:
        await update.message.reply_text("Минуты должны быть числом.")
        return
    if minutes < MIN_INTERVAL_MINUTES:
        await update.message.reply_text(f"Минимальный интервал — {MIN_INTERVAL_MINUTES} мин.")
        return
    ok = db.set_interval(chat_id, name, minutes)
    await update.message.reply_text(
        f"Интервал обновлён на {minutes} мин." if ok else "Такого фильтра нет."
    )


async def cmd_renamefilter(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /renamefilter старое_имя новое_имя")
        return
    old_name, new_name = context.args[0], context.args[1]
    if db.filter_exists(chat_id, new_name):
        await update.message.reply_text(f"Фильтр «{new_name}» уже существует.")
        return
    ok = db.rename_filter(chat_id, old_name, new_name)
    await update.message.reply_text(
        f"Переименовал в «{new_name}»." if ok else "Такого фильтра нет."
    )


async def cmd_seturl(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    if len(context.args) < 2:
        await update.message.reply_text("Использование: /seturl имя_фильтра новая_ссылка")
        return
    name, url = context.args[0], context.args[1]
    if not avito_client.is_valid_avito_url(url):
        await update.message.reply_text("Это не похоже на ссылку avito.ru.")
        return
    ok = db.set_url(chat_id, name, url)
    await update.message.reply_text(
        "Ссылка обновлена. История уже виденных объявлений сохранена, "
        "первый уведомлений по новым критериям может не быть, пока не появится что-то новое."
        if ok
        else "Такого фильтра нет."
    )


async def cmd_setkeywords(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    if len(context.args) < 1:
        await update.message.reply_text(
            "Использование: /setkeywords имя_фильтра слово1,слово2,...\n"
            "Объявления с этими словами в заголовке не будут присылаться. "
            "Чтобы очистить список: /setkeywords имя_фильтра -"
        )
        return
    name = context.args[0]
    raw = " ".join(context.args[1:]).strip()
    keywords = "" if raw in ("-", "") else raw
    ok = db.set_exclude_keywords(chat_id, name, keywords)
    if not ok:
        await update.message.reply_text("Такого фильтра нет.")
        return
    await update.message.reply_text(
        "Стоп-слова очищены." if not keywords else f"Буду скрывать объявления со словами: {keywords}"
    )


async def cmd_setprice(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    if len(context.args) < 3:
        await update.message.reply_text(
            "Использование: /setprice имя_фильтра мин макс (0 — без ограничения)"
        )
        return
    name = context.args[0]
    try:
        price_min = int(context.args[1])
        price_max = int(context.args[2])
    except ValueError:
        await update.message.reply_text("Мин/макс должны быть числами.")
        return
    if price_min < 0 or price_max < 0:
        await update.message.reply_text("Цена не может быть отрицательной.")
        return
    if price_max and price_min > price_max:
        await update.message.reply_text("Минимум больше максимума.")
        return
    ok = db.set_price_range(chat_id, name, price_min, price_max)
    if not ok:
        await update.message.reply_text("Такого фильтра нет.")
        return
    lo, hi = price_min or "0", price_max or "∞"
    await update.message.reply_text(f"Диапазон цены: {lo}–{hi} ₽")


async def cmd_status(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    items = db.list_filters(chat_id)
    if not items:
        await update.message.reply_text("Фильтров пока нет. Добавь: /addfilter")
        return
    now = time.time()
    lines = []
    for f in items:
        if not f.active:
            due = "на паузе"
        else:
            remaining = f.interval_minutes * 60 - (now - f.last_checked_at)
            due = "вот-вот" if remaining <= 0 else f"через {int(remaining // 60)} мин"
        lines.append(f"• {html.escape(f.name)} — следующая проверка: {due}")
    await update.message.reply_html("\n".join(lines))


async def cmd_broadcast(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if ADMIN_CHAT_ID is None or update.effective_chat.id != ADMIN_CHAT_ID:
        return
    text = " ".join(context.args)
    if not text:
        await update.message.reply_text("Использование: /broadcast текст сообщения")
        return
    chat_ids = db.list_chat_ids()
    sent = 0
    for chat_id in chat_ids:
        try:
            await context.bot.send_message(chat_id=chat_id, text=f"📢 {text}")
            sent += 1
        except Exception:
            logger.warning("broadcast failed for chat_id=%s", chat_id)
        await asyncio.sleep(0.1)
    await update.message.reply_text(f"Разослано в {sent}/{len(chat_ids)} чатов.")


async def cmd_check(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id, name = _resolve_target(update, context)
    if not name:
        await update.message.reply_text("Использование: /check имя_фильтра")
        return
    f = db.get_filter(chat_id, name)
    if not f:
        await update.message.reply_text("Такого фильтра нет.")
        return
    await update.message.reply_text(f"Проверяю «{name}»…")
    result = await run_check(context, f, notify_baseline=True)
    await update.message.reply_text(f"Готово: {result}")


async def cmd_checkall(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    items = db.list_filters(chat_id)
    if not items:
        await update.message.reply_text("Фильтров пока нет. Добавь: /addfilter")
        return
    await update.message.reply_text(f"Проверяю {len(items)} фильтр(ов)…")
    for f in items:
        result = await run_check(context, f, notify_baseline=True)
        logger.info("[%s/%s] manual checkall: %s", f.chat_id, f.name, result)
    await update.message.reply_text("Готово.")


async def cmd_stats(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    mine = db.list_filters(chat_id)
    g = db.global_stats()
    await update.message.reply_html(
        f"<b>Твои фильтры:</b> {len(mine)} "
        f"(активных: {sum(1 for f in mine if f.active)})\n"
        f"<b>Бот в целом:</b> {g['filters']} фильтров в {g['chats']} чатах, "
        f"всего найдено {g['total_found']} объявлений."
    )


def _filter_to_export_dict(f: Filter) -> dict:
    return {
        "name": f.name,
        "url": f.url,
        "interval_minutes": f.interval_minutes,
        "exclude_keywords": f.exclude_keywords,
        "price_min": f.price_min,
        "price_max": f.price_max,
    }


async def cmd_export(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    chat_id = update.effective_chat.id
    items = db.list_filters(chat_id)
    if not items:
        await update.message.reply_text("Фильтров пока нет, нечего экспортировать.")
        return
    payload = json.dumps([_filter_to_export_dict(f) for f in items], ensure_ascii=False, indent=2)
    await update.message.reply_document(
        document=InputFile(io.BytesIO(payload.encode("utf-8")), filename="avito_filters.json"),
        caption=f"Экспортировано {len(items)} фильтр(ов). Пришли этот файл боту, чтобы восстановить.",
    )


async def cmd_import_document(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    document = update.message.document
    if not document or not (document.file_name or "").lower().endswith(".json"):
        return

    chat_id = update.effective_chat.id
    tg_file = await context.bot.get_file(document.file_id)
    raw = await tg_file.download_as_bytearray()
    try:
        items = json.loads(bytes(raw).decode("utf-8"))
    except (json.JSONDecodeError, UnicodeDecodeError):
        await update.message.reply_text("Не смог разобрать файл — это не тот JSON.")
        return
    if not isinstance(items, list):
        await update.message.reply_text("Ожидался список фильтров в JSON.")
        return

    added, skipped, invalid = 0, 0, 0
    for entry in items:
        if db.count_filters(chat_id) >= MAX_FILTERS_PER_CHAT:
            break
        if not isinstance(entry, dict):
            invalid += 1
            continue
        name = str(entry.get("name", "")).strip()
        url = str(entry.get("url", "")).strip()
        if not name or not avito_client.is_valid_avito_url(url):
            invalid += 1
            continue
        if db.filter_exists(chat_id, name):
            skipped += 1
            continue
        interval = entry.get("interval_minutes", DEFAULT_INTERVAL_MINUTES)
        interval = interval if isinstance(interval, int) and interval >= MIN_INTERVAL_MINUTES else DEFAULT_INTERVAL_MINUTES
        db.add_filter(chat_id, name, url, interval)
        keywords = entry.get("exclude_keywords", "")
        if isinstance(keywords, str) and keywords:
            db.set_exclude_keywords(chat_id, name, keywords)
        price_min = entry.get("price_min", 0)
        price_max = entry.get("price_max", 0)
        if isinstance(price_min, int) and isinstance(price_max, int) and (price_min or price_max):
            db.set_price_range(chat_id, name, price_min, price_max)
        added += 1

    await update.message.reply_text(
        f"Импорт завершён: добавлено {added}, пропущено (уже есть) {skipped}, "
        f"некорректных записей {invalid}. Первую проверку каждый новый фильтр сделает "
        f"сам в течение {POLL_INTERVAL_SECONDS} сек — можно и вручную: /checkall."
    )


FILTER_ACTIONS = {"pause", "resume", "check", "delrequest", "delconfirm", "delcancel", "interval", "setiv", "back"}


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not chat_allowed(query.message.chat_id):
        return
    parts = query.data.split(":")
    action = parts[0]
    if action not in FILTER_ACTIONS or len(parts) < 2:
        return
    try:
        filter_id = int(parts[1])
    except ValueError:
        return
    f = db.get_filter_by_id(filter_id)
    if not f or f.chat_id != query.message.chat_id:
        await query.edit_message_text("Фильтр не найден (возможно, уже удалён).")
        return

    if action == "pause":
        db.set_active(f.chat_id, f.name, False)
    elif action == "resume":
        db.set_active(f.chat_id, f.name, True)
    elif action == "check":
        await query.edit_message_reply_markup(reply_markup=None)
        await context.bot.send_message(f.chat_id, f"Проверяю «{f.name}»…")
        await run_check(context, f, notify_baseline=True)
    elif action == "delrequest":
        kb = InlineKeyboardMarkup(
            [
                [
                    InlineKeyboardButton("Да, удалить", callback_data=f"delconfirm:{f.id}"),
                    InlineKeyboardButton("Отмена", callback_data=f"delcancel:{f.id}"),
                ]
            ]
        )
        await query.edit_message_text(
            f"Удалить фильтр «{html.escape(f.name)}»?", parse_mode=ParseMode.HTML, reply_markup=kb
        )
        return
    elif action == "delconfirm":
        db.delete_filter(f.chat_id, f.name)
        await query.edit_message_text(f"Фильтр «{html.escape(f.name)}» удалён.")
        return
    elif action == "delcancel":
        pass
    elif action == "interval":
        await query.edit_message_text(
            describe_filter(f) + "\n\nВыбери интервал проверки:",
            parse_mode=ParseMode.HTML,
            reply_markup=interval_keyboard(f),
        )
        return
    elif action == "setiv":
        if len(parts) < 3:
            return
        try:
            minutes = int(parts[2])
        except ValueError:
            return
        db.set_interval(f.chat_id, f.name, minutes)
    elif action == "back":
        pass

    f = db.get_filter_by_id(filter_id)
    if f:
        await query.edit_message_text(
            describe_filter(f), parse_mode=ParseMode.HTML, reply_markup=filter_keyboard(f)
        )


async def on_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await update.message.reply_text("Не понял команду. Список команд: /help")


MENU_HANDLERS.update(
    {
        MENU_LIST: cmd_myfilters,
        MENU_STATUS: cmd_status,
        MENU_STATS: cmd_stats,
        MENU_EXPORT: cmd_export,
        MENU_HELP: cmd_help,
    }
)


BOT_COMMANDS = [
    BotCommand("addfilter", "добавить фильтр"),
    BotCommand("myfilters", "список фильтров"),
    BotCommand("status", "когда следующая проверка"),
    BotCommand("check", "проверить фильтр сейчас"),
    BotCommand("checkall", "проверить все фильтры"),
    BotCommand("pause", "поставить фильтр на паузу"),
    BotCommand("resume", "возобновить фильтр"),
    BotCommand("removefilter", "удалить фильтр"),
    BotCommand("setinterval", "периодичность проверки"),
    BotCommand("setkeywords", "стоп-слова в заголовке"),
    BotCommand("setprice", "диапазон цены"),
    BotCommand("renamefilter", "переименовать фильтр"),
    BotCommand("seturl", "заменить ссылку фильтра"),
    BotCommand("export", "выгрузить фильтры в JSON"),
    BotCommand("stats", "статистика"),
    BotCommand("help", "список команд"),
]


async def _post_init(application: Application) -> None:
    await application.bot.set_my_commands(BOT_COMMANDS)


def _menu_text_filter(text: str) -> filters.BaseFilter:
    return filters.Regex(f"^{re.escape(text)}$")


def build_app() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).post_init(_post_init).build()

    conv = ConversationHandler(
        entry_points=[
            CommandHandler("addfilter", cmd_addfilter),
            MessageHandler(_menu_text_filter(MENU_ADD), cmd_addfilter),
        ],
        states={
            ADD_METHOD: [CallbackQueryHandler(addmethod_chosen, pattern=r"^(addmethod:|wizcancel$)")],
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addfilter_got_name)],
            ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, addfilter_got_url)],
            PICK_CATEGORY: [CallbackQueryHandler(pick_category, pattern=r"^(cat:|wizcancel$)")],
            PICK_SUBCAT: [
                CallbackQueryHandler(pick_subcat, pattern=r"^(subcat:|wizback:category$|wizcancel$)")
            ],
            PICK_CITY: [
                CallbackQueryHandler(pick_city, pattern=r"^(city:|wizback:subcat$|wizcancel$)")
            ],
            ASK_KEYWORD: [
                CallbackQueryHandler(ask_keyword_button, pattern=r"^wizkw:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_keyword_text),
            ],
            ASK_PRICE: [
                CallbackQueryHandler(ask_price_button, pattern=r"^wizprice:"),
                MessageHandler(filters.TEXT & ~filters.COMMAND, ask_price_text),
            ],
            PREVIEW: [CallbackQueryHandler(preview_action, pattern=r"^(wizsave:|wizcancel$)")],
            ASK_CUSTOM_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, custom_name_text)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(conv)
    app.add_handler(MessageHandler(_menu_text_filter(MENU_LIST), cmd_myfilters))
    app.add_handler(MessageHandler(_menu_text_filter(MENU_STATUS), cmd_status))
    app.add_handler(MessageHandler(_menu_text_filter(MENU_STATS), cmd_stats))
    app.add_handler(MessageHandler(_menu_text_filter(MENU_EXPORT), cmd_export))
    app.add_handler(MessageHandler(_menu_text_filter(MENU_HELP), cmd_help))
    app.add_handler(CommandHandler("myfilters", cmd_myfilters))
    app.add_handler(CommandHandler("status", cmd_status))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("removefilter", cmd_removefilter))
    app.add_handler(CommandHandler("setinterval", cmd_setinterval))
    app.add_handler(CommandHandler("renamefilter", cmd_renamefilter))
    app.add_handler(CommandHandler("seturl", cmd_seturl))
    app.add_handler(CommandHandler("setkeywords", cmd_setkeywords))
    app.add_handler(CommandHandler("setprice", cmd_setprice))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("checkall", cmd_checkall))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CommandHandler("broadcast", cmd_broadcast))
    app.add_handler(CommandHandler("export", cmd_export))
    app.add_handler(MessageHandler(filters.Document.ALL, cmd_import_document))
    app.add_handler(CallbackQueryHandler(on_button, pattern=rf"^({'|'.join(FILTER_ACTIONS)}):"))
    app.add_handler(MessageHandler(filters.COMMAND, on_unknown))

    if app.job_queue is not None:
        app.job_queue.run_repeating(poll_due_filters, interval=POLL_INTERVAL_SECONDS, first=10)
    else:
        logger.warning("JobQueue unavailable — install python-telegram-bot[job-queue]")

    return app


def main() -> None:
    app = build_app()
    logger.info("bot starting, db=%s", DB_PATH)
    app.run_polling(allowed_updates=Update.ALL_TYPES)


if __name__ == "__main__":
    main()
