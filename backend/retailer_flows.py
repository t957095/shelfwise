"""Retailer-specific product discovery programs.

These task flows are deterministic retrieval plans the Foundry layer can
reason over and the scraper/image pipeline can execute directly. Each program
targets a retailer or specialty catalog that is useful for UPC/POS enrichment.
"""

from __future__ import annotations

import urllib.parse
from typing import Any, Dict, Iterable, List, Optional


RETAILER_PROGRAMS: List[Dict[str, Any]] = [
    {
        "name": "Amazon Marketplace",
        "domain": "amazon.com",
        "categories": ["marketplace", "all"],
        "templates": ["https://www.amazon.com/s?k={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "scrape_product_detail", "rank_images"],
    },
    {
        "name": "eBay Marketplace",
        "domain": "ebay.com",
        "categories": ["marketplace", "all"],
        "templates": ["https://www.ebay.com/sch/i.html?_nkw={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "scrape_product_detail", "rank_images"],
    },
    {
        "name": "Walmart",
        "domain": "walmart.com",
        "categories": ["grocery", "household", "cleaning", "pet care", "baby care", "personal care", "all"],
        "templates": ["https://www.walmart.com/search?q={query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Target",
        "domain": "target.com",
        "categories": ["grocery", "household", "cleaning", "pet care", "baby care", "personal care", "all"],
        "templates": ["https://www.target.com/s?searchTerm={query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Sam's Club",
        "domain": "samsclub.com",
        "categories": ["grocery", "household", "cleaning", "beverages", "snacks", "all"],
        "templates": ["https://www.samsclub.com/sams/search/searchResults.jsp?searchTerm={query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Costco",
        "domain": "costco.com",
        "categories": ["grocery", "household", "cleaning", "beverages", "snacks", "all"],
        "templates": ["https://www.costco.com/CatalogSearch?keyword={query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Kroger",
        "domain": "kroger.com",
        "categories": ["grocery", "beverages", "snacks", "frozen"],
        "templates": ["https://www.kroger.com/search?query={query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Chewy",
        "domain": "chewy.com",
        "categories": ["pet care"],
        "templates": ["https://www.chewy.com/s?query={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_pet_product_images"],
    },
    {
        "name": "Petco",
        "domain": "petco.com",
        "categories": ["pet care"],
        "templates": ["https://www.petco.com/shop/en/petcostore/search?query={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_pet_product_images"],
    },
    {
        "name": "PetSmart",
        "domain": "petsmart.com",
        "categories": ["pet care"],
        "templates": ["https://www.petsmart.com/search/?q={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_pet_product_images"],
    },
    {
        "name": "Tractor Supply",
        "domain": "tractorsupply.com",
        "categories": ["pet care", "household"],
        "templates": ["https://www.tractorsupply.com/tsc/search/{query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Home Depot",
        "domain": "homedepot.com",
        "categories": ["cleaning", "household", "hardware"],
        "templates": ["https://www.homedepot.com/s/{query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Lowe's",
        "domain": "lowes.com",
        "categories": ["cleaning", "household", "hardware"],
        "templates": ["https://www.lowes.com/search?searchTerm={query}"],
        "tasks": ["search_upc", "extract_json_ld", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Grainger",
        "domain": "grainger.com",
        "categories": ["cleaning", "household", "hardware", "office"],
        "templates": ["https://www.grainger.com/search?searchQuery={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Uline",
        "domain": "uline.com",
        "categories": ["cleaning", "household", "office"],
        "templates": ["https://www.uline.com/BL_86/Search?keywords={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Staples",
        "domain": "staples.com",
        "categories": ["office", "cleaning", "household"],
        "templates": ["https://www.staples.com/{query}/directory_{query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Office Depot",
        "domain": "officedepot.com",
        "categories": ["office"],
        "templates": ["https://www.officedepot.com/catalog/search.do?Ntt={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
    {
        "name": "Walgreens",
        "domain": "walgreens.com",
        "categories": ["personal care", "baby care", "health"],
        "templates": ["https://www.walgreens.com/search/results.jsp?Ntt={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
    {
        "name": "CVS",
        "domain": "cvs.com",
        "categories": ["personal care", "baby care", "health"],
        "templates": ["https://www.cvs.com/search?searchTerm={query}"],
        "tasks": ["search_upc", "extract_listing_cards", "extract_open_graph", "rank_images"],
    },
]


def category_key(category: Optional[str]) -> str:
    if not category:
        return ""
    normalized = str(category).strip().lower()
    if "pet" in normalized:
        return "pet care"
    if "clean" in normalized:
        return "cleaning"
    if "household" in normalized:
        return "household"
    if "baby" in normalized:
        return "baby care"
    if "personal" in normalized or "health" in normalized or "beauty" in normalized:
        return "personal care"
    if "beverage" in normalized or "drink" in normalized or "cola" in normalized:
        return "beverages"
    if "snack" in normalized or "cracker" in normalized or "cookie" in normalized:
        return "snacks"
    if "frozen" in normalized:
        return "frozen"
    if "office" in normalized:
        return "office"
    if "grocery" in normalized or "food" in normalized:
        return "grocery"
    return normalized


def retailer_programs_for_category(category: Optional[str], include_general: bool = True) -> List[Dict[str, Any]]:
    key = category_key(category)
    programs = []
    for program in RETAILER_PROGRAMS:
        categories = set(program.get("categories") or [])
        if key and key in categories:
            programs.append(program)
        elif include_general and "all" in categories:
            programs.append(program)
    return programs


def retailer_listing_urls(identifier: str, category: Optional[str] = None, include_general: bool = True) -> List[str]:
    encoded = urllib.parse.quote_plus(str(identifier or "").strip())
    if not encoded:
        return []
    urls: List[str] = []
    for program in retailer_programs_for_category(category, include_general=include_general):
        for template in program.get("templates") or []:
            url = template.format(query=encoded)
            if url not in urls:
                urls.append(url)
    return urls


def retailer_domains(category: Optional[str] = None, include_general: bool = True) -> List[str]:
    domains: List[str] = []
    for program in retailer_programs_for_category(category, include_general=include_general):
        domain = program.get("domain")
        if domain and domain not in domains:
            domains.append(domain)
    return domains


def retailer_source_counts() -> Dict[str, Any]:
    by_category: Dict[str, int] = {}
    for program in RETAILER_PROGRAMS:
        for category in program.get("categories") or []:
            if category == "all":
                continue
            by_category[category] = by_category.get(category, 0) + 1
    return {
        "retailer_programs": len(RETAILER_PROGRAMS),
        "retailer_categories": by_category,
        "retailer_domains": len({program["domain"] for program in RETAILER_PROGRAMS}),
        "retailer_task_types": len({task for program in RETAILER_PROGRAMS for task in program.get("tasks", [])}),
    }


def foundry_tool_plan(identifier: str, category: Optional[str], limit: int = 12) -> Dict[str, Any]:
    programs = retailer_programs_for_category(category, include_general=True)[:limit]
    encoded = urllib.parse.quote_plus(str(identifier or "").strip())
    return {
        "identifier": identifier,
        "category": category,
        "tools": [
            {
                "tool": "scrape_retailer_program",
                "retailer": program["name"],
                "domain": program["domain"],
                "tasks": program.get("tasks", []),
                "urls": [template.format(query=encoded) for template in program.get("templates", [])],
            }
            for program in programs
        ],
    }


def merge_unique_urls(*groups: Iterable[str]) -> List[str]:
    urls: List[str] = []
    for group in groups:
        for url in group:
            if url and url not in urls:
                urls.append(url)
    return urls
