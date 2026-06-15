"""POS CSV parser for ShelfWise.

Handles real-world point-of-sale exports with messy headers, numeric UPCs,
quoted fields, mixed encodings, and local image paths. Extracts a clean list
of UPCs plus optional seed data (name, brand, category, description, price,
images) that the reasoning agent can use as a starting point.
"""

from __future__ import annotations

import csv
import io
import logging
import re
from typing import Any, Dict, List, Optional, Tuple

logger = logging.getLogger("shelfwise.csv_parser")

# Common header aliases seen in POS and inventory exports
UPC_ALIASES = {
    "upc",
    "upc_code",
    "upc code",
    "barcode",
    "bar_code",
    "bar code",
    "ean",
    "ean13",
    "ean-13",
    "sku",
    "item_sku",
    "item sku",
    "plu",
    "item_number",
    "item number",
    "item_no",
    "item no",
    "itemcode",
    "item_code",
    "item code",
    "product_code",
    "product code",
    "product_id",
    "product id",
    "productid",
    "id",
    "code",
}

NAME_ALIASES = {
    "product_name",
    "product name",
    "name",
    "title",
    "item_name",
    "item name",
    "description",
    "item_description",
    "item description",
}

BRAND_ALIASES = {
    "brand",
    "brand_name",
    "brand name",
    "manufacturer",
    "vendor",
    "supplier",
}

CATEGORY_ALIASES = {
    "category",
    "category_name",
    "category name",
    "department",
    "class",
    "subcategory",
    "sub_category",
    "sub category",
}

PRICE_ALIASES = {
    "price",
    "retail_price",
    "retail price",
    "sale_price",
    "sale price",
    "unit_price",
    "unit price",
    "cost",
    "msrp",
}

IMAGE_ALIASES = [
    "image",
    "image_url",
    "image url",
    "image_src",
    "image src",
    "photo",
    "picture",
    "thumbnail",
    "image_1",
    "image_2",
    "image_3",
    "image_4",
    "image_5",
    "image1",
    "image2",
    "image3",
    "image4",
    "image5",
]


def _normalize_header(header: str) -> str:
    """Normalize a CSV header for alias matching."""
    if header is None:
        return ""
    return re.sub(r"[\s_-]+", " ", header.strip().lower())


def _find_column(fieldnames: List[str], aliases: set) -> Optional[str]:
    """Return the first fieldname that matches one of the aliases."""
    normalized = {f: _normalize_header(f) for f in fieldnames}
    for alias in aliases:
        for field, norm in normalized.items():
            if norm == alias or norm.replace(" ", "_") == alias.replace(" ", "_"):
                return field
    return None


def _find_image_columns(fieldnames: List[str]) -> List[str]:
    """Return image column names in deterministic order."""
    normalized = {f: _normalize_header(f) for f in fieldnames}
    found = []
    seen = set()
    # Prefer numbered image columns first
    ordered = [f"image_{i}" for i in range(1, 21)] + [f"image{i}" for i in range(1, 21)] + IMAGE_ALIASES
    for alias in ordered:
        for field, norm in normalized.items():
            key = norm.replace(" ", "_")
            if key == alias and field not in seen:
                found.append(field)
                seen.add(field)
    return found


def detect_columns(fieldnames: List[str]) -> Dict[str, Optional[str]]:
    """Map canonical field names to actual CSV headers."""
    return {
        "upc": _find_column(fieldnames, UPC_ALIASES),
        "name": _find_column(fieldnames, NAME_ALIASES),
        "brand": _find_column(fieldnames, BRAND_ALIASES),
        "category": _find_column(fieldnames, CATEGORY_ALIASES),
        "price": _find_column(fieldnames, PRICE_ALIASES),
        "images": _find_image_columns(fieldnames),
    }


def _clean_text(value: Any) -> Optional[str]:
    """Clean a text field, returning None if empty."""
    if value is None:
        return None
    text = str(value).strip()
    # Strip trailing .0 from numeric strings
    if re.fullmatch(r"\d+\.0+", text):
        text = text.split(".")[0]
    return text if text else None


def clean_upc(value: Any) -> Optional[str]:
    """Normalize a UPC/EAN/SKU value from a POS export."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None

    # Handle floats like "200104000009.0" or "499132680127.0"
    try:
        if "." in text:
            float_val = float(text)
            # If it's an integer-valued float, convert to int string
            if float_val.is_integer():
                text = str(int(float_val))
    except ValueError:
        pass

    # Remove any non-digit characters except letters (for SKUs)
    # Preserve alphanumeric for SKUs, but strip whitespace and quotes
    text = re.sub(r"[\s\"']+", "", text)
    if not text:
        return None

    # For pure numeric codes, drop leading zeros only if length is reasonable
    # (keep EAN-13 and UPC-A as-is; leading zeros matter)
    if text.isdigit():
        # Keep the raw numeric string; downstream can pad if needed
        return text

    return text


def _clean_price(value: Any) -> Optional[float]:
    """Extract a float price from a POS price field."""
    if value is None:
        return None
    text = str(value).strip()
    if not text:
        return None
    # Remove currency symbols and commas
    text = re.sub(r"[$€£,]", "", text)
    try:
        return float(text)
    except ValueError:
        return None


def _is_url(value: str) -> bool:
    """Return True if the value looks like a public HTTP URL."""
    return value.startswith("http://") or value.startswith("https://")


def extract_seed_data(row: Dict[str, Any], columns: Dict[str, Optional[str]]) -> Dict[str, Any]:
    """Extract seed metadata from a CSV row to bootstrap enrichment."""
    seed: Dict[str, Any] = {}

    name_col = columns.get("name")
    if name_col:
        name = _clean_text(row.get(name_col))
        if name:
            seed["name"] = name

    brand_col = columns.get("brand")
    if brand_col:
        brand = _clean_text(row.get(brand_col))
        if brand:
            seed["brand"] = brand

    category_col = columns.get("category")
    if category_col:
        category = _clean_text(row.get(category_col))
        if category:
            seed["category"] = category

    price_col = columns.get("price")
    if price_col:
        price = _clean_price(row.get(price_col))
        if price is not None:
            seed["price"] = price

    image_cols = columns.get("images") or []
    image_urls = []
    for col in image_cols:
        val = _clean_text(row.get(col))
        if val and _is_url(val):
            image_urls.append(val)
    if image_urls:
        seed["image_urls"] = image_urls

    return seed


def _decode_csv(content: bytes) -> str:
    """Decode CSV bytes, trying common encodings."""
    for encoding in ("utf-8-sig", "utf-8", "latin-1", "cp1252"):
        try:
            return content.decode(encoding)
        except UnicodeDecodeError:
            continue
    # Last resort
    return content.decode("utf-8", errors="replace")


def parse_pos_csv(
    content: bytes,
    max_rows: Optional[int] = None,
) -> Tuple[List[str], List[Dict[str, Any]], Dict[str, Optional[str]], bool]:
    """Parse a POS CSV export.

    Returns:
        - upcs: list of cleaned UPC/barcode/SKU values
        - seeds: list of seed data dicts aligned with upcs
        - columns: detected column mapping
        - truncated: whether the file was truncated to max_rows
    """
    text = _decode_csv(content)
    reader = csv.DictReader(io.StringIO(text))
    fieldnames = reader.fieldnames or []
    if not fieldnames:
        raise ValueError("CSV has no headers")

    columns = detect_columns(fieldnames)
    upc_col = columns.get("upc")
    if not upc_col:
        raise ValueError(f"Could not find a UPC/barcode/SKU column. Headers found: {fieldnames}")

    upcs: List[str] = []
    seeds: List[Dict[str, Any]] = []
    seen: set = set()

    for idx, row in enumerate(reader):
        if max_rows is not None and len(upcs) >= max_rows:
            break
        raw = row.get(upc_col)
        upc = clean_upc(raw)
        if not upc or upc in seen:
            continue
        seen.add(upc)
        upcs.append(upc)
        seeds.append(extract_seed_data(row, columns))

    truncated = max_rows is not None and len(upcs) >= max_rows
    return upcs, seeds, columns, truncated


def preview_pos_csv(content: bytes, max_rows: int = 5) -> Dict[str, Any]:
    """Return a preview of a POS CSV for the frontend uploader."""
    upcs, seeds, columns, truncated = parse_pos_csv(content, max_rows=max_rows)
    return {
        "detected_columns": columns,
        "total_upcs": len(upcs),
        "truncated": truncated,
        "sample": [{"upc": upc, "seed": seed} for upc, seed in zip(upcs[:max_rows], seeds[:max_rows])],
    }
