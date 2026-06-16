from typing import Any, Dict, List, Optional

from pydantic import BaseModel, Field


class RawProductData(BaseModel):
    upc: str
    source: str
    source_url: Optional[str] = None
    name: Optional[str] = None
    brand: Optional[str] = None
    category: Optional[str] = None
    description: Optional[str] = None
    image_urls: List[str] = []
    attributes: Dict[str, Any] = {}
    raw: Dict[str, Any] = {}
    success: bool = True
    error: Optional[str] = None


class ProductImage(BaseModel):
    url: str
    source: str
    source_url: Optional[str] = None
    score: float = 0.0
    verified: bool = False
    generated: bool = False
    needs_review: bool = False
    query: Optional[str] = None
    width: Optional[int] = None
    height: Optional[int] = None


class Citation(BaseModel):
    source: str
    source_url: Optional[str] = None
    fields: List[str] = []
    confidence: float = 0.0
    note: Optional[str] = None


class ConsolidatedProduct(BaseModel):
    upc: str
    name: str
    brand: Optional[str] = None
    category: Optional[str] = None
    description: str = ""
    image_url: Optional[str] = None
    images: List[ProductImage] = []
    attributes: Dict[str, Any] = {}
    confidence: float = 0.0
    status: str = "partial"
    citations: List[Citation] = []
    reasoning_trace: List[str] = []
    foundry_enriched: bool = False
    foundry_sdk: Optional[str] = None


class UPCBatchRequest(BaseModel):
    upcs: List[str]
    auto_scrape: bool = True


class ExportRequest(BaseModel):
    format: str
    status: Optional[str] = None
    min_confidence: Optional[float] = Field(None, ge=0.0, le=1.0)
    q: Optional[str] = None
    preview: bool = False
    preview_limit: int = Field(5, ge=1, le=50)


class JobStatus(BaseModel):
    job_id: str
    total: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    created_at: str = ""
    updated_at: str = ""
