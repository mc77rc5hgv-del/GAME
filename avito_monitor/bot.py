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
import logging
import os
import time
from pathlib import Path

from telegram import InlineKeyboardButton, InlineKeyboardMarkup, Update
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

_allowed_raw = os.environ.get("AVITO_ALLOWED_CHAT_IDS", "").strip()
ALLOWED_CHAT_IDS: set[int] | None = (
    {int(x) for x in _allowed_raw.split(",") if x.strip()} if _allowed_raw else None
)

ASK_NAME, ASK_URL = range(2)

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


def filter_keyboard(f: Filter) -> InlineKeyboardMarkup:
    toggle = ("⏸ Пауза", f"pause:{f.id}") if f.active else ("▶️ Возобновить", f"resume:{f.id}")
    return InlineKeyboardMarkup(
        [
            [
                InlineKeyboardButton("🔄 Проверить сейчас", callback_data=f"check:{f.id}"),
                InlineKeyboardButton(toggle[0], callback_data=toggle[1]),
            ],
            [InlineKeyboardButton("🗑 Удалить", callback_data=f"delrequest:{f.id}")],
        ]
    )


def describe_filter(f: Filter) -> str:
    status = "🟢 активен" if f.active else "⏸ на паузе"
    fail_note = ""
    if f.consecutive_failures >= ALERT_AFTER_FAILURES:
        fail_note = " ⚠️ похоже на блокировку сайтом"
    last_found = (
        time.strftime("%d.%m %H:%M", time.localtime(f.last_found_at))
        if f.last_found_at
        else "пока не было"
    )
    return (
        f"<b>{html.escape(f.name)}</b> — {status}{fail_note}\n"
        f"Интервал: {f.interval_minutes} мин · найдено всего: {f.total_found}\n"
        f"Последняя находка: {last_found}\n"
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

    listings = avito_client.parse_listings(html_text)
    seen = db.get_seen_ids(f.id)
    is_first_run = len(seen) == 0
    new_listings = [item for item in listings if item.id not in seen]

    sent = 0
    if not is_first_run:
        to_send = list(reversed(new_listings))
        for item in to_send[:MAX_NOTIFY_PER_CHECK]:
            await context.bot.send_message(
                chat_id=f.chat_id,
                text=format_listing_message(f.name, item),
                parse_mode=ParseMode.HTML,
            )
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
    elif notify_baseline:
        await context.bot.send_message(
            chat_id=f.chat_id,
            text=(
                f"Фильтр «{html.escape(f.name)}» подключён, нашёл {len(listings)} "
                f"объявлений сейчас — это базовый срез, уведомлять буду только о новых."
            ),
        )

    db.add_seen_ids(f.id, [item.id for item in listings])
    db.mark_checked(f.id, success=True, new_found=sent)
    return f"ok, найдено {len(listings)}, новых отправлено {sent}"


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
    "<b>Команды:</b>\n"
    "/addfilter — добавить фильтр (пошагово спрошу имя и ссылку)\n"
    "/addfilter имя ссылка — добавить фильтр одной командой\n"
    "/myfilters — список фильтров с кнопками управления\n"
    "/pause имя — поставить фильтр на паузу\n"
    "/resume имя — возобновить фильтр\n"
    "/removefilter имя — удалить фильтр\n"
    "/setinterval имя минуты — задать периодичность проверки\n"
    "/check имя — проверить фильтр прямо сейчас\n"
    "/checkall — проверить все свои фильтры сейчас\n"
    "/stats — статистика бота\n"
    "/cancel — отменить текущий диалог\n\n"
    "Ссылка для фильтра — это обычный URL поиска Avito: настрой на сайте нужный "
    "город/цену/категорию и скопируй адрес из браузера."
)


async def cmd_start(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await update.message.reply_html(
        "Привет! " + HELP_TEXT
    )


async def cmd_help(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await update.message.reply_html(HELP_TEXT)


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

    if len(context.args) >= 2:
        name = context.args[0]
        url = context.args[1]
        return await _create_filter(update, context, chat_id, name, url)

    await update.message.reply_text(
        "Как назвать фильтр? (короткое имя для команд, например «iphone-msk»)"
    )
    return ASK_NAME


async def addfilter_got_name(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
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
    if not avito_client.is_valid_avito_url(url):
        await update.message.reply_text(
            "Это не похоже на ссылку avito.ru. Пришли URL страницы поиска Avito."
        )
        return ASK_URL

    if db.filter_exists(chat_id, name):
        await update.message.reply_text(
            f"Фильтр «{name}» уже есть. Выбери другое имя или удали старый: /removefilter {name}"
        )
        return ConversationHandler.END

    db.add_filter(chat_id, name, url, DEFAULT_INTERVAL_MINUTES)
    await update.message.reply_text(
        f"Добавил фильтр «{name}», проверяю каждые {DEFAULT_INTERVAL_MINUTES} мин. "
        f"Сейчас сделаю первую проверку — она задаст точку отсчёта, без уведомлений "
        f"о текущих объявлениях, дальше буду слать только новые."
    )
    f = db.get_filter(chat_id, name)
    result = await run_check(context, f, notify_baseline=False)
    logger.info("[%s/%s] initial check: %s", f.chat_id, f.name, result)
    return ConversationHandler.END


async def cmd_cancel(update: Update, context: ContextTypes.DEFAULT_TYPE) -> int:
    context.user_data.pop("new_filter_name", None)
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


async def on_button(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    query = update.callback_query
    await query.answer()
    if not chat_allowed(query.message.chat_id):
        return
    action, _, raw_id = query.data.partition(":")
    filter_id = int(raw_id)
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

    f = db.get_filter_by_id(filter_id)
    if f:
        await query.edit_message_text(
            describe_filter(f), parse_mode=ParseMode.HTML, reply_markup=filter_keyboard(f)
        )


async def on_unknown(update: Update, context: ContextTypes.DEFAULT_TYPE) -> None:
    if not await guard(update):
        return
    await update.message.reply_text("Не понял команду. Список команд: /help")


def build_app() -> Application:
    if not TELEGRAM_BOT_TOKEN:
        raise SystemExit("TELEGRAM_BOT_TOKEN is not set")

    app = Application.builder().token(TELEGRAM_BOT_TOKEN).build()

    conv = ConversationHandler(
        entry_points=[CommandHandler("addfilter", cmd_addfilter)],
        states={
            ASK_NAME: [MessageHandler(filters.TEXT & ~filters.COMMAND, addfilter_got_name)],
            ASK_URL: [MessageHandler(filters.TEXT & ~filters.COMMAND, addfilter_got_url)],
        },
        fallbacks=[CommandHandler("cancel", cmd_cancel)],
    )

    app.add_handler(CommandHandler("start", cmd_start))
    app.add_handler(CommandHandler("help", cmd_help))
    app.add_handler(conv)
    app.add_handler(CommandHandler("myfilters", cmd_myfilters))
    app.add_handler(CommandHandler("pause", cmd_pause))
    app.add_handler(CommandHandler("resume", cmd_resume))
    app.add_handler(CommandHandler("removefilter", cmd_removefilter))
    app.add_handler(CommandHandler("setinterval", cmd_setinterval))
    app.add_handler(CommandHandler("check", cmd_check))
    app.add_handler(CommandHandler("checkall", cmd_checkall))
    app.add_handler(CommandHandler("stats", cmd_stats))
    app.add_handler(CallbackQueryHandler(on_button))
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
