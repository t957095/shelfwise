import json
import os
from typing import List, Dict, Any, Optional
from pathlib import Path

class ScraperRegistry:
    """Dynamic scraper registry loaded from JSON configuration."""

    def __init__(self, registry_path: str = None):
        if registry_path is None:
            registry_path = Path(__file__).parent / "scraper_registry.json"
        self.registry_path = registry_path
        self.sources = []
        self._load_registry()

    def _load_registry(self):
        """Load scraper definitions from JSON registry."""
        if not os.path.exists(self.registry_path):
            self._create_default_registry()
        try:
            with open(self.registry_path, 'r') as f:
                data = json.load(f)
                self.sources = data.get('sources', [])
        except Exception as e:
            print(f"Warning: Could not load registry: {e}")
            self.sources = []

    def _create_default_registry(self):
        """Create a default registry file with known sources."""
        default_sources = [
            {
                "name": "Open Food Facts",
                "type": "api",
                "weight": 0.90,
                "url_template": "https://world.openfoodfacts.org/api/v2/product/{upc}.json",
                "method": "GET",
                "timeout": 12,
                "extract": {
                    "name": ["product", "product_name"],
                    "brand": ["product", "brands"],
                    "category": ["product", "categories"],
                    "description": ["product", "generic_name"],
                    "image_urls": ["product", "image_url"]
                }
            },
            {
                "name": "UPCItemDB",
                "type": "api",
                "weight": 0.85,
                "url_template": "https://api.upcitemdb.com/prod/trial/lookup?upc={upc}",
                "method": "GET",
                "timeout": 12,
                "extract": {
                    "name": ["items", 0, "title"],
                    "brand": ["items", 0, "brand"],
                    "category": ["items", 0, "category"],
                    "description": ["items", 0, "description"],
                    "image_urls": ["items", 0, "images"]
                }
            }
        ]
        registry = {"version": "1.0", "sources": default_sources}
        with open(self.registry_path, 'w') as f:
            json.dump(registry, f, indent=2)
        self.sources = default_sources

    def get_all_sources(self) -> List[Dict[str, Any]]:
        """Return all registered scraper sources."""
        return self.sources

    def get_enabled_sources(self, max_sources: int = None) -> List[Dict[str, Any]]:
        """Return sources that are enabled and have working URLs."""
        enabled = [s for s in self.sources if not s.get('disabled', False)]
        if max_sources:
            enabled = enabled[:max_sources]
        return enabled

    def get_source_by_name(self, name: str) -> Optional[Dict[str, Any]]:
        """Find a source by its name."""
        for source in self.sources:
            if source.get('name') == name:
                return source
        return None

    def add_source(self, source_def: Dict[str, Any]) -> bool:
        """Add a new source to the registry."""
        if not self._validate_source(source_def):
            return False
        self.sources.append(source_def)
        self._save_registry()
        return True

    def remove_source(self, name: str) -> bool:
        """Remove a source by name."""
        original_len = len(self.sources)
        self.sources = [s for s in self.sources if s.get('name') != name]
        if len(self.sources) < original_len:
            self._save_registry()
            return True
        return False

    def _validate_source(self, source: Dict[str, Any]) -> bool:
        """Validate a source definition has required fields."""
        required = ['name', 'type', 'url_template']
        for field in required:
            if field not in source:
                return False
        return True

    def _save_registry(self):
        """Save current registry back to JSON file."""
        data = {"version": "1.0", "sources": self.sources}
        with open(self.registry_path, 'w') as f:
            json.dump(data, f, indent=2)

    def get_source_count(self) -> int:
        """Return total number of registered sources."""
        return len(self.sources)

    def get_source_stats(self) -> Dict[str, int]:
        """Return statistics about source types."""
        stats = {"total": len(self.sources), "api": 0, "html": 0, "search": 0}
        for source in self.sources:
            source_type = source.get('type', 'unknown')
            if source_type in stats:
                stats[source_type] += 1
        return stats
