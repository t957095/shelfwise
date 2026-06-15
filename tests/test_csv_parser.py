import pytest

from backend.csv_parser import (
    clean_upc,
    detect_columns,
    parse_pos_csv,
    preview_pos_csv,
)


def test_detect_columns_finds_upc():
    fieldnames = ["id", "upc", "product_name", "brand", "price", "image_1"]
    columns = detect_columns(fieldnames)
    assert columns["upc"] == "upc"
    assert columns["name"] in {"product_name", "name"}
    assert columns["brand"] == "brand"
    assert columns["price"] == "price"
    assert columns["images"] == ["image_1"]


def test_detect_columns_aliases():
    fieldnames = ["Item Number", "Barcode", "Item Name", "Vendor", "Retail Price", "Photo"]
    columns = detect_columns(fieldnames)
    assert columns["upc"] == "Barcode"
    assert columns["name"] == "Item Name"
    assert columns["brand"] == "Vendor"
    assert columns["price"] == "Retail Price"
    assert columns["images"] == ["Photo"]


def test_clean_upc_strips_decimal():
    assert clean_upc("200104000009.0") == "200104000009"
    assert clean_upc(200104000009.0) == "200104000009"
    assert clean_upc("  499132680127  ") == "499132680127"
    assert clean_upc("abc-123") == "abc-123"


def test_clean_upc_rejects_empty():
    assert clean_upc("") is None
    assert clean_upc(None) is None


def test_parse_pos_csv_basic():
    content = b"id,upc,product_name,brand,price,image_1\n1,200104000009.0,Beef shank,Shan,20.97,\n2,499132680127.0,Crescent chicken,Crescent,2.99,\n"
    upcs, seeds, columns, truncated = parse_pos_csv(content)
    assert upcs == ["200104000009", "499132680127"]
    assert not truncated
    assert seeds[0]["name"] == "Beef shank"
    assert seeds[0]["brand"] == "Shan"
    assert seeds[0]["price"] == 20.97


def test_parse_pos_csv_respects_max_rows():
    rows = "id,upc\n" + "\n".join(f"{i},{i:012d}.0" for i in range(1, 11))
    upcs, _, _, truncated = parse_pos_csv(rows.encode("utf-8"), max_rows=5)
    assert len(upcs) == 5
    assert truncated is True


def test_parse_pos_csv_skips_local_image_paths():
    content = b"upc,product_name,image_1\n499132680127.0,Chicken,assets/products/x.jpg\n"
    upcs, seeds, _, _ = parse_pos_csv(content)
    assert "image_urls" not in seeds[0]


def test_parse_pos_csv_keeps_public_image_urls():
    content = b"upc,product_name,image_1\n499132680127.0,Chicken,https://example.com/x.jpg\n"
    upcs, seeds, _, _ = parse_pos_csv(content)
    assert seeds[0].get("image_urls") == ["https://example.com/x.jpg"]


def test_preview_pos_csv():
    content = b"upc,product_name\n200104000009.0,Beef\n499132680127.0,Chicken\n"
    preview = preview_pos_csv(content, max_rows=5)
    assert preview["total_upcs"] == 2
    assert preview["truncated"] is False
    assert len(preview["sample"]) == 2


def test_parse_pos_csv_missing_upc_column_raises():
    content = b"foo,bar\n1,2\n"
    with pytest.raises(ValueError):
        parse_pos_csv(content)


def test_parse_pos_csv_latin1_encoding():
    content = "upc,product_name\n123456789012.0,Café\n".encode("latin-1")
    upcs, seeds, _, _ = parse_pos_csv(content)
    assert upcs == ["123456789012"]
    assert seeds[0]["name"] == "Café"
