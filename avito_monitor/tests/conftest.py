import importlib
import sys
import tempfile
from pathlib import Path
from unittest.mock import AsyncMock, MagicMock

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))


@pytest.fixture
def bot_module(monkeypatch):
    """Fresh, isolated import of bot.py: its own temp SQLite db, dummy
    token, and small thresholds so failure/auto-pause paths are easy to
    trigger in a handful of iterations instead of dozens.
    """
    monkeypatch.setenv("AVITO_BOT_DB", tempfile.mktemp(suffix=".db"))
    monkeypatch.setenv("TELEGRAM_BOT_TOKEN", "dummy:token")
    monkeypatch.setenv("AVITO_ALERT_AFTER_FAILURES", "2")
    monkeypatch.setenv("AVITO_ALERT_COOLDOWN_SECONDS", "9999999")
    monkeypatch.setenv("AVITO_AUTOPAUSE_AFTER_FAILURES", "3")
    monkeypatch.setenv("AVITO_ADMIN_CHAT_ID", "999")
    monkeypatch.delenv("AVITO_ALLOWED_CHAT_IDS", raising=False)

    import bot as bot_mod

    importlib.reload(bot_mod)
    return bot_mod


class FakeMsg:
    def __init__(self, text=""):
        self.text = text
        self.document = None
        self.reply_text = AsyncMock()
        self.reply_html = AsyncMock()
        self.reply_document = AsyncMock()


class FakeChat:
    def __init__(self, cid):
        self.id = cid


class FakeUpdate:
    def __init__(self, chat_id, text="", args=None):
        self.effective_chat = FakeChat(chat_id)
        self.message = FakeMsg(text)
        self.effective_message = self.message
        self.callback_query = None


class FakeQuery:
    """Fakes telegram.CallbackQuery for testing inline-button handlers."""

    def __init__(self, data, chat_id):
        self.data = data
        self.message = FakeMsg()
        self.message.chat_id = chat_id
        self.answer = AsyncMock()
        self.edit_message_text = AsyncMock()
        self.edit_message_reply_markup = AsyncMock()


class FakeCBUpdate:
    """Fakes telegram.Update for a callback-query-triggered update."""

    def __init__(self, query):
        self.callback_query = query
        self.effective_chat = FakeChat(query.message.chat_id)
        self.effective_message = query.message
        self.message = None


class FakeContext:
    def __init__(self, args=None):
        self.args = args or []
        self.user_data = {}
        self.bot = MagicMock()
        self.bot.send_message = AsyncMock()
        self.bot.send_photo = AsyncMock()
        self.bot.send_document = AsyncMock()
        self.bot.get_file = AsyncMock()


@pytest.fixture
def fake_update():
    return FakeUpdate


@pytest.fixture
def fake_context():
    return FakeContext


@pytest.fixture
def fake_query():
    return FakeQuery


@pytest.fixture
def fake_cb_update():
    return FakeCBUpdate
