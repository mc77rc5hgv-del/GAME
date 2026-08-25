import json
from unittest.mock import MagicMock, patch


async def test_addfilter_one_shot_and_duplicate(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 555
    fake_html = (
        '<div data-marker="item" data-item-id="1">'
        '<a data-marker="item-title" href="/a_1" title="A">A</a>'
        '<p data-marker="item-price">1 000</p></div>'
    )
    with patch.object(bot.avito_client, "fetch", return_value=(fake_html, 200)):
        upd = fake_update(chat_id, args=["iphone", "https://www.avito.ru/moskva?q=iphone"])
        ctx = fake_context(args=["iphone", "https://www.avito.ru/moskva?q=iphone"])
        state = await bot.cmd_addfilter(upd, ctx)

    assert state == bot.ConversationHandler.END
    assert bot.db.filter_exists(chat_id, "iphone")

    upd2 = fake_update(chat_id, args=["iphone", "https://www.avito.ru/x"])
    ctx2 = fake_context(args=["iphone", "https://www.avito.ru/x"])
    await bot.cmd_addfilter(upd2, ctx2)
    assert "уже есть" in upd2.message.reply_text.call_args[0][0]


async def test_addfilter_rejects_non_avito_url(bot_module, fake_update, fake_context):
    bot = bot_module
    upd = fake_update(1, args=["bad", "https://evil.com"])
    ctx = fake_context(args=["bad", "https://evil.com"])
    state = await bot.cmd_addfilter(upd, ctx)
    assert state == bot.ASK_URL
    assert not bot.db.filter_exists(1, "bad")


async def test_addfilter_url_method_conversation(bot_module, fake_update, fake_context, fake_query, fake_cb_update):
    bot = bot_module
    chat_id = 777
    ctx = fake_context(args=[])
    upd0 = fake_update(chat_id)
    state = await bot.cmd_addfilter(upd0, ctx)
    assert state == bot.ADD_METHOD  # shows "по категории" / "по ссылке" choice first

    q = fake_query("addmethod:url", chat_id)
    state = await bot.addmethod_chosen(fake_cb_update(q), ctx)
    assert state == bot.ASK_NAME

    upd1 = fake_update(chat_id, text="cars")
    state = await bot.addfilter_got_name(upd1, ctx)
    assert state == bot.ASK_URL
    assert ctx.user_data["new_filter_name"] == "cars"

    fake_html = (
        '<div data-marker="item" data-item-id="9">'
        '<a data-marker="item-title" href="/c_9" title="Car">Car</a>'
        '<p data-marker="item-price">500000</p></div>'
    )
    with patch.object(bot.avito_client, "fetch", return_value=(fake_html, 200)):
        upd2 = fake_update(chat_id, text="https://www.avito.ru/moskva/avtomobili")
        state = await bot.addfilter_got_url(upd2, ctx)

    assert state == bot.ConversationHandler.END
    assert bot.db.filter_exists(chat_id, "cars")


async def test_addfilter_category_wizard_auto_save(bot_module, fake_context, fake_query, fake_cb_update):
    bot = bot_module
    chat_id = 778
    ctx = fake_context()

    q1 = fake_query("addmethod:category", chat_id)
    state = await bot.addmethod_chosen(fake_cb_update(q1), ctx)
    assert state == bot.PICK_CATEGORY
    assert ctx.user_data["wizard"] == {}

    q2 = fake_query("cat:2", chat_id)  # Электроника
    state = await bot.pick_category(fake_cb_update(q2), ctx)
    assert state == bot.PICK_SUBCAT
    assert ctx.user_data["wizard"]["cat_idx"] == 2

    q3 = fake_query("subcat:0", chat_id)  # Телефоны
    state = await bot.pick_subcat(fake_cb_update(q3), ctx)
    assert state == bot.PICK_CITY
    assert ctx.user_data["wizard"]["subcat_slug"] == "telefony"

    q4 = fake_query("city:1", chat_id)  # Москва
    state = await bot.pick_city(fake_cb_update(q4), ctx)
    assert state == bot.ASK_KEYWORD
    assert ctx.user_data["wizard"]["city_slug"] == "moskva"

    q5 = fake_query("wizkw:skip", chat_id)
    state = await bot.ask_keyword_button(fake_cb_update(q5), ctx)
    assert state == bot.ASK_PRICE

    q6 = fake_query("wizprice:skip", chat_id)
    fake_html = (
        '<div data-marker="item" data-item-id="1">'
        '<a data-marker="item-title" href="/a_1" title="X">X</a>'
        '<p data-marker="item-price">1000</p></div>'
    )
    with patch.object(bot.avito_client, "fetch", return_value=(fake_html, 200)):
        state = await bot.ask_price_button(fake_cb_update(q6), ctx)
        assert state == bot.PREVIEW
        assert ctx.user_data["wizard"]["url"] == "https://www.avito.ru/moskva/telefony"
        suggested = ctx.user_data["wizard"]["suggested_name"]
        assert suggested == "telefony-moskva"

        q7 = fake_query("wizsave:auto", chat_id)
        state = await bot.preview_action(fake_cb_update(q7), ctx)

    assert state == bot.ConversationHandler.END
    assert bot.db.filter_exists(chat_id, "telefony-moskva")
    assert bot.db.get_filter(chat_id, "telefony-moskva").url == "https://www.avito.ru/moskva/telefony"
    assert "wizard" not in ctx.user_data


async def test_addfilter_category_wizard_with_keyword_price_and_custom_name(
    bot_module, fake_context, fake_update, fake_query, fake_cb_update
):
    bot = bot_module
    chat_id = 779
    ctx = fake_context()
    ctx.user_data["wizard"] = {"cat_idx": 1}  # Транспорт

    q_subcat = fake_query("subcat:0", chat_id)  # Автомобили
    await bot.pick_subcat(fake_cb_update(q_subcat), ctx)
    q_city = fake_query("city:0", chat_id)  # Вся Россия
    await bot.pick_city(fake_cb_update(q_city), ctx)

    q_kw_ask = fake_query("wizkw:ask", chat_id)
    state = await bot.ask_keyword_button(fake_cb_update(q_kw_ask), ctx)
    assert state == bot.ASK_KEYWORD

    upd_kw = fake_update(chat_id, text="ваз 2107")
    state = await bot.ask_keyword_text(upd_kw, ctx)
    assert state == bot.ASK_PRICE
    assert ctx.user_data["wizard"]["keyword"] == "ваз 2107"

    q_price_ask = fake_query("wizprice:ask", chat_id)
    state = await bot.ask_price_button(fake_cb_update(q_price_ask), ctx)
    assert state == bot.ASK_PRICE

    bad_price = fake_update(chat_id, text="50000 10000")  # min > max
    state = await bot.ask_price_text(bad_price, ctx)
    assert state == bot.ASK_PRICE
    assert "больше" in bad_price.message.reply_text.call_args[0][0]

    fake_html = (
        '<div data-marker="item" data-item-id="1">'
        '<a data-marker="item-title" href="/a_1" title="X">X</a>'
        '<p data-marker="item-price">150000</p></div>'
    )
    with patch.object(bot.avito_client, "fetch", return_value=(fake_html, 200)):
        good_price = fake_update(chat_id, text="100000 300000")
        state = await bot.ask_price_text(good_price, ctx)
        assert state == bot.PREVIEW
        wiz_url = ctx.user_data["wizard"]["url"]
        assert "q=%D0%B2%D0%B0%D0%B7" in wiz_url  # url-encoded "ваз"
        assert "pmin=100000" in wiz_url and "pmax=300000" in wiz_url

        q_custom = fake_query("wizsave:custom", chat_id)
        state = await bot.preview_action(fake_cb_update(q_custom), ctx)
        assert state == bot.ASK_CUSTOM_NAME

        name_upd = fake_update(chat_id, text="my-vaz")
        state = await bot.custom_name_text(name_upd, ctx)

    assert state == bot.ConversationHandler.END
    assert bot.db.filter_exists(chat_id, "my-vaz")


async def test_wizard_back_navigation_and_cancel(bot_module, fake_context, fake_query, fake_cb_update):
    bot = bot_module
    chat_id = 780
    ctx = fake_context()
    ctx.user_data["wizard"] = {"cat_idx": 0}

    q_back = fake_query("wizback:category", chat_id)
    state = await bot.pick_subcat(fake_cb_update(q_back), ctx)
    assert state == bot.PICK_CATEGORY

    q_cancel = fake_query("wizcancel", chat_id)
    state = await bot.pick_category(fake_cb_update(q_cancel), ctx)
    assert state == bot.ConversationHandler.END
    assert "wizard" not in ctx.user_data


async def test_menu_button_interrupts_wizard(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 781
    ctx = fake_context()
    ctx.user_data["wizard"] = {"cat_idx": 0, "subcat_name": "x", "subcat_slug": "x", "city_name": "y", "city_slug": "y"}

    upd = fake_update(chat_id, text=bot.MENU_LIST)
    state = await bot.ask_keyword_text(upd, ctx)
    assert state == bot.ConversationHandler.END
    assert "wizard" not in ctx.user_data
    upd.message.reply_text.assert_called()  # cmd_myfilters replied ("no filters yet")


async def test_pause_resume_setinterval(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 10
    bot.db.add_filter(chat_id, "f", "https://www.avito.ru/x", 15)

    await bot.cmd_pause(fake_update(chat_id, args=["f"]), fake_context(args=["f"]))
    assert bot.db.get_filter(chat_id, "f").active is False

    await bot.cmd_resume(fake_update(chat_id, args=["f"]), fake_context(args=["f"]))
    assert bot.db.get_filter(chat_id, "f").active is True

    upd = fake_update(chat_id, args=["f", "1"])
    await bot.cmd_setinterval(upd, fake_context(args=["f", "1"]))
    assert "Минимальный" in upd.message.reply_text.call_args[0][0]

    await bot.cmd_setinterval(fake_update(chat_id, args=["f", "20"]), fake_context(args=["f", "20"]))
    assert bot.db.get_filter(chat_id, "f").interval_minutes == 20


async def test_rename_seturl_keywords_price(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 20
    bot.db.add_filter(chat_id, "bikes", "https://www.avito.ru/x", 15)

    await bot.cmd_renamefilter(
        fake_update(chat_id, args=["bikes", "cycles"]), fake_context(args=["bikes", "cycles"])
    )
    assert bot.db.filter_exists(chat_id, "cycles") and not bot.db.filter_exists(chat_id, "bikes")

    upd = fake_update(chat_id, args=["cycles", "https://evil.com"])
    await bot.cmd_seturl(upd, fake_context(args=["cycles", "https://evil.com"]))
    assert "avito.ru" in upd.message.reply_text.call_args[0][0]

    await bot.cmd_seturl(
        fake_update(chat_id, args=["cycles", "https://www.avito.ru/moskva?q=bike2"]),
        fake_context(args=["cycles", "https://www.avito.ru/moskva?q=bike2"]),
    )
    assert bot.db.get_filter(chat_id, "cycles").url == "https://www.avito.ru/moskva?q=bike2"

    await bot.cmd_setkeywords(
        fake_update(chat_id, args=["cycles", "битый,ржавый"]),
        fake_context(args=["cycles", "битый,ржавый"]),
    )
    assert bot.db.get_filter(chat_id, "cycles").exclude_keyword_list() == ["битый", "ржавый"]

    bad = fake_update(chat_id, args=["cycles", "50000", "1000"])
    await bot.cmd_setprice(bad, fake_context(args=["cycles", "50000", "1000"]))
    assert "больше" in bad.message.reply_text.call_args[0][0]

    await bot.cmd_setprice(
        fake_update(chat_id, args=["cycles", "1000", "50000"]),
        fake_context(args=["cycles", "1000", "50000"]),
    )
    f = bot.db.get_filter(chat_id, "cycles")
    assert (f.price_min, f.price_max) == (1000, 50000)


async def test_check_applies_price_filter_and_sends_photo(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 30
    bot.db.add_filter(chat_id, "cycles", "https://www.avito.ru/x", 15)
    bot.db.set_price_range(chat_id, "cycles", 1000, 50000)

    html1 = (
        '<div data-marker="item" data-item-id="1">'
        '<a data-marker="item-title" href="/a_1" title="Baseline">Baseline</a>'
        '<p data-marker="item-price">2000</p></div>'
    )
    with patch.object(bot.avito_client, "fetch", return_value=(html1, 200)):
        await bot.run_check(fake_context(), bot.db.get_filter(chat_id, "cycles"))

    html2 = html1 + (
        '<div data-marker="item" data-item-id="2">'
        '<a data-marker="item-title" href="/b_2" title="Cheap">Cheap</a>'
        '<p data-marker="item-price">500</p></div>'
        '<div data-marker="item" data-item-id="3">'
        '<a data-marker="item-title" href="/c_3" title="Good">Good</a>'
        '<img src="https://img.avito.st/c.jpg"/>'
        '<p data-marker="item-price">20000</p></div>'
    )
    ctx = fake_context()
    with patch.object(bot.avito_client, "fetch", return_value=(html2, 200)):
        await bot.run_check(ctx, bot.db.get_filter(chat_id, "cycles"))

    photo_texts = [c.kwargs.get("caption", "") for c in ctx.bot.send_photo.call_args_list]
    msg_texts = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    all_texts = photo_texts + msg_texts
    assert any("Good" in t for t in all_texts)
    assert not any("Cheap" in t for t in all_texts)
    assert ctx.bot.send_photo.call_count == 1  # "Good" has an image, sent via send_photo


async def test_price_drop_notification(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 40
    bot.db.add_filter(chat_id, "f", "https://www.avito.ru/x", 15)

    html1 = (
        '<div data-marker="item" data-item-id="1">'
        '<a data-marker="item-title" href="/a_1" title="Sofa">Sofa</a>'
        '<p data-marker="item-price">10000</p></div>'
    )
    with patch.object(bot.avito_client, "fetch", return_value=(html1, 200)):
        await bot.run_check(fake_context(), bot.db.get_filter(chat_id, "f"))  # baseline

    html2 = (
        '<div data-marker="item" data-item-id="1">'
        '<a data-marker="item-title" href="/a_1" title="Sofa">Sofa</a>'
        '<p data-marker="item-price">8000</p></div>'
    )
    ctx = fake_context()
    with patch.object(bot.avito_client, "fetch", return_value=(html2, 200)):
        result = await bot.run_check(ctx, bot.db.get_filter(chat_id, "f"))

    assert "снижений цены: 1" in result
    msg_texts = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("Было: 10000" in t and "стало: 8000" in t for t in msg_texts)


async def test_auto_pause_after_repeated_failures_then_resume(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 50
    fid = bot.db.add_filter(chat_id, "blocked", "https://www.avito.ru/z", 15)

    ctx = fake_context()
    with patch.object(bot.avito_client, "fetch", return_value=(None, 429)):
        for _ in range(3):  # AVITO_AUTOPAUSE_AFTER_FAILURES=3 in the fixture
            f = bot.db.get_filter_by_id(fid)
            await bot.run_check(ctx, f)

    f = bot.db.get_filter_by_id(fid)
    assert f.auto_paused is True and f.active is False
    texts = [c.kwargs.get("text", "") for c in ctx.bot.send_message.call_args_list]
    assert any("автоматически поставлен на паузу" in t for t in texts)

    await bot.cmd_resume(fake_update(chat_id, args=["blocked"]), fake_context(args=["blocked"]))
    f2 = bot.db.get_filter(chat_id, "blocked")
    assert f2.active is True and f2.auto_paused is False and f2.consecutive_failures == 0


async def test_button_pause_and_delete_flow(bot_module, fake_context, fake_query, fake_cb_update):
    bot = bot_module
    chat_id = 60
    fid = bot.db.add_filter(chat_id, "f", "https://www.avito.ru/x", 15)

    q = fake_query(f"pause:{fid}", chat_id)
    await bot.on_button(fake_cb_update(q), fake_context())
    assert bot.db.get_filter_by_id(fid).active is False

    q2 = fake_query(f"delrequest:{fid}", chat_id)
    await bot.on_button(fake_cb_update(q2), fake_context())
    q3 = fake_query(f"delconfirm:{fid}", chat_id)
    await bot.on_button(fake_cb_update(q3), fake_context())
    assert not bot.db.filter_exists(chat_id, "f")


async def test_button_interval_preset(bot_module, fake_context, fake_query, fake_cb_update):
    bot = bot_module
    chat_id = 61
    fid = bot.db.add_filter(chat_id, "f", "https://www.avito.ru/x", 15)

    q_open = fake_query(f"interval:{fid}", chat_id)
    await bot.on_button(fake_cb_update(q_open), fake_context())
    q_open.edit_message_text.assert_called()

    q_set = fake_query(f"setiv:{fid}:30", chat_id)
    await bot.on_button(fake_cb_update(q_set), fake_context())
    assert bot.db.get_filter_by_id(fid).interval_minutes == 30


async def test_on_button_ignores_stale_wizard_callback_data(bot_module, fake_context, fake_query, fake_cb_update):
    bot = bot_module
    chat_id = 62
    # No colon / non-numeric id — must not crash, and must not match a filter.
    for data in ("wizcancel", "wizback:category", "wizsave:auto"):
        q = fake_query(data, chat_id)
        await bot.on_button(fake_cb_update(q), fake_context())
        q.edit_message_text.assert_not_called()


async def test_broadcast_requires_admin(bot_module, fake_update, fake_context):
    bot = bot_module
    non_admin = fake_update(70, args=["hi"])
    await bot.cmd_broadcast(non_admin, fake_context(args=["hi"]))
    non_admin.message.reply_text.assert_not_called()

    bot.db.add_filter(70, "f", "https://www.avito.ru/x", 15)
    admin_upd = fake_update(999, args=["hello", "everyone"])
    await bot.cmd_broadcast(admin_upd, fake_context(args=["hello", "everyone"]))
    admin_upd.message.reply_text.assert_called()
    assert "1/1" in admin_upd.message.reply_text.call_args[0][0]


async def test_export_then_import_round_trip(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 80
    bot.db.add_filter(chat_id, "iphone", "https://www.avito.ru/x", 15)
    bot.db.set_exclude_keywords(chat_id, "iphone", "битый")
    bot.db.set_price_range(chat_id, "iphone", 1000, 5000)

    upd = fake_update(chat_id)
    await bot.cmd_export(upd, fake_context())
    upd.message.reply_document.assert_called()
    sent_file = upd.message.reply_document.call_args.kwargs["document"]
    payload = json.loads(sent_file.input_file_content.decode("utf-8"))
    assert payload[0]["name"] == "iphone"
    assert payload[0]["exclude_keywords"] == "битый"

    bot.db.delete_filter(chat_id, "iphone")
    assert not bot.db.filter_exists(chat_id, "iphone")

    import_upd = fake_update(chat_id)
    import_upd.message.document = MagicMock()
    import_upd.message.document.file_name = "avito_filters.json"
    import_upd.message.document.file_id = "abc"
    ctx = fake_context()
    tg_file = MagicMock()

    async def _download():
        return bytearray(json.dumps(payload).encode("utf-8"))

    tg_file.download_as_bytearray = _download
    ctx.bot.get_file.return_value = tg_file

    await bot.cmd_import_document(import_upd, ctx)
    assert bot.db.filter_exists(chat_id, "iphone")
    restored = bot.db.get_filter(chat_id, "iphone")
    assert restored.exclude_keyword_list() == ["битый"]
    assert (restored.price_min, restored.price_max) == (1000, 5000)


async def test_import_skips_invalid_and_duplicate_entries(bot_module, fake_update, fake_context):
    bot = bot_module
    chat_id = 90
    bot.db.add_filter(chat_id, "existing", "https://www.avito.ru/x", 15)

    payload = [
        {"name": "existing", "url": "https://www.avito.ru/y"},  # duplicate name -> skipped
        {"name": "bad", "url": "https://evil.com"},  # invalid url -> invalid
        {"name": "ok", "url": "https://www.avito.ru/z"},  # valid -> added
        "not-a-dict",  # invalid -> invalid
    ]
    upd = fake_update(chat_id)
    upd.message.document = MagicMock()
    upd.message.document.file_name = "filters.json"
    upd.message.document.file_id = "abc"
    ctx = fake_context()
    tg_file = MagicMock()

    async def _download():
        return bytearray(json.dumps(payload).encode("utf-8"))

    tg_file.download_as_bytearray = _download
    ctx.bot.get_file.return_value = tg_file

    await bot.cmd_import_document(upd, ctx)
    assert bot.db.filter_exists(chat_id, "ok")
    text = upd.message.reply_text.call_args[0][0]
    assert "добавлено 1" in text
    assert "пропущено (уже есть) 1" in text
    assert "некорректных записей 2" in text
