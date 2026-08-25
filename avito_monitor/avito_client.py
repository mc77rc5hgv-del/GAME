"""Fetching and parsing of Avito search-result pages.

Shared by the cron-style monitor.py script and the interactive bot.py.
Avito changes its markup periodically; if parsing starts returning zero
listings on pages that clearly have some, update parse_via_data_marker.
"""
from __future__ import annotations

import html
import json
import random
import re
import time
import urllib.parse
from dataclasses import dataclass

import requests

MAX_FETCH_RETRIES = 4
REQUEST_TIMEOUT = 20

USER_AGENTS = [
    "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/124.0.0.0 Safari/537.36",
    "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/17.4 Safari/605.1.15",
    "Mozilla/5.0 (X11; Linux x86_64; rv:126.0) Gecko/20100101 Firefox/126.0",
]

ITEM_ID_RE = re.compile(r"_(\d{6,})(?:[/?]|$)")
AVITO_URL_RE = re.compile(r"^https?://(www\.|m\.)?avito\.ru/", re.I)


@dataclass
class Listing:
    id: str
    title: str
    url: str
    price: str = ""
    image: str = ""


def is_valid_avito_url(url: str) -> bool:
    return bool(AVITO_URL_RE.match(url.strip()))


def fetch(url: str) -> tuple[str | None, int | None]:
    """Returns (html, last_status_code). html is None if all retries failed."""
    session = requests.Session()
    last_status: int | None = None
    for attempt in range(1, MAX_FETCH_RETRIES + 1):
        headers = {
            "User-Agent": random.choice(USER_AGENTS),
            "Accept": "text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
            "Accept-Language": "ru-RU,ru;q=0.9,en-US;q=0.8,en;q=0.7",
        }
        try:
            resp = session.get(url, headers=headers, timeout=REQUEST_TIMEOUT)
            last_status = resp.status_code
        except requests.RequestException:
            resp = None
            last_status = None

        if resp is not None and resp.status_code == 200 and "data-marker" in resp.text:
            return resp.text, 200

        if attempt < MAX_FETCH_RETRIES:
            time.sleep(2 ** attempt + random.uniform(0, 1.5))

    return None, last_status


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

        price_match = re.search(r'data-marker="item-price"[^>]*>\s*([\d\s ]+)', window)
        price = re.sub(r"[\s ]", "", price_match.group(1)) if price_match else ""

        image_match = re.search(r'<img[^>]+src="(https://[^"]+)"', window)
        image = image_match.group(1) if image_match else ""

        if title and url:
            listings.append(Listing(id=item_id, title=title, url=url, price=price, image=image))
    return listings


def extract_item_id(url: str) -> str | None:
    match = ITEM_ID_RE.search(url)
    return match.group(1) if match else None


def apply_client_filters(
    listings: list[Listing],
    exclude_keywords: list[str] | None = None,
    price_min: int = 0,
    price_max: int = 0,
) -> list[Listing]:
    """Extra filtering on top of whatever the Avito search URL already does:
    drop listings whose title contains a blacklisted word, or whose price
    falls outside [price_min, price_max] (0 = no bound on that side).
    Listings with no parsed price pass any price bound (can't tell).
    """
    exclude_keywords = [w.lower() for w in (exclude_keywords or []) if w]
    result = []
    for item in listings:
        title_lower = item.title.lower()
        if any(word in title_lower for word in exclude_keywords):
            continue
        if item.price.isdigit():
            price = int(item.price)
            if price_min and price < price_min:
                continue
            if price_max and price > price_max:
                continue
        result.append(item)
    return result
