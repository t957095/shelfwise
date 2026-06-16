from backend.foundry_tools import build_foundry_tool_context, execute_foundry_product_tool
from backend.retailer_flows import retailer_domains, retailer_listing_urls, retailer_source_counts


def test_pet_care_flow_prefers_specialty_retailers():
    urls = retailer_listing_urls("017800111719", category="Pet Care", include_general=False)
    domains = retailer_domains("pet supplies", include_general=False)

    assert any("chewy.com" in url for url in urls)
    assert any("petco.com" in url for url in urls)
    assert "chewy.com" in domains
    assert "petco.com" in domains


def test_foundry_tool_context_contains_callable_workflow():
    context = build_foundry_tool_context("017800111719", "Pet Care")
    tool_names = {tool["function"]["name"] for tool in context["tool_definitions"]}

    assert "plan_retailer_workflow" in tool_names
    assert "direct_retailer_probe_urls" in tool_names
    assert context["tool_outputs"][0]["tools"]


def test_foundry_direct_probe_tool_executes_locally():
    result = execute_foundry_product_tool(
        "direct_retailer_probe_urls",
        {"identifier": "017800111719", "category": "Pet Care"},
    )

    assert result["urls"]
    assert any("chewy.com" in url for url in result["urls"])


def test_retailer_source_counts_include_programs_and_tasks():
    counts = retailer_source_counts()

    assert counts["retailer_programs"] >= 15
    assert counts["retailer_domains"] >= 15
    assert counts["retailer_task_types"] >= 4
