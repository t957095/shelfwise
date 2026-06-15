from fastapi.testclient import TestClient

from backend.database import delete_all_products, upsert_product
from backend.main import app
from backend.models import ConsolidatedProduct

client = TestClient(app)


def test_read_root():
    """Test root endpoint returns app info."""
    response = client.get("/")
    assert response.status_code == 200
    data = response.json()
    assert "name" in data
    assert data["name"] == "ShelfWise"
    assert "version" in data
    assert "endpoints" in data


def test_health_check():
    """Test health endpoint."""
    response = client.get("/api/health")
    assert response.status_code == 200
    data = response.json()
    assert data["status"] == "healthy"
    assert "features" in data
    assert "scrapers" in data


def test_get_products_empty():
    """Test getting products when database is empty."""
    delete_all_products()
    response = client.get("/api/products")
    assert response.status_code == 200
    data = response.json()
    assert data["count"] == 0
    assert data["products"] == []


def test_get_product_not_found():
    """Test getting a product that doesn't exist."""
    response = client.get("/api/products/999999999999")
    assert response.status_code == 404


def test_get_stats_empty():
    """Test stats endpoint when database is empty."""
    delete_all_products()
    response = client.get("/api/stats")
    assert response.status_code == 200
    data = response.json()
    assert data["total_products"] == 0
    assert data["avg_confidence"] == 0.0


def test_export_csv_empty():
    """Test CSV export with no products."""
    delete_all_products()
    response = client.post("/api/export", json={"format": "csv"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("text/csv")


def test_export_json_empty():
    """Test JSON export with no products."""
    delete_all_products()
    response = client.post("/api/export", json={"format": "json"})
    assert response.status_code == 200
    assert response.headers["content-type"].startswith("application/json")
    data = response.json()
    assert data == []


def test_export_invalid_format():
    """Test export with invalid format."""
    response = client.post("/api/export", json={"format": "xml"})
    assert response.status_code == 400


def test_batch_submission_validation():
    """Test batch submission with empty UPC list."""
    response = client.post("/api/batch", json={"upcs": [], "auto_scrape": True})
    assert response.status_code == 400


def test_batch_submission():
    """Test batch submission with valid UPCs."""
    response = client.post(
        "/api/batch",
        json={"upcs": ["049000050103"], "auto_scrape": False},
    )
    assert response.status_code == 200
    data = response.json()
    assert "job_id" in data
    assert data["total"] == 1
    assert "message" in data


def test_job_status_not_found():
    """Test getting status for non-existent job."""
    response = client.get("/api/jobs/nonexistent")
    assert response.status_code == 404


def test_static_files():
    """Test that frontend files are served."""
    response = client.get("/app")
    assert response.status_code == 200
    assert "ShelfWise" in response.text


def test_app_js_served():
    """Test that app.js is accessible."""
    response = client.get("/app/app.js")
    assert response.status_code == 200


def test_styles_css_served():
    """Test that styles.css is accessible."""
    response = client.get("/app/styles.css")
    assert response.status_code == 200


def _seed_products():
    delete_all_products()
    products = [
        ConsolidatedProduct(
            upc="111111111111",
            name="Alpha Product",
            brand="AlphaBrand",
            category="Beverages",
            description="Alpha desc",
            confidence=0.95,
            status="complete",
        ),
        ConsolidatedProduct(
            upc="222222222222",
            name="Beta Product",
            brand="BetaBrand",
            category="Snacks",
            description="Beta desc",
            confidence=0.45,
            status="partial",
        ),
    ]
    for p in products:
        upsert_product(p)


def test_export_preview_filters():
    """Test export preview with status and confidence filters."""
    _seed_products()
    response = client.post(
        "/api/export",
        json={"format": "json", "preview": True, "preview_limit": 10, "status": "complete"},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["preview"] is True
    assert data["total"] == 1
    assert data["products"][0]["upc"] == "111111111111"


def test_export_preview_min_confidence():
    """Test export preview filtered by min_confidence."""
    _seed_products()
    response = client.post(
        "/api/export",
        json={"format": "json", "preview": True, "min_confidence": 0.5},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["total"] == 1
    assert data["products"][0]["upc"] == "111111111111"


def test_export_csv_filtered():
    """Test CSV export respects filters."""
    _seed_products()
    response = client.post("/api/export", json={"format": "csv", "status": "complete"})
    assert response.status_code == 200
    text = response.text
    assert "Alpha Product" in text
    assert "Beta Product" not in text
