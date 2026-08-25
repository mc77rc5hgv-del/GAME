"""Curated category/city picker data for the guided "add filter" flow.

This environment can't reach avito.ru at all (blocked at the network
level — see README), so this list could not be verified against the
live site. It's built from long-stable, widely-attested Avito URL slugs
and covers the most commonly used categories, not Avito's full taxonomy.
Anything not covered here can still be added the original way: copy a
search URL from avito.ru after configuring filters there (see the
"🔗 Вставить ссылку" option in /addfilter).

Because a slug could be stale or wrong, the bot always shows the built
link with a "Проверить на Avito" button before saving a filter — so a
bad guess is caught immediately instead of silently failing later.
"""
from __future__ import annotations

from urllib.parse import quote

# (category label, [(subcategory label, url slug), ...])
CATEGORIES: list[tuple[str, list[tuple[str, str]]]] = [
    (
        "🏠 Недвижимость",
        [
            ("Квартиры", "kvartiry"),
            ("Комнаты", "komnaty"),
            ("Дома, дачи, коттеджи", "doma_dachi_kottedzhi"),
            ("Земельные участки", "zemelnye_uchastki"),
            ("Гаражи и машиноместа", "garazhi_i_mashinomesta"),
        ],
    ),
    (
        "🚗 Транспорт",
        [
            ("Автомобили", "avtomobili"),
            ("Мотоциклы и мототехника", "mototsikly_i_mototehnika"),
            ("Грузовики и спецтехника", "gruzoviki_i_spetstehnika"),
            ("Запчасти и аксессуары", "zapchasti_i_aksessuary"),
        ],
    ),
    (
        "📱 Электроника",
        [
            ("Телефоны", "telefony"),
            ("Ноутбуки", "noutbuki"),
            ("Планшеты и электронные книги", "planshety_i_elektronnye_knigi"),
            ("Аудио и видео", "audio_i_video"),
            ("Игры, приставки и программы", "igry_pristavki_i_programmy"),
            ("Фототехника", "foto"),
        ],
    ),
    (
        "👗 Личные вещи",
        [
            ("Одежда, обувь, аксессуары", "odezhda_obuv_aksessuary"),
            ("Детская одежда и обувь", "detskaya_odezhda_i_obuv"),
            ("Часы и украшения", "chasy_i_ukrasheniya"),
            ("Красота и здоровье", "krasota_i_zdorove"),
        ],
    ),
    (
        "🏡 Для дома и дачи",
        [
            ("Мебель и интерьер", "mebel_i_interer"),
            ("Бытовая техника", "bytovaya_tehnika"),
            ("Посуда и товары для кухни", "posuda_i_tovary_dlya_kuhni"),
            ("Ремонт и строительство", "remont_i_stroitelstvo"),
        ],
    ),
    (
        "🎸 Хобби и отдых",
        [
            ("Велосипеды", "velosipedy"),
            ("Книги и журналы", "knigi_i_zhurnaly"),
            ("Музыкальные инструменты", "muzykalnye_instrumenty"),
            ("Спорт и отдых", "sport_i_otdyh"),
            ("Коллекционирование", "kollektsionirovanie"),
        ],
    ),
    (
        "🐾 Животные",
        [
            ("Собаки", "sobaki"),
            ("Кошки", "koshki"),
            ("Птицы", "ptitsy"),
            ("Товары для животных", "tovary_dlya_zhivotnyh"),
        ],
    ),
]

# (city label, url slug); first entry is the "no specific city" option.
CITIES: list[tuple[str, str]] = [
    ("Вся Россия", "rossiya"),
    ("Москва", "moskva"),
    ("Санкт-Петербург", "sankt-peterburg"),
    ("Новосибирск", "novosibirsk"),
    ("Екатеринбург", "ekaterinburg"),
    ("Казань", "kazan"),
    ("Нижний Новгород", "nizhniy_novgorod"),
    ("Челябинск", "chelyabinsk"),
    ("Самара", "samara"),
    ("Ростов-на-Дону", "rostov-na-donu"),
    ("Уфа", "ufa"),
    ("Краснодар", "krasnodar"),
]


def build_search_url(
    city_slug: str,
    category_slug: str,
    keyword: str = "",
    price_min: int = 0,
    price_max: int = 0,
) -> str:
    url = f"https://www.avito.ru/{city_slug}/{category_slug}"
    params = []
    if keyword:
        params.append(f"q={quote(keyword)}")
    if price_min:
        params.append(f"pmin={price_min}")
    if price_max:
        params.append(f"pmax={price_max}")
    if params:
        url += "?" + "&".join(params)
    return url
