#!/usr/bin/env python3
"""Polls configured Avito search URLs and pushes new listings to Telegram.

Run periodically (e.g. via a GitHub Actions cron job). State (which listing
ids have already been seen/notified) is persisted per filter under state/.
"""
from __future__ import annotations

import html
import json
import os
import random
import re
import sys
import time
import urllib.parse
from dataclasses import dataclass, field
from pathlib import Path

import requests

BASE_DIR = Path(__file__).resolve().parent
CONFIG_PATH = Path(os.environ.get("AVITO_CONFIG", BASE_DIR / "config.json"))
STATE_DIR = Path(os.environ.get("AVITO_STATE_DIR", BASE_DIR / "state"))

TELEGRAM_BOT_TOKEN = os.environ.get("TELEGRAM_BOT_TOKEN", "")
TELEGRAM_CHAT_ID = os.environ.get("TELEGRAM_CHAT_ID", "")

MAX_SEEN_IDS = 1000
MAX_FETCH_RETRIES = 4
ALERT_AFTER_FAILURES = 3
ALERT_COOLDOWN_SECONDS = 6 * 3600

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

ITEM_ID_RE = re.compile(r"_(\d{6,})(?:[/?]|$)")


@dataclass
class Listing:
    id: str
    title: str
    url: str
    price: str = ""
    image: str = ""


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


def fetch(url: str) -> str | None:
    session = requests.Session()
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            resp = session.get(url, headers=headers, timeout=20)
        except requests.RequestException as exc:
            log(f"  fetch attempt {attempt} failed: {exc}")
            resp = None

        if resp is not None and resp.status_code == 200 and "data-marker" in resp.text:
            return resp.text

        status = resp.status_code if resp is not None else "network-error"
        log(f"  fetch attempt {attempt} got status={status}")

        if attempt < MAX_FETCH_RETRIES:
            time.sleep(2 ** attempt + random.uniform(0, 1.5))

    return None


def parse_listings(html_text: str) -> list[Listing]:
    listings = parse_via_jsonld(html_text)
    if listings:
        return listings
    return parse_via_data_marker(html_text)


def parse_via_jsonld(html_text: str) -> list[Listing]:
    listings: list[Listing] = []
    for match in re.finditer(
        r'<script[^>]+type="application/ld\+json"[^>]*>(.*?)</script>', html_text, re.S
    ):
        try:
            data = json.loads(match.group(1))
        except json.JSONDecodeError:
            continue
        items = data.get("itemListElement") if isinstance(data, dict) else None
        if not items:
            continue
        for entry in items:
            item = entry.get("item", entry) if isinstance(entry, dict) else None
            if not item:
                continue
            url = item.get("url") or item.get("@id") or ""
            item_id = extract_item_id(url)
            if not item_id:
                continue
            price = ""
            offers = item.get("offers")
            if isinstance(offers, dict):
                price = str(offers.get("price", "") or "")
            listings.append(
                Listing(
                    id=item_id,
                    title=html.unescape(item.get("name", "")).strip(),
                    url=url,
                    price=price,
                    image=item.get("image", "") if isinstance(item.get("image"), str) else "",
                )
            )
    return listings


def parse_via_data_marker(html_text: str) -> list[Listing]:
    listings: list[Listing] = []
    for block in re.finditer(r'data-marker="item"[^>]*data-item-id="(\d+)"', html_text):
        item_id = block.group(1)
        window_start = block.start()
        window = html_text[window_start : window_start + 4000]

        title_match = re.search(
            r'data-marker="item-title"[^>]*(?:title="([^"]*)")?[^>]*>([^<]*)', window
        )
        title = ""
        if title_match:
            title = title_match.group(1) or title_match.group(2) or ""
        title = html.unescape(title).strip()

        href_match = re.search(r'href="(/[^"]+_' + item_id + r'[^"]*)"', window)
        url = urllib.parse.urljoin("https://www.avito.ru", href_match.group(1)) if href_match else ""

        price_match = re.search(r'data-marker="item-price"[^>]*>\s*([\d\s ]+)', window)
        price = re.sub(r"[\s ]", "", price_match.group(1)) if price_match else ""

        if title and url:
            listings.append(Listing(id=item_id, title=title, url=url, price=price))
    return listings


def extract_item_id(url: str) -> str | None:
    match = ITEM_ID_RE.search(url)
    return match.group(1) if match else None


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
    listings = parse_listings(html_text)
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
