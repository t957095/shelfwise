import io

from fastapi.testclient import TestClient
from PIL import Image

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


def _seed_single_product():
    delete_all_products()
    upsert_product(
        ConsolidatedProduct(
            upc="333333333333",
            name="Gamma Product",
            brand="GammaBrand",
            category="Beverages",
            description="Gamma desc",
            confidence=0.95,
            status="complete",
        )
    )


def _make_image_bytes() -> bytes:
    img = Image.new("RGB", (100, 100), color="red")
    buf = io.BytesIO()
    img.save(buf, format="PNG")
    return buf.getvalue()


def test_upload_product_image():
    """Test uploading an image for a product."""
    _seed_single_product()
    response = client.post(
        "/api/products/333333333333/images",
        files={"file": ("test.png", io.BytesIO(_make_image_bytes()), "image/png")},
    )
    assert response.status_code == 200
    data = response.json()
    assert data["upc"] == "333333333333"
    assert data["image_url"].startswith("/uploads/")
    assert len(data["images"]) == 1


def test_upload_product_image_invalid_type():
    """Test uploading a non-image file is rejected."""
    _seed_single_product()
    response = client.post(
        "/api/products/333333333333/images",
        files={"file": ("test.txt", io.BytesIO(b"not an image"), "text/plain")},
    )
    assert response.status_code == 400


def test_delete_product_image():
    """Test deleting an uploaded product image."""
    _seed_single_product()
    upload_response = client.post(
        "/api/products/333333333333/images",
        files={"file": ("test.png", io.BytesIO(_make_image_bytes()), "image/png")},
    )
    image_url = upload_response.json()["image_url"]

    delete_response = client.delete(
        "/api/products/333333333333/images",
        params={"url": image_url},
    )
    assert delete_response.status_code == 200
    data = delete_response.json()
    assert len(data["images"]) == 0
    assert data["image_url"] is None
