#!/usr/bin/env python3
"""Cron-style Avito monitor: reads config.json, pushes new listings to one
fixed Telegram chat. Intended for a scheduled runner (e.g. GitHub Actions)
where filters are edited by hand in config.json.

For an interactive multi-user bot where filters are managed via Telegram
commands, use bot.py instead.
"""
from __future__ import annotations

import html
import json
import os
import sys
import time
from dataclasses import dataclass, field
from pathlib import Path

import requests

import avito_client
from avito_client import Listing

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("AVITO_CONFIG", BASE_DIR / "config.json"))
STATE_DIR = Path(os.environ.get("AVITO_STATE_DIR", BASE_DIR / "state"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

MAX_SEEN_IDS = 1000
ALERT_AFTER_FAILURES = 3
ALERT_COOLDOWN_SECONDS = 6 * 3600


@dataclass
class FilterState:
    seen_ids: list[str] = field(default_factory=list)
    consecutive_failures: int = 0
    last_alert_ts: float = 0.0


def log(msg: str) -> None:
    print(msg, flush=True)


def load_config() -> list[dict]:
    if not CONFIG_PATH.exists():
        log(f"Config not found at {CONFIG_PATH}. Copy config.example.json to config.json and edit it.")
        sys.exit(1)
    data = json.loads(CONFIG_PATH.read_text(encoding="utf-8"))
    filters = data.get("filters", [])
    if not filters:
        log("Config has no filters defined.")
        sys.exit(1)
    return filters


def state_path(name: str) -> Path:
    STATE_DIR.mkdir(parents=True, exist_ok=True)
    return STATE_DIR / f"{name}.json"


def load_state(name: str) -> FilterState:
    path = state_path(name)
    if not path.exists():
        return FilterState()
    raw = json.loads(path.read_text(encoding="utf-8"))
    return FilterState(
        seen_ids=raw.get("seen_ids", []),
        consecutive_failures=raw.get("consecutive_failures", 0),
        last_alert_ts=raw.get("last_alert_ts", 0.0),
    )


def save_state(name: str, state: FilterState) -> None:
    path = state_path(name)
    path.write_text(
        json.dumps(
            {
                "seen_ids": state.seen_ids[-MAX_SEEN_IDS:],
                "consecutive_failures": state.consecutive_failures,
                "last_alert_ts": state.last_alert_ts,
            },
            ensure_ascii=False,
            indent=2,
        ),
        encoding="utf-8",
    )


def send_telegram_message(text: str) -> bool:
    if not TELEGRAM_BOT_TOKEN or not TELEGRAM_CHAT_ID:
        log("  TELEGRAM_BOT_TOKEN / TELEGRAM_CHAT_ID not set, skipping send")
        return False
    api_url = f"https://api.telegram.org/bot{TELEGRAM_BOT_TOKEN}/sendMessage"
    try:
        resp = requests.post(
            api_url,
            json={
                "chat_id": TELEGRAM_CHAT_ID,
                "text": text,
                "parse_mode": "HTML",
                "disable_web_page_preview": False,
            },
            timeout=15,
        )
        if resp.status_code != 200:
            log(f"  telegram send failed: {resp.status_code} {resp.text[:200]}")
            return False
        return True
    except requests.RequestException as exc:
        log(f"  telegram send error: {exc}")
        return False


def format_listing_message(filter_name: str, listing: Listing) -> str:
    title = html.escape(listing.title or "Без названия")
    price = f"{listing.price} ₽" if listing.price else "цена не указана"
    return (
        f"🆕 <b>{title}</b>\n"
        f"💰 {price}\n"
        f"🔎 Фильтр: {html.escape(filter_name)}\n"
        f"{html.escape(listing.url)}"
    )


def fetch(url: str) -> str | None:
    html_text, status = avito_client.fetch(url)
    if html_text is None:
        log(f"  fetch failed, last status={status}")
    return html_text


def process_filter(name: str, url: str) -> None:
    log(f"[{name}] fetching {url}")
    state = load_state(name)
    html_text = fetch(url)

    if html_text is None:
        state.consecutive_failures += 1
        log(f"[{name}] fetch failed ({state.consecutive_failures} in a row)")
        now = time.time()
        if (
            state.consecutive_failures >= ALERT_AFTER_FAILURES
            and now - state.last_alert_ts > ALERT_COOLDOWN_SECONDS
        ):
            send_telegram_message(
                f"⚠️ Мониторинг Avito: фильтр «{html.escape(name)}» не удаётся загрузить "
                f"{state.consecutive_failures} раз подряд (похоже на блокировку антиботом). "
                f"Проверьте вручную: {html.escape(url)}"
            )
            state.last_alert_ts = now
        save_state(name, state)
        return

    state.consecutive_failures = 0
    listings = avito_client.parse_listings(html_text)
    log(f"[{name}] parsed {len(listings)} listings")

    if not listings:
        save_state(name, state)
        return

    seen = set(state.seen_ids)
    is_first_run = len(seen) == 0
    new_listings = [item for item in listings if item.id not in seen]

    if is_first_run:
        # Don't spam Telegram with the whole current result set on first run;
        # just record what's there and notify on genuinely new ones from now on.
        log(f"[{name}] first run, recording {len(listings)} listings as baseline")
    else:
        for item in reversed(new_listings):
            log(f"[{name}] new listing {item.id}: {item.title}")
            send_telegram_message(format_listing_message(name, item))
            time.sleep(1)

    state.seen_ids = list(seen | {item.id for item in listings})
    save_state(name, state)


def main() -> None:
    filters = load_config()
    for f in filters:
        try:
            process_filter(f["name"], f["url"])
        except Exception as exc:  # keep going even if one filter blows up
            log(f"[{f.get('name')}] unexpected error: {exc}")


if __name__ == "__main__":
    main()
