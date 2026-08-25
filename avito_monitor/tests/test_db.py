import sqlite3
import tempfile
import time

import pytest

from db import Database


@pytest.fixture
def db(tmp_path):
    return Database(tmp_path / "test.db")


def test_add_and_get_filter(db):
    fid = db.add_filter(chat_id=1, name="iphone", url="https://www.avito.ru/x", interval_minutes=15)
    assert db.filter_exists(1, "iphone")
    assert db.count_filters(1) == 1
    assert not db.filter_exists(1, "other")

    f = db.get_filter(1, "iphone")
    assert f.id == fid
    assert f.active is True
    assert f.interval_minutes == 15
    assert f.exclude_keywords == "" and f.price_min == 0 and f.price_max == 0
    assert f.auto_paused is False


def test_due_filters_respect_interval(db):
    fid = db.add_filter(1, "iphone", "https://www.avito.ru/x", interval_minutes=15)
    now = time.time()

    # freshly created (last_checked_at=0) is immediately due
    assert len(db.list_due_filters(now=now)) == 1

    db.mark_checked(fid, success=True, new_found=2)
    assert db.get_filter_by_id(fid).total_found == 2
    assert db.list_due_filters(now=time.time()) == []
    assert len(db.list_due_filters(now=time.time() + 16 * 60)) == 1


def test_mark_checked_failure_increments_streak(db):
    fid = db.add_filter(1, "iphone", "https://www.avito.ru/x", interval_minutes=15)
    db.mark_checked(fid, success=False)
    db.mark_checked(fid, success=False)
    f = db.get_filter_by_id(fid)
    assert f.consecutive_failures == 2

    db.mark_checked(fid, success=True, new_found=0)
    assert db.get_filter_by_id(fid).consecutive_failures == 0


def test_record_seen_upserts_price_and_bumps_seen_at(db):
    fid = db.add_filter(1, "x", "https://www.avito.ru/x", 15)
    db.record_seen(fid, [("1", "1000"), ("2", "")])
    assert db.get_seen_prices(fid) == {"1": "1000", "2": ""}

    time.sleep(0.01)
    db.record_seen(fid, [("1", "900")])
    assert db.get_seen_prices(fid)["1"] == "900"
    assert db.get_seen_ids(fid) == {"1", "2"}


def test_record_seen_prunes_oldest_but_keeps_still_live_items(db, monkeypatch):
    import db as db_mod

    monkeypatch.setattr(db_mod, "MAX_SEEN_PER_FILTER", 2)
    fid = db.add_filter(1, "x", "https://www.avito.ru/x", 15)

    db.record_seen(fid, [("old", "1")])
    time.sleep(0.01)
    db.record_seen(fid, [("mid", "2")])
    time.sleep(0.01)
    # "old" is re-seen (still on the site) so it must not be evicted next
    db.record_seen(fid, [("old", "1"), ("new", "3")])

    assert db.get_seen_ids(fid) == {"old", "new"}


def test_rename_and_seturl_preserve_id(db):
    fid = db.add_filter(1, "old", "https://www.avito.ru/x", 15)
    assert db.rename_filter(1, "old", "new")
    assert db.get_filter_by_id(fid).name == "new"
    assert db.set_url(1, "new", "https://www.avito.ru/y")
    assert db.get_filter_by_id(fid).url == "https://www.avito.ru/y"


def test_exclude_keywords_and_price_range(db):
    db.add_filter(1, "x", "https://www.avito.ru/x", 15)
    assert db.set_exclude_keywords(1, "x", "битый, ржавый")
    assert db.get_filter(1, "x").exclude_keyword_list() == ["битый", "ржавый"]
    assert db.set_price_range(1, "x", 1000, 5000)
    f = db.get_filter(1, "x")
    assert (f.price_min, f.price_max) == (1000, 5000)


def test_auto_pause_and_resume(db):
    fid = db.add_filter(1, "x", "https://www.avito.ru/x", 15)
    db.set_auto_paused(fid, True)
    f = db.get_filter_by_id(fid)
    assert f.active is False and f.auto_paused is True

    assert db.set_active(1, "x", True)
    f2 = db.get_filter_by_id(fid)
    assert f2.active is True and f2.auto_paused is False and f2.consecutive_failures == 0


def test_delete_filter_cascades_seen_items(tmp_path):
    db = Database(tmp_path / "cascade.db")
    fid = db.add_filter(1, "x", "https://www.avito.ru/x", 15)
    db.record_seen(fid, [("1", "100"), ("2", "200")])
    assert db.delete_filter(1, "x")

    conn = sqlite3.connect(db.path)
    rows = conn.execute("SELECT * FROM seen_items").fetchall()
    conn.close()
    assert rows == []


def test_migration_from_pre_extension_schema(tmp_path):
    path = tmp_path / "legacy.db"
    conn = sqlite3.connect(path)
    conn.executescript(
        """
        CREATE TABLE filters (
            id INTEGER PRIMARY KEY AUTOINCREMENT, chat_id INTEGER NOT NULL, name TEXT NOT NULL,
            url TEXT NOT NULL, interval_minutes INTEGER NOT NULL DEFAULT 15,
            active INTEGER NOT NULL DEFAULT 1, last_checked_at REAL NOT NULL DEFAULT 0,
            last_found_at REAL NOT NULL DEFAULT 0, total_found INTEGER NOT NULL DEFAULT 0,
            consecutive_failures INTEGER NOT NULL DEFAULT 0, last_alert_at REAL NOT NULL DEFAULT 0,
            created_at REAL NOT NULL, UNIQUE(chat_id, name)
        );
        CREATE TABLE seen_items (
            filter_id INTEGER NOT NULL REFERENCES filters(id) ON DELETE CASCADE,
            item_id TEXT NOT NULL, seen_at REAL NOT NULL, PRIMARY KEY (filter_id, item_id)
        );
        """
    )
    conn.execute(
        "INSERT INTO filters (chat_id, name, url, created_at) VALUES (1, 'old', 'https://www.avito.ru/x', 0)"
    )
    fid = conn.execute("SELECT id FROM filters").fetchone()[0]
    conn.execute("INSERT INTO seen_items (filter_id, item_id, seen_at) VALUES (?, '5', 0)", (fid,))
    conn.commit()
    conn.close()

    db = Database(path)
    f = db.get_filter(1, "old")
    assert f.exclude_keywords == "" and f.price_min == 0 and f.price_max == 0
    assert f.auto_paused is False
    assert db.get_seen_prices(fid) == {"5": ""}
    db.record_seen(fid, [("5", "1234")])
    assert db.get_seen_prices(fid) == {"5": "1234"}
