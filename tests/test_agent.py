import pytest
import pytest_asyncio

from backend.foundry_agent import ProductReasoningAgent, _jaccard_similarity
from backend.models import ConsolidatedProduct


@pytest_asyncio.fixture
async def agent():
    return ProductReasoningAgent()


def test_jaccard_similarity_identical():
    """Test Jaccard similarity for identical strings."""
    assert _jaccard_similarity("Coca Cola", "Coca Cola") == 1.0


def test_jaccard_similarity_different():
    """Test Jaccard similarity for completely different strings."""
    assert _jaccard_similarity("Coca Cola", "Pepsi") < 0.3


@pytest.mark.asyncio
async def test_consolidate_single_source(agent):
    """Test consolidation with a single high-confidence source."""
    raw = [
        {
            "upc": "123456789012",
            "source": "Open Food Facts",
            "name": "Coca-Cola Classic",
            "brand": "Coca-Cola",
            "category": "Beverages",
            "description": "Classic cola",
            "image_urls": ["https://example.com/coke.jpg"],
            "success": True,
        }
    ]

    result_dict = await agent.consolidate("123456789012", raw)
    result = ConsolidatedProduct(**result_dict)

    assert result.name == "Coca-Cola Classic"
    assert result.brand == "Coca-Cola"
    assert result.confidence >= 0.5
    assert len(result.citations) >= 1


@pytest.mark.asyncio
async def test_consolidate_multiple_sources_agreement(agent):
    """Test consolidation when multiple sources agree."""
    raw = [
        {
            "upc": "123456789012",
            "source": "Open Food Facts",
            "name": "Coca-Cola Classic 12oz",
            "brand": "Coca-Cola",
            "category": "Beverages",
            "description": "Classic cola",
            "image_urls": ["https://off.com/coke.jpg"],
            "success": True,
        },
        {
            "upc": "123456789012",
            "source": "UPCItemDB",
            "name": "Coca-Cola Classic",
            "brand": "Coca-Cola",
            "category": "Soft Drinks",
            "description": "Classic cola drink",
            "image_urls": ["https://upc.com/coke.jpg"],
            "success": True,
        },
    ]

    result_dict = await agent.consolidate("123456789012", raw)
    result = ConsolidatedProduct(**result_dict)

    assert result.brand == "Coca-Cola"
    assert result.confidence >= 0.7
    assert len(result.citations) >= 2


@pytest.mark.asyncio
async def test_consolidate_conflicting_sources(agent):
    """Test consolidation when sources conflict on brand."""
    raw = [
        {
            "upc": "123456789012",
            "source": "Open Food Facts",
            "name": "Product A",
            "brand": "BrandA",
            "category": "Food",
            "success": True,
        },
        {
            "upc": "123456789012",
            "source": "UPCItemDB",
            "name": "Product A",
            "brand": "BrandB",
            "category": "Groceries",
            "success": True,
        },
    ]

    result_dict = await agent.consolidate("123456789012", raw)
    result = ConsolidatedProduct(**result_dict)

    assert result.brand in ["BrandA", "BrandB"]
    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_consolidate_no_data(agent):
    """Test consolidation with no successful sources."""
    raw = [
        {
            "upc": "123456789012",
            "source": "Open Food Facts",
            "success": False,
            "error": "Not found",
        },
    ]

    result_dict = await agent.consolidate("123456789012", raw)
    result = ConsolidatedProduct(**result_dict)

    assert "Unknown Product" in result.name or result.name == ""
    assert result.confidence == 0.0


@pytest.mark.asyncio
async def test_confidence_scoring(agent):
    """Test that confidence is properly bounded [0, 1]."""
    raw = [
        {
            "upc": "123456789012",
            "source": "Open Food Facts",
            "name": "Test",
            "brand": "TestBrand",
            "category": "TestCat",
            "description": "Test description",
            "image_urls": ["https://test.com/img.jpg"],
            "success": True,
        },
    ]

    result_dict = await agent.consolidate("123456789012", raw)
    result = ConsolidatedProduct(**result_dict)

    assert 0.0 <= result.confidence <= 1.0


@pytest.mark.asyncio
async def test_reasoning_trace_generation(agent):
    """Test that reasoning trace is populated."""
    raw = [
        {
            "upc": "123456789012",
            "source": "Open Food Facts",
            "name": "Test Product",
            "brand": "TestBrand",
            "success": True,
        },
    ]

    result_dict = await agent.consolidate("123456789012", raw)
    result = ConsolidatedProduct(**result_dict)

    assert len(result.reasoning_trace) > 0
