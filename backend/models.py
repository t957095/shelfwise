from typing import Optional, List, Dict, Any
from pydantic import BaseModel


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
    score: float = 0.0


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


class JobStatus(BaseModel):
    job_id: str
    total: int = 0
    queued: int = 0
    running: int = 0
    completed: int = 0
    failed: int = 0
    created_at: str = ""
    updated_at: str = ""
