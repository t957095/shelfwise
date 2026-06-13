import pytest
from backend.models import RawProductData, ConsolidatedProduct
from backend.foundry_agent import ProductReasoningAgent


@pytest.fixture
def agent():
    return ProductReasoningAgent()


def test_jaccard_similarity_identical(agent):
    """Test Jaccard similarity for identical strings."""
    assert agent._jaccard_similarity("Coca Cola", "Coca Cola") == 1.0


def test_jaccard_similarity_different(agent):
    """Test Jaccard similarity for completely different strings."""
    assert agent._jaccard_similarity("Coca Cola", "Pepsi") < 0.3


def test_consolidate_single_source(agent):
    """Test consolidation with a single high-confidence source."""
    raw = [
        RawProductData(
            upc="123456789012",
            source="OpenFoodFacts",
            name="Coca-Cola Classic",
            brand="Coca-Cola",
            category="Beverages",
            description="Classic cola",
            image_urls=["https://example.com/coke.jpg"],
            success=True,
        )
    ]

    result = agent.consolidate("123456789012", raw)

    assert isinstance(result, ConsolidatedProduct)
    assert result.name == "Coca-Cola Classic"
    assert result.brand == "Coca-Cola"
    assert result.confidence >= 0.5
    assert len(result.citations) == 1
    assert result.citations[0].source == "OpenFoodFacts"


def test_consolidate_multiple_sources_agreement(agent):
    """Test consolidation when multiple sources agree."""
    raw = [
        RawProductData(
            upc="123456789012",
            source="OpenFoodFacts",
            name="Coca-Cola Classic 12oz",
            brand="Coca-Cola",
            category="Beverages",
            description="Classic cola",
            image_urls=["https://off.com/coke.jpg"],
            success=True,
        ),
        RawProductData(
            upc="123456789012",
            source="UPCItemDB",
            name="Coca-Cola Classic",
            brand="Coca-Cola",
            category="Soft Drinks",
            description="Classic cola drink",
            image_urls=["https://upc.com/coke.jpg"],
            success=True,
        ),
    ]

    result = agent.consolidate("123456789012", raw)

    assert result.brand == "Coca-Cola"
    assert result.confidence >= 0.7  # High confidence due to agreement
    assert len(result.citations) == 2


def test_consolidate_conflicting_sources(agent):
    """Test consolidation when sources conflict on brand."""
    raw = [
        RawProductData(
            upc="123456789012",
            source="OpenFoodFacts",
            name="Product A",
            brand="BrandA",
            category="Food",
            success=True,
        ),
        RawProductData(
            upc="123456789012",
            source="UPCItemDB",
            name="Product A",
            brand="BrandB",
            category="Groceries",
            success=True,
        ),
    ]

    result = agent.consolidate("123456789012", raw)

    # Should pick the higher-weighted source's brand
    assert result.brand in ["BrandA", "BrandB"]
    # Confidence should be lower due to conflict
    assert result.confidence < 0.8


def test_consolidate_no_data(agent):
    """Test consolidation with no successful sources."""
    raw = [
        RawProductData(
            upc="123456789012",
            source="OpenFoodFacts",
            success=False,
            error="Not found",
        ),
    ]

    result = agent.consolidate("123456789012", raw)

    assert result.name == "Unknown Product (UPC: 123456789012)"
    assert result.confidence == 0.0
    assert result.status == "insufficient_data"


def test_confidence_scoring(agent):
    """Test that confidence is properly bounded [0, 1]."""
    raw = [
        RawProductData(
            upc="123456789012",
            source="OpenFoodFacts",
            name="Test",
            brand="TestBrand",
            category="TestCat",
            description="Test description",
            image_urls=["https://test.com/img.jpg"],
            success=True,
        ),
    ]

    result = agent.consolidate("123456789012", raw)

    assert 0.0 <= result.confidence <= 1.0
    assert result.status in ["complete", "partial", "insufficient_data", "error"]


def test_reasoning_trace_generation(agent):
    """Test that reasoning trace is populated."""
    raw = [
        RawProductData(
            upc="123456789012",
            source="OpenFoodFacts",
            name="Test Product",
            brand="TestBrand",
            success=True,
        ),
    ]

    result = agent.consolidate("123456789012", raw)

    assert len(result.reasoning_trace) > 0
    assert any("source" in step.lower() for step in result.reasoning_trace)
