"""Foundry tool definitions for ShelfWise product enrichment.

These definitions mirror Microsoft Foundry function-tool semantics: the model
can ask for a named function with JSON arguments, the application executes it,
and the result is returned as grounded context. The local reasoning path also
uses the same functions so behavior stays consistent without Azure credentials.
"""

from __future__ import annotations

from typing import Any, Dict, List, Optional

from backend.retailer_flows import foundry_tool_plan, retailer_domains, retailer_listing_urls


FOUNDRY_PRODUCT_TOOL_DEFINITIONS: List[Dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "plan_retailer_workflow",
            "description": "Build a category-aware retailer scraping workflow for a UPC or POS identifier.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string", "description": "UPC, SKU, or POS identifier."},
                    "category": {"type": "string", "description": "Optional POS category or department."},
                },
                "required": ["identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "direct_retailer_probe_urls",
            "description": "Return direct retailer/search URLs that should be scraped for product evidence.",
            "parameters": {
                "type": "object",
                "properties": {
                    "identifier": {"type": "string"},
                    "category": {"type": "string"},
                },
                "required": ["identifier"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "category_search_domains",
            "description": "Return retailer domains that should be used for site-scoped image and listing search.",
            "parameters": {
                "type": "object",
                "properties": {"category": {"type": "string"}},
                "required": [],
            },
        },
    },
]


def execute_foundry_product_tool(name: str, arguments: Optional[Dict[str, Any]] = None) -> Dict[str, Any]:
    args = arguments or {}
    identifier = str(args.get("identifier") or args.get("upc") or "").strip()
    category = args.get("category")

    if name == "plan_retailer_workflow":
        return foundry_tool_plan(identifier, category)
    if name == "direct_retailer_probe_urls":
        return {
            "identifier": identifier,
            "category": category,
            "urls": retailer_listing_urls(identifier, category=category, include_general=True),
        }
    if name == "category_search_domains":
        return {"category": category, "domains": retailer_domains(category=category, include_general=True)}
    return {"error": f"Unknown ShelfWise Foundry tool: {name}"}


def build_foundry_tool_context(identifier: str, category: Optional[str]) -> Dict[str, Any]:
    """Pre-execute the deterministic tools for non-tool-capable clients."""
    return {
        "tool_definitions": FOUNDRY_PRODUCT_TOOL_DEFINITIONS,
        "tool_outputs": [
            execute_foundry_product_tool("plan_retailer_workflow", {"identifier": identifier, "category": category}),
            execute_foundry_product_tool("direct_retailer_probe_urls", {"identifier": identifier, "category": category}),
            execute_foundry_product_tool("category_search_domains", {"category": category}),
        ],
    }
