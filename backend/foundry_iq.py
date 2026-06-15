"""
ShelfWise Foundry IQ Simulation Layer
Local implementation of Microsoft Foundry IQ knowledge retrieval patterns.
Provides agentic knowledge grounding, semantic search, ontology-based reasoning,
and cited answers — without consuming Azure credits during development.

When AZURE_FOUNDRY_ENDPOINT is set, this module proxies to the real service.
Otherwise, it runs a local knowledge graph + semantic retrieval engine.
"""

import hashlib
import json
import math
import os
import re
import sqlite3
from collections import defaultdict
from dataclasses import dataclass, field
from datetime import datetime
from typing import Any, Dict, List, Optional

# ---------------------------------------------------------------------------
# Data models
# ---------------------------------------------------------------------------

@dataclass
class KnowledgeNode:
    """A node in the product knowledge graph."""
    id: str
    entity_type: str  # product, brand, category, attribute, attribute_value
    label: str
    properties: Dict[str, Any] = field(default_factory=dict)
    sources: List[str] = field(default_factory=list)
    confidence: float = 1.0
    created_at: str = field(default_factory=lambda: datetime.utcnow().isoformat())

    def to_dict(self) -> Dict:
        return {
            "id": self.id,
            "entity_type": self.entity_type,
            "label": self.label,
            "properties": self.properties,
            "sources": self.sources,
            "confidence": self.confidence,
            "created_at": self.created_at,
        }


@dataclass
class KnowledgeEdge:
    """A relationship between two knowledge nodes."""
    source_id: str
    target_id: str
    relation: str
    properties: Dict[str, Any] = field(default_factory=dict)
    confidence: float = 1.0

    def to_dict(self) -> Dict:
        return {
            "source": self.source_id,
            "target": self.target_id,
            "relation": self.relation,
            "properties": self.properties,
            "confidence": self.confidence,
        }


@dataclass
class GroundedAnswer:
    """A Foundry IQ-style grounded answer with citations."""
    answer: str
    citations: List[Dict[str, Any]]
    confidence: float
    grounding_sources: List[str]
    query_id: str

    def to_dict(self) -> Dict:
        return {
            "answer": self.answer,
            "citations": self.citations,
            "confidence": self.confidence,
            "grounding_sources": self.grounding_sources,
            "query_id": self.query_id,
        }


# ---------------------------------------------------------------------------
# Local Knowledge Graph
# ---------------------------------------------------------------------------

class ProductKnowledgeGraph:
    """In-memory knowledge graph built from scraped product data.
    Simulates Foundry IQ's semantic layer for business concepts.
    """

    def __init__(self):
        self.nodes: Dict[str, KnowledgeNode] = {}
        self.edges: List[KnowledgeEdge] = []
        self.index: Dict[str, List[str]] = defaultdict(list)  # word -> node ids
        self._search_cache: Dict[str, Any] = {}

    def _make_id(self, entity_type: str, label: str) -> str:
        return f"{entity_type}:{hashlib.md5(label.lower().encode()).hexdigest()[:12]}"

    def _tokenize(self, text: str) -> List[str]:
        return re.findall(r"[a-zA-Z0-9]+", text.lower())

    def _index_node(self, node: KnowledgeNode):
        tokens = self._tokenize(node.label)
        for token in tokens:
            self.index[token].append(node.id)
        for key, val in node.properties.items():
            if isinstance(val, str):
                for token in self._tokenize(val):
                    self.index[token].append(node.id)

    def add_node(self, node: KnowledgeNode) -> KnowledgeNode:
        if node.id not in self.nodes:
            self.nodes[node.id] = node
            self._index_node(node)
        return node

    def add_edge(self, edge: KnowledgeEdge):
        self.edges.append(edge)

    def get_node(self, node_id: str) -> Optional[KnowledgeNode]:
        return self.nodes.get(node_id)

    def find_nodes(self, entity_type: Optional[str] = None, label_contains: Optional[str] = None) -> List[KnowledgeNode]:
        results = []
        for node in self.nodes.values():
            if entity_type and node.entity_type != entity_type:
                continue
            if label_contains and label_contains.lower() not in node.label.lower():
                continue
            results.append(node)
        return results

    def semantic_search(self, query: str, top_k: int = 10) -> List[Dict]:
        """Simple BM25-style ranked retrieval over knowledge nodes."""
        query_tokens = self._tokenize(query)
        if not query_tokens:
            return []

        scores: Dict[str, float] = defaultdict(float)
        for token in query_tokens:
            for node_id in self.index.get(token, []):
                node = self.nodes[node_id]
                # TF component: how many times token appears
                node_tokens = self._tokenize(node.label) + [
                    t for v in node.properties.values() if isinstance(v, str) for t in self._tokenize(v)
                ]
                tf = node_tokens.count(token)
                # IDF component: log(N / df)
                df = len(set(self.index.get(token, [])))
                idf = math.log((len(self.nodes) + 1) / (df + 1)) + 1
                scores[node_id] += tf * idf * node.confidence

        ranked = sorted(scores.items(), key=lambda x: x[1], reverse=True)[:top_k]
        return [
            {
                "node": self.nodes[node_id].to_dict(),
                "score": round(score, 4),
                "related_edges": [
                    e.to_dict() for e in self.edges
                    if e.source_id == node_id or e.target_id == node_id
                ][:5],
            }
            for node_id, score in ranked
        ]

    def get_related(self, node_id: str, relation: Optional[str] = None) -> List[Dict]:
        """Get related nodes (simulates graph traversal / ontology reasoning)."""
        related = []
        for edge in self.edges:
            if edge.source_id == node_id:
                if relation and edge.relation != relation:
                    continue
                target = self.nodes.get(edge.target_id)
                if target:
                    related.append({"edge": edge.to_dict(), "node": target.to_dict()})
            elif edge.target_id == node_id:
                if relation and edge.relation != relation:
                    continue
                source = self.nodes.get(edge.source_id)
                if source:
                    related.append({"edge": edge.to_dict(), "node": source.to_dict()})
        return related

    def build_from_product(self, product: Dict[str, Any]):
        """Ingest a product into the knowledge graph."""
        upc = product.get("upc", "")
        name = product.get("name", "")
        brand = product.get("brand", "")
        category = product.get("category", "")

        # Product node
        product_id = self._make_id("product", upc)
        product_node = KnowledgeNode(
            id=product_id,
            entity_type="product",
            label=name or f"Product {upc}",
            properties={
                "upc": upc,
                "description": product.get("description", ""),
                "confidence": product.get("confidence", 0),
                "status": product.get("status", ""),
                "image_url": product.get("image_url", ""),
            },
            sources=[c.get("source", "") for c in product.get("citations", [])],
            confidence=product.get("confidence", 1.0),
        )
        self.add_node(product_node)

        # Brand node
        if brand:
            brand_id = self._make_id("brand", brand)
            brand_node = KnowledgeNode(
                id=brand_id,
                entity_type="brand",
                label=brand,
                properties={"name": brand},
                confidence=product.get("confidence", 1.0),
            )
            self.add_node(brand_node)
            self.add_edge(KnowledgeEdge(
                source_id=product_id,
                target_id=brand_id,
                relation="manufactured_by",
                confidence=product.get("confidence", 1.0),
            ))

        # Category node
        if category:
            cat_id = self._make_id("category", category)
            cat_node = KnowledgeNode(
                id=cat_id,
                entity_type="category",
                label=category,
                properties={"name": category},
                confidence=product.get("confidence", 1.0),
            )
            self.add_node(cat_node)
            self.add_edge(KnowledgeEdge(
                source_id=product_id,
                target_id=cat_id,
                relation="belongs_to",
                confidence=product.get("confidence", 1.0),
            ))

        # Attribute nodes
        for attr_key, attr_val in product.get("attributes", {}).items():
            if isinstance(attr_val, str):
                attr_id = self._make_id("attribute", f"{attr_key}:{attr_val}")
                attr_node = KnowledgeNode(
                    id=attr_id,
                    entity_type="attribute",
                    label=f"{attr_key}: {attr_val}",
                    properties={"key": attr_key, "value": attr_val},
                    confidence=product.get("confidence", 1.0),
                )
                self.add_node(attr_node)
                self.add_edge(KnowledgeEdge(
                    source_id=product_id,
                    target_id=attr_id,
                    relation=f"has_{attr_key}",
                    confidence=product.get("confidence", 1.0),
                ))

    def to_dict(self) -> Dict:
        return {
            "nodes": [n.to_dict() for n in self.nodes.values()],
            "edges": [e.to_dict() for e in self.edges],
            "stats": {
                "total_nodes": len(self.nodes),
                "total_edges": len(self.edges),
                "entity_types": list(set(n.entity_type for n in self.nodes.values())),
            },
        }


# ---------------------------------------------------------------------------
# Foundry IQ Service
# ---------------------------------------------------------------------------

class FoundryIQService:
    """Local simulation of Microsoft Foundry IQ.
    Provides knowledge retrieval, grounding, and semantic reasoning.
    """

    def __init__(self, db_path: str = "shelfwise.db"):
        self.db_path = db_path
        self.knowledge_graph = ProductKnowledgeGraph()
        self._query_history: List[Dict] = []
        self._permissions: Dict[str, List[str]] = {
            "admin": ["read", "write", "delete", "query"],
            "user": ["read", "query"],
            "guest": ["query"],
        }
        self._is_real = bool(os.getenv("AZURE_FOUNDRY_ENDPOINT"))
        self._real_endpoint = os.getenv("AZURE_FOUNDRY_ENDPOINT", "")
        self._real_key = os.getenv("AZURE_FOUNDRY_KEY", "")

    @property
    def is_real_integration(self) -> bool:
        return self._is_real

    def _check_permission(self, role: str, action: str) -> bool:
        return action in self._permissions.get(role, [])

    def _generate_query_id(self, query: str) -> str:
        return hashlib.sha256(f"{query}:{datetime.utcnow().isoformat()}".encode()).hexdigest()[:16]

    def ingest_product_catalog(self):
        """Load all products from SQLite into the knowledge graph."""
        try:
            conn = sqlite3.connect(self.db_path)
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("SELECT upc, name, brand, category, confidence, status, foundry_enriched, foundry_sdk, data FROM products")
            rows = cursor.fetchall()
            for row in rows:
                row_dict = dict(row)
                # Product details live in the JSON `data` column
                try:
                    product = json.loads(row_dict.get("data", "{}"))
                except (json.JSONDecodeError, TypeError):
                    product = {}
                # Ensure core scalar fields from the row are present
                product.setdefault("upc", row_dict.get("upc"))
                product.setdefault("name", row_dict.get("name"))
                product.setdefault("brand", row_dict.get("brand"))
                product.setdefault("category", row_dict.get("category"))
                product.setdefault("confidence", row_dict.get("confidence"))
                product.setdefault("status", row_dict.get("status"))
                self.knowledge_graph.build_from_product(product)
            conn.close()
        except Exception as e:
            print(f"[FoundryIQ] Catalog ingestion warning: {e}")

    def query_knowledge(
        self,
        query: str,
        role: str = "user",
        top_k: int = 5,
        require_citations: bool = True,
    ) -> GroundedAnswer:
        """Execute a knowledge retrieval query with grounding.
        Simulates Foundry IQ's cited, permission-aware answer generation.
        """
        if not self._check_permission(role, "query"):
            return GroundedAnswer(
                answer="Access denied: insufficient permissions for knowledge query.",
                citations=[],
                confidence=0.0,
                grounding_sources=[],
                query_id=self._generate_query_id(query),
            )

        query_id = self._generate_query_id(query)

        # Semantic search over knowledge graph
        results = self.knowledge_graph.semantic_search(query, top_k=top_k * 2)

        # Deduplicate by source
        seen_sources = set()
        filtered_results = []
        for r in results:
            source_key = r["node"]["id"]
            if source_key not in seen_sources:
                seen_sources.add(source_key)
                filtered_results.append(r)
            if len(filtered_results) >= top_k:
                break

        # Build grounded answer
        if not filtered_results:
            answer = f"No knowledge found for query: '{query}'. The product catalog may not contain matching items."
            citations = []
            confidence = 0.0
            sources = []
        else:
            # Generate natural-language answer from top results
            parts = []
            citations = []
            sources = []
            total_confidence = 0.0

            for i, result in enumerate(filtered_results):
                node = result["node"]
                score = result["score"]
                total_confidence += min(score, 1.0)

                entity_type = node["entity_type"]
                label = node["label"]
                props = node.get("properties", {})

                if entity_type == "product":
                    desc = props.get("description", "")
                    upc = props.get("upc", "")
                    parts.append(f"{i+1}. {label} (UPC: {upc}): {desc[:120]}{'...' if len(desc) > 120 else ''}")
                elif entity_type == "brand":
                    parts.append(f"{i+1}. Brand: {label}")
                elif entity_type == "category":
                    parts.append(f"{i+1}. Category: {label}")
                else:
                    parts.append(f"{i+1}. {label}")

                citations.append({
                    "index": i + 1,
                    "source_id": node["id"],
                    "source_type": entity_type,
                    "label": label,
                    "retrieval_score": round(score, 4),
                    "confidence": node.get("confidence", 1.0),
                    "data_sources": node.get("sources", []),
                })
                sources.extend(node.get("sources", []))

            answer = f"Found {len(filtered_results)} relevant knowledge items for '{query}':\n\n" + "\n".join(parts)
            confidence = min(total_confidence / len(filtered_results), 1.0)

        result = GroundedAnswer(
            answer=answer,
            citations=citations,
            confidence=round(confidence, 3),
            grounding_sources=list(set(sources)),
            query_id=query_id,
        )

        self._query_history.append({
            "query": query,
            "query_id": query_id,
            "role": role,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result.to_dict(),
        })

        return result

    def reason_over_products(
        self,
        upc: str,
        question: str,
        role: str = "user",
    ) -> GroundedAnswer:
        """Ask a reasoning question about a specific product.
        Simulates multi-step reasoning with knowledge graph traversal.
        """
        if not self._check_permission(role, "query"):
            return GroundedAnswer(
                answer="Access denied.",
                citations=[],
                confidence=0.0,
                grounding_sources=[],
                query_id=self._generate_query_id(f"{upc}:{question}"),
            )

        # Find product node
        product_id = f"product:{hashlib.md5(upc.lower().encode()).hexdigest()[:12]}"
        product_node = self.knowledge_graph.get_node(product_id)

        if not product_node:
            # Try to load from DB on-demand
            self.ingest_product_catalog()
            product_node = self.knowledge_graph.get_node(product_id)

        if not product_node:
            return GroundedAnswer(
                answer=f"Product with UPC {upc} not found in knowledge base.",
                citations=[],
                confidence=0.0,
                grounding_sources=[],
                query_id=self._generate_query_id(f"{upc}:{question}"),
            )

        # Traverse related nodes for reasoning context
        related = self.knowledge_graph.get_related(product_id)
        context_parts = [f"Product: {product_node.label}"]
        for rel in related:
            edge_rel = rel["edge"]["relation"]
            node_label = rel["node"]["label"]
            context_parts.append(f"  - {edge_rel.replace('_', ' ')}: {node_label}")

        # Simple question-type reasoning
        q_lower = question.lower()
        answer_parts = []
        confidence = product_node.confidence

        if any(w in q_lower for w in ["brand", "who makes", "manufacturer", "company"]):
            brand_rels = [r for r in related if r["edge"]["relation"] == "manufactured_by"]
            if brand_rels:
                answer_parts.append(f"The manufacturer is {brand_rels[0]['node']['label']}.")
            else:
                answer_parts.append("Brand information is not available in the knowledge base.")
                confidence *= 0.5

        elif any(w in q_lower for w in ["category", "type of", "kind of"]):
            cat_rels = [r for r in related if r["edge"]["relation"] == "belongs_to"]
            if cat_rels:
                answer_parts.append(f"This product belongs to the {cat_rels[0]['node']['label']} category.")
            else:
                answer_parts.append("Category information is not available.")
                confidence *= 0.5

        elif any(w in q_lower for w in ["attribute", "size", "flavor", "color", "spec"]):
            attr_rels = [r for r in related if r["edge"]["relation"].startswith("has_")]
            if attr_rels:
                attrs = [f"{r['node']['properties'].get('key', '')}: {r['node']['properties'].get('value', '')}" for r in attr_rels]
                answer_parts.append(f"Product attributes: {', '.join(attrs)}.")
            else:
                answer_parts.append("No attributes found in the knowledge base.")
                confidence *= 0.5

        elif any(w in q_lower for w in ["describe", "what is", "tell me about"]):
            desc = product_node.properties.get("description", "")
            if desc:
                answer_parts.append(desc)
            else:
                answer_parts.append(f"{product_node.label}. No detailed description available.")
                confidence *= 0.7

        elif any(w in q_lower for w in ["related", "similar", "also by", "other"]):
            brand_rels = [r for r in related if r["edge"]["relation"] == "manufactured_by"]
            if brand_rels:
                brand_id = brand_rels[0]["node"]["id"]
                brand_products = self.knowledge_graph.get_related(brand_id, relation="manufactured_by")
                others = [p["node"]["label"] for p in brand_products if p["node"]["id"] != product_id][:5]
                if others:
                    answer_parts.append(f"Other products by this brand: {', '.join(others)}.")
                else:
                    answer_parts.append("No other products from this brand found.")
            else:
                answer_parts.append("Cannot determine related products without brand information.")
                confidence *= 0.5

        else:
            # Generic fallback with context
            answer_parts.append(f"Based on the product knowledge graph for {product_node.label}:")
            answer_parts.append("\n".join(context_parts))

        answer = " ".join(answer_parts) if answer_parts else "Unable to answer this question with available knowledge."
        query_id = self._generate_query_id(f"{upc}:{question}")

        citations = [{
            "index": 1,
            "source_id": product_node.id,
            "source_type": "product",
            "label": product_node.label,
            "retrieval_score": 1.0,
            "confidence": product_node.confidence,
            "data_sources": product_node.sources,
        }]

        result = GroundedAnswer(
            answer=answer,
            citations=citations,
            confidence=round(confidence, 3),
            grounding_sources=list(set(product_node.sources)),
            query_id=query_id,
        )

        self._query_history.append({
            "query": f"{upc}: {question}",
            "query_id": query_id,
            "role": role,
            "timestamp": datetime.utcnow().isoformat(),
            "result": result.to_dict(),
        })

        return result

    def get_ontology(self) -> Dict:
        """Return the current product ontology (simulates Foundry IQ semantic layer)."""
        entity_types = defaultdict(list)
        for node in self.knowledge_graph.nodes.values():
            entity_types[node.entity_type].append(node.label)

        relations = defaultdict(list)
        for edge in self.knowledge_graph.edges:
            relations[edge.relation].append({
                "from": self.knowledge_graph.nodes.get(edge.source_id, KnowledgeNode(id="", entity_type="", label="")).label,
                "to": self.knowledge_graph.nodes.get(edge.target_id, KnowledgeNode(id="", entity_type="", label="")).label,
            })

        return {
            "ontology_name": "ShelfWise Product Ontology",
            "version": "1.0.0",
            "entity_types": {k: list(set(v))[:20] for k, v in entity_types.items()},
            "relations": {k: v[:10] for k, v in relations.items()},
            "stats": self.knowledge_graph.to_dict()["stats"],
        }

    def get_query_history(self, limit: int = 50) -> List[Dict]:
        return self._query_history[-limit:]

    def health(self) -> Dict:
        return {
            "status": "healthy",
            "mode": "azure" if self._is_real else "local_simulation",
            "knowledge_graph": self.knowledge_graph.to_dict()["stats"],
            "permissions_loaded": len(self._permissions),
            "total_queries_served": len(self._query_history),
        }


# Singleton instance
_foundry_iq_service: Optional[FoundryIQService] = None

def get_foundry_iq_service(db_path: str = "shelfwise.db") -> FoundryIQService:
    global _foundry_iq_service
    if _foundry_iq_service is None:
        _foundry_iq_service = FoundryIQService(db_path=db_path)
        _foundry_iq_service.ingest_product_catalog()
    return _foundry_iq_service
