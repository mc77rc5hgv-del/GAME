import avito_client as ac


def test_parse_via_jsonld():
    html_text = """
    <script type="application/ld+json">
    {"@context":"https://schema.org","@type":"ItemList","itemListElement":[
     {"@type":"ListItem","position":1,"item":{"@type":"Product","name":"iPhone 13 128GB &amp; чехол",
      "url":"https://www.avito.ru/moskva/telefony/iphone_13_128gb_1234567890",
      "offers":{"price":45000},"image":"https://img.avito.st/x.jpg"}}]}
    </script>
    """
    result = ac.parse_via_jsonld(html_text)
    assert len(result) == 1
    item = result[0]
    assert item.id == "1234567890"
    assert item.price == "45000"
    assert "&" in item.title


def test_parse_via_data_marker():
    html_text = (
        '<div data-marker="item" data-item-id="9876543210" class="iva-item">'
        '<a data-marker="item-title" href="/moskva/telefony/iphone_14_pro_9876543210" '
        'title="iPhone 14 Pro 256GB">iPhone 14 Pro 256GB</a>'
        '<img src="https://images.avito.ru/z.jpg"/>'
        '<p data-marker="item-price">85 000 &#8381;</p>'
        "</div>"
    )
    result = ac.parse_via_data_marker(html_text)
    assert len(result) == 1
    item = result[0]
    assert item.id == "9876543210"
    assert item.price == "85000"
    assert item.url.endswith("9876543210")
    assert item.image == "https://images.avito.ru/z.jpg"


def test_is_valid_avito_url():
    assert ac.is_valid_avito_url("https://www.avito.ru/moskva?q=iphone")
    assert ac.is_valid_avito_url("https://m.avito.ru/moskva")
    assert not ac.is_valid_avito_url("https://evil.com/avito.ru")
    assert not ac.is_valid_avito_url("not a url")


def test_apply_client_filters_excludes_keywords_and_price_range():
    listings = [
        ac.Listing(id="1", title="iPhone 13 битый экран", url="u1", price="10000"),
        ac.Listing(id="2", title="iPhone 13 новый", url="u2", price="45000"),
        ac.Listing(id="3", title="iPhone 13 на запчасти", url="u3", price="5000"),
        ac.Listing(id="4", title="iPhone 13 хороший", url="u4", price=""),
        ac.Listing(id="5", title="iPhone 13 дорогой", url="u5", price="90000"),
    ]
    result = ac.apply_client_filters(
        listings, exclude_keywords=["битый", "запчасти"], price_min=8000, price_max=60000
    )
    assert [i.id for i in result] == ["2", "4"]


def test_apply_client_filters_no_bounds_is_noop():
    listings = [ac.Listing(id="1", title="x", url="u", price="123")]
    assert ac.apply_client_filters(listings) == listings
