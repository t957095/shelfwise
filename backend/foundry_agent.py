"""Foundry Agent - Product Reasoning Engine for ShelfWise.

Microsoft Azure AI Foundry SDK integration with tiered fallback:
  1. Azure AI Inference SDK (azure-ai-inference) — primary for hackathon
  2. Azure AI Projects Agent SDK (azure-ai-projects) — agent orchestration
  3. Ollama local LLM — OpenAI-compatible fallback
  4. Local deterministic simulation — final fallback
"""

import asyncio
import hashlib
import json
import logging
import os
import re
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple

# Ensure .env is loaded before reading env vars
try:
    from dotenv import load_dotenv

    _env_path = Path(__file__).resolve().parent.parent / ".env"
    if _env_path.exists():
        load_dotenv(_env_path)
except Exception:
    pass

# Optional Foundry IQ knowledge graph fallback
try:
    _FOUNDRY_IQ_AVAILABLE = True
except Exception:
    _FOUNDRY_IQ_AVAILABLE = False

# ---------------------------------------------------------------------------
# Microsoft Azure AI Foundry SDK imports (graceful degradation if missing)
# ---------------------------------------------------------------------------
try:
    from azure.ai.inference import ChatCompletionsClient
    from azure.ai.inference.models import SystemMessage, UserMessage
    from azure.core.credentials import AzureKeyCredential

    _AZURE_INFERENCE_AVAILABLE = True
except Exception:
    _AZURE_INFERENCE_AVAILABLE = False

try:
    from azure.ai.projects import AIProjectClient
    from azure.identity import DefaultAzureCredential

    _AZURE_PROJECTS_AVAILABLE = True
except Exception:
    _AZURE_PROJECTS_AVAILABLE = False

# OpenAI SDK for Ollama / GitHub Models compatible endpoints
try:
    from openai import AsyncOpenAI

    _OPENAI_AVAILABLE = True
except Exception:
    _OPENAI_AVAILABLE = False

from backend.image_verifier import select_verified_images

SOURCE_WEIGHTS = {
    "Open Food Facts": 0.90,
    "UPCItemDB": 0.85,
    "BarcodeLookup": 0.75,
    "Go-UPC": 0.70,
    "Buycott": 0.65,
    "EANdata": 0.60,
    "Lookify": 0.55,
    "UPCDatabase": 0.50,
    "Brave Search": 0.45,
    "Google Search": 0.40,
    "Demo Fallback": 0.40,
}

STOPWORDS = {"the", "a", "an", "and", "or", "of", "in", "on", "at", "to", "for", "with", "by"}


def _canonicalize(text: str) -> str:
    if not text:
        return ""
    cleaned = re.sub(r"[^\w\s]", " ", text.lower())
    words = [w for w in cleaned.split() if w not in STOPWORDS and len(w) > 1]
    return " ".join(sorted(words))


def _jaccard_similarity(a: str, b: str) -> float:
    set_a = set(a.lower().split())
    set_b = set(b.lower().split())
    if not set_a and not set_b:
        return 1.0
    intersection = set_a & set_b
    union = set_a | set_b
    return len(intersection) / len(union) if union else 0.0


class ProductReasoningAgent:
    """AI reasoning agent that consolidates raw product data from multiple sources."""

    def __init__(self, foundry_iq_service: Optional[Any] = None):
        self._azure_client: Optional[Any] = None
        self._openai_client: Optional[Any] = None
        self._azure_projects_client: Optional[Any] = None
        self._foundry_iq_service: Optional[Any] = foundry_iq_service
        self._init_clients()

    def _init_clients(self):
        """Initialize Microsoft Foundry SDK clients from environment.

        Supports both FOUNDRY_ENDPOINT/FOUNDRY_API_KEY and the Azure-native
        AZURE_FOUNDRY_ENDPOINT/AZURE_FOUNDRY_KEY variable names.
        """
        endpoint = os.environ.get("FOUNDRY_ENDPOINT", "") or os.environ.get("AZURE_FOUNDRY_ENDPOINT", "")
        api_key = os.environ.get("FOUNDRY_API_KEY", "") or os.environ.get("AZURE_FOUNDRY_KEY", "")
        conn_str = os.environ.get("AZURE_FOUNDRY_CONNECTION_STRING", "")

        # --- Tier 1: Azure AI Inference SDK ---
        # Primary: Azure AI Inference endpoints (GitHub Models, Azure OpenAI, etc.)
        if (
            _AZURE_INFERENCE_AVAILABLE
            and endpoint
            and api_key
            and ("azure.com" in endpoint or "inference.ai" in endpoint)
        ):
            try:
                model = os.environ.get("FOUNDRY_MODEL", "gpt-4o")
                self._azure_client = ChatCompletionsClient(
                    endpoint=endpoint.rstrip("/") + "/openai/deployments/" + model,
                    credential=AzureKeyCredential(api_key),
                )
            except Exception as e:
                logger = logging.getLogger("shelfwise")
                logger.warning("Azure AI Inference client init failed: %s", e)
                self._azure_client = None

        # --- Tier 1b: Azure AI Projects (Agent SDK) ---
        if _AZURE_PROJECTS_AVAILABLE and conn_str:
            try:
                self._azure_projects_client = AIProjectClient.from_connection_string(
                    credential=DefaultAzureCredential(),
                    conn_str=conn_str,
                )
            except Exception as e:
                logger = logging.getLogger("shelfwise")
                logger.warning("Azure AI Projects client init failed: %s", e)
                self._azure_projects_client = None

        # --- Tier 2: OpenAI-compatible (Ollama / GitHub Models) ---
        if _OPENAI_AVAILABLE and endpoint and api_key:
            try:
                self._openai_client = AsyncOpenAI(
                    base_url=endpoint,
                    api_key=api_key,
                )
            except Exception as e:
                logger = logging.getLogger("shelfwise")
                logger.warning("OpenAI-compatible client init failed: %s", e)
                self._openai_client = None

    # -----------------------------------------------------------------------
    # Main consolidate flow
    # -----------------------------------------------------------------------
    async def consolidate(self, upc: str, raw_data_list: List[Dict[str, Any]]) -> Dict[str, Any]:
        trace = [f"Starting consolidation for UPC {upc}"]

        if not raw_data_list:
            trace.append("No scraper data found — will attempt Foundry LLM enrichment from UPC alone")
            raw_data_list = []

        # Step 1: Weight and filter sources
        weighted = self._weight_sources(raw_data_list)
        trace.append(f"Weighted {len(weighted)} sources: " + ", ".join(f"{s['source']}({w:.2f})" for s, w in weighted))

        # Step 2: Resolve fields
        name, name_sources = self._resolve_name(weighted)
        trace.append(f"Resolved name: '{name}' from {name_sources}")

        brand, brand_sources = self._resolve_brand(weighted)
        trace.append(f"Resolved brand: '{brand}' from {brand_sources}")

        category, category_sources = self._resolve_category(weighted)
        trace.append(f"Resolved category: '{category}' from {category_sources}")

        # Step 3: Merge attributes
        attributes = self._merge_attributes(weighted)
        trace.append(f"Merged {len(attributes)} attributes from all sources")

        # Step 4: Build description
        fields = {"name": name, "brand": brand, "category": category, "attributes": attributes, "upc": upc}
        description = self._build_description(fields, weighted)
        trace.append(f"Generated description ({len(description)} chars)")

        # Step 5: Select images
        images, best_image_url = await self._select_images(upc, weighted, name, brand)
        trace.append(f"Selected {len(images)} images, best: {best_image_url is not None}")

        # Step 6: Compute confidence
        resolved_count = sum(1 for x in [name, brand, category] if x)
        confidence = self._compute_confidence(weighted, resolved_count, name_sources)
        trace.append(f"Computed confidence: {confidence:.2f}")

        # Step 7: Generate citations
        citations = self._foundry_iq_ground(
            {
                "name": name,
                "brand": brand,
                "category": category,
                "description": description,
                "images": images,
                "attributes": attributes,
            },
            weighted,
        )
        trace.append(f"Generated {len(citations)} citations")

        # Step 8: Determine status
        if confidence >= 0.7:
            status = "complete"
        elif confidence > 0.0:
            status = "partial"
        else:
            status = "error"
        trace.append(f"Status: {status}")

        # Step 9: Microsoft Foundry LLM enrichment (never blocks)
        foundry_result = await self._foundry_reasoning_call(upc, raw_data_list, name, brand, category, description)
        if foundry_result and foundry_result.get("data"):
            trace.append("Microsoft Foundry reasoning applied")
            llm_data = foundry_result["data"]
            if isinstance(llm_data, dict):
                if llm_data.get("name"):
                    name = llm_data["name"]
                if llm_data.get("brand"):
                    brand = llm_data["brand"]
                if llm_data.get("category"):
                    category = llm_data["category"]
                if llm_data.get("description"):
                    description = llm_data["description"]
                if llm_data.get("attributes") and isinstance(llm_data["attributes"], dict):
                    attributes.update(llm_data["attributes"])
                # If Foundry returns meaningful data, boost confidence and status
                if name and brand and category:
                    confidence = min(1.0, confidence + 0.25)
                    if status == "error":
                        status = "complete"
                        trace.append("Status promoted from error to complete by Foundry LLM")
                    trace.append("Foundry enriched fields merged — full product data from LLM")
                else:
                    confidence = min(1.0, confidence + 0.15)
                    trace.append("Foundry enriched fields merged")

        return {
            "upc": upc,
            "name": name,
            "brand": brand,
            "category": category,
            "description": description,
            "image_url": best_image_url,
            "images": images,
            "attributes": attributes,
            "confidence": round(confidence, 3),
            "status": status,
            "citations": citations,
            "reasoning_trace": trace,
            "foundry_enriched": bool(foundry_result and foundry_result.get("data")),
            "foundry_sdk": (foundry_result.get("sdk") if foundry_result else None),
        }

    # -----------------------------------------------------------------------
    # Microsoft Foundry SDK Integration
    # -----------------------------------------------------------------------
    async def _foundry_reasoning_call(
        self,
        upc: str,
        raw_data_list: List[Dict[str, Any]],
        current_name: str,
        current_brand: Optional[str],
        current_category: Optional[str],
        current_description: str,
    ) -> Optional[Dict[str, Any]]:
        """
        Tiered Microsoft Foundry integration:
          1. Azure AI Inference SDK (azure-ai-inference)
          2. Azure AI Projects Agent SDK (azure-ai-projects)
          3. OpenAI-compatible client (Ollama / GitHub Models)
          4. Local simulation fallback
        """
        model = os.environ.get("FOUNDRY_MODEL", "gpt-4o-mini")

        # Build structured prompt
        prompt = self._build_llm_prompt(
            upc, raw_data_list, current_name, current_brand, current_category, current_description
        )

        # --- Tier 1: Azure AI Inference SDK ---
        if self._azure_client and _AZURE_INFERENCE_AVAILABLE:
            try:
                result = await self._azure_inference_complete(prompt, model)
                if result:
                    return {"data": result, "sdk": "azure-ai-inference"}
            except Exception:
                pass

        # --- Tier 2: Azure AI Projects Agent SDK ---
        if self._azure_projects_client and _AZURE_PROJECTS_AVAILABLE:
            try:
                result = await self._azure_projects_complete(prompt, model)
                if result:
                    return {"data": result, "sdk": "azure-ai-projects"}
            except Exception:
                pass

        # --- Tier 3: OpenAI-compatible (Ollama / GitHub Models) ---
        if self._openai_client and _OPENAI_AVAILABLE:
            try:
                result = await self._openai_compatible_complete(prompt, model)
                if result:
                    return {"data": result, "sdk": "openai-compatible"}
            except Exception:
                pass

        # --- Tier 4: Foundry IQ knowledge graph fallback ---
        if self._foundry_iq_service and _FOUNDRY_IQ_AVAILABLE:
            try:
                result = await self._foundry_iq_fallback(upc, current_name, current_brand, current_category)
                if result:
                    return {"data": result, "sdk": "foundry-iq-local"}
            except Exception:
                pass

        # --- Tier 5: Local simulation (no network) ---
        return None

    async def _foundry_iq_fallback(
        self, upc: str, current_name: str, current_brand: Optional[str], current_category: Optional[str]
    ) -> Optional[Dict[str, Any]]:
        """Use the local Foundry IQ knowledge graph to enrich product data.

        Looks up the product by UPC, then extracts brand, category, and attributes
        from related graph nodes. Returns a dict in the same shape as the LLM tier.
        """
        if not self._foundry_iq_service:
            return None

        kg = self._foundry_iq_service.knowledge_graph
        product_id = f"product:{hashlib.md5(upc.lower().encode()).hexdigest()[:12]}"
        product_node = kg.get_node(product_id)

        # If not in runtime graph, try re-ingesting the catalog from SQLite
        if not product_node:
            try:
                self._foundry_iq_service.ingest_product_catalog()
                product_node = kg.get_node(product_id)
            except Exception:
                pass

        if not product_node:
            return None

        related = kg.get_related(product_id)

        graph_name = product_node.label
        name = current_name
        if not name or name.lower() in {"unknown product", "unknown", ""}:
            name = graph_name
        brand = current_brand
        category = current_category
        attributes: Dict[str, Any] = {}
        description = product_node.properties.get("description", "")

        for rel in related:
            relation = rel["edge"]["relation"]
            node = rel["node"]
            if relation == "manufactured_by" and not brand:
                brand = node.get("label")
            elif relation == "belongs_to" and not category:
                category = node.get("label")
            elif relation.startswith("has_"):
                props = node.get("properties", {})
                key = props.get("key")
                value = props.get("value")
                if key and value is not None:
                    attributes[key] = value

        # Only return meaningful enrichment
        if not (brand or category or attributes or description):
            return None

        return {
            "name": name,
            "brand": brand,
            "category": category,
            "description": description or f"{name} by {brand}" if brand else name,
            "attributes": attributes,
        }

    def _build_llm_prompt(
        self,
        upc: str,
        raw_data_list: List[Dict[str, Any]],
        name: str,
        brand: Optional[str],
        category: Optional[str],
        description: str,
    ) -> str:
        """Build a structured prompt for LLM enrichment."""
        sources_text = json.dumps(raw_data_list, indent=2, default=str)[:4000]
        prompt = f"""You are a product data enrichment agent for ShelfWise, an AI Product Portfolio Builder.

UPC: {upc}
Current draft data:
  Name: {name}
  Brand: {brand or "unknown"}
  Category: {category or "unknown"}
  Description: {description}

Raw source data:
{sources_text}

Your task: Produce a JSON object with these exact keys (no markdown, no explanation):
{{
  "name": "improved product name",
  "brand": "brand name",
  "category": "product category",
  "description": "polished 1-2 sentence description",
  "attributes": {{"key": "value"}}
}}

Rules:
- Keep the name factual and concise.
- Description should be marketing-ready but accurate.
- Only include attributes you are confident about.
- If current data is already good, return it unchanged.
- Output ONLY valid JSON. No markdown fences.
"""
        return prompt

    async def _azure_inference_complete(self, prompt: str, model: str) -> Optional[Dict[str, Any]]:
        """Use azure-ai-inference ChatCompletionsClient (sync SDK wrapped for async)."""
        if not self._azure_client:
            return None

        def _sync_call():
            return self._azure_client.complete(
                messages=[
                    SystemMessage(content="You are a product data enrichment agent. Output only valid JSON."),
                    UserMessage(content=prompt),
                ],
                model=model,
                max_tokens=800,
                temperature=0.2,
            )

        response = await asyncio.to_thread(_sync_call)
        if response and response.choices:
            content = response.choices[0].message.content
            return self._parse_json_safely(content)
        return None

    async def _azure_projects_complete(self, prompt: str, model: str) -> Optional[Dict[str, Any]]:
        """Use azure-ai-projects to create/run an agent (sync SDK wrapped for async)."""
        if not self._azure_projects_client:
            return None

        def _sync_agent_workflow():
            agent = self._azure_projects_client.agents.create_agent(
                model=model,
                name="shelfwise-enricher",
                instructions="You are a product data enrichment agent. Output only valid JSON.",
            )
            thread = self._azure_projects_client.agents.create_thread()
            self._azure_projects_client.agents.create_message(
                thread_id=thread.id,
                role="user",
                content=prompt,
            )
            run = self._azure_projects_client.agents.create_run(
                thread_id=thread.id,
                assistant_id=agent.id,
            )
            import time

            for _ in range(30):
                run = self._azure_projects_client.agents.get_run(thread_id=thread.id, run_id=run.id)
                if run.status in ("completed", "failed", "cancelled"):
                    break
                time.sleep(1)
            if run.status == "completed":
                messages = self._azure_projects_client.agents.list_messages(thread_id=thread.id)
                for msg in reversed(messages.data):
                    if msg.role == "assistant" and msg.content:
                        text = msg.content[0].text.value if msg.content[0].text else ""
                        result = self._parse_json_safely(text)
                        self._azure_projects_client.agents.delete_agent(agent.id)
                        return result
            self._azure_projects_client.agents.delete_agent(agent.id)
            return None

        return await asyncio.to_thread(_sync_agent_workflow)

    async def _openai_compatible_complete(self, prompt: str, model: str) -> Optional[Dict[str, Any]]:
        """Use OpenAI SDK for Ollama or GitHub Models endpoints."""
        if not self._openai_client:
            return None
        response = await self._openai_client.chat.completions.create(
            model=model,
            messages=[
                {"role": "system", "content": "You are a product data enrichment agent. Output only valid JSON."},
                {"role": "user", "content": prompt},
            ],
            max_tokens=800,
            temperature=0.2,
        )
        if response and response.choices:
            content = response.choices[0].message.content
            return self._parse_json_safely(content)
        return None

    def _parse_json_safely(self, text: str) -> Optional[Dict[str, Any]]:
        """Extract JSON from LLM response, handling markdown fences."""
        if not text:
            return None
        text = text.strip()
        if text.startswith("```"):
            lines = text.splitlines()
            if lines[0].startswith("```"):
                lines = lines[1:]
            if lines and lines[-1].startswith("```"):
                lines = lines[:-1]
            text = "\n".join(lines).strip()
        try:
            return json.loads(text)
        except json.JSONDecodeError:
            return None

    # -----------------------------------------------------------------------
    # Source weighting & resolution
    # -----------------------------------------------------------------------
    def _weight_sources(self, raw_data_list: List[Dict[str, Any]]) -> List[Tuple[Dict[str, Any], float]]:
        weighted = []
        for data in raw_data_list:
            if not data.get("success"):
                continue
            source_name = data.get("source", "Unknown")
            weight = SOURCE_WEIGHTS.get(source_name, 0.30)
            weighted.append((data, weight))
        weighted.sort(key=lambda x: x[1], reverse=True)
        return weighted

    def _resolve_name(self, weighted_sources: List[Tuple[Dict, float]]) -> Tuple[str, List[str]]:
        candidates = []
        for data, weight in weighted_sources:
            name = data.get("name")
            if name and len(name.strip()) > 0:
                candidates.append((name.strip(), weight, data.get("source", "Unknown")))

        if not candidates:
            return "Unknown Product", []

        seen_canonical = {}
        deduped = []
        for name, weight, source in candidates:
            can = _canonicalize(name)
            if can not in seen_canonical:
                seen_canonical[can] = (name, weight, source)
                deduped.append((name, weight, source))
            else:
                old_name, old_w, old_src = seen_canonical[can]
                if weight > old_w:
                    seen_canonical[can] = (name, weight, f"{old_src},{source}")

        deduped.sort(key=lambda x: (x[1], len(x[0])), reverse=True)

        best_name = deduped[0][0]
        sources_used = [deduped[0][2]]

        for name, weight, source in deduped[1:]:
            sim = _jaccard_similarity(best_name.lower(), name.lower())
            if sim > 0.5:
                sources_used.append(source)

        best_name = " ".join(best_name.split())
        return best_name, list(dict.fromkeys(sources_used))

    def _resolve_brand(self, weighted_sources: List[Tuple[Dict, float]]) -> Tuple[Optional[str], List[str]]:
        for data, weight in weighted_sources:
            brand = data.get("brand")
            if brand and len(str(brand).strip()) > 0:
                return str(brand).strip(), [data.get("source", "Unknown")]
        return None, []

    def _resolve_category(self, weighted_sources: List[Tuple[Dict, float]]) -> Tuple[Optional[str], List[str]]:
        for data, weight in weighted_sources:
            if data.get("source") == "Open Food Facts":
                cat = data.get("category")
                if cat and len(str(cat).strip()) > 0:
                    return str(cat).strip(), ["Open Food Facts"]
        for data, weight in weighted_sources:
            cat = data.get("category")
            if cat and len(str(cat).strip()) > 0:
                return str(cat).strip(), [data.get("source", "Unknown")]
        return None, []

    def _build_description(self, fields: Dict, weighted_sources: List[Tuple[Dict, float]]) -> str:
        parts = []
        name = fields.get("name")
        brand = fields.get("brand")
        category = fields.get("category")
        attrs = fields.get("attributes", {})

        if name and brand:
            parts.append(f"{name} by {brand}")
        elif name:
            parts.append(name)

        if category:
            parts.append(f"Category: {category}")

        notable = []
        for key in ["size", "weight", "quantity", "flavor", "color", "container", "material", "dimensions"]:
            if key in attrs:
                notable.append(f"{key.capitalize()}: {attrs[key]}")
        if notable:
            parts.append(" | ".join(notable))

        nutriments = attrs.get("nutriments", {})
        if isinstance(nutriments, dict):
            nutrition_parts = []
            for k in ["energy-kcal_100g", "proteins_100g", "carbohydrates_100g", "fat_100g", "sugars_100g"]:
                if k in nutriments:
                    short = k.replace("_100g", "").replace("energy-kcal", "calories")
                    nutrition_parts.append(f"{short}: {nutriments[k]}")
            if nutrition_parts:
                parts.append("Nutrition per 100g: " + ", ".join(nutrition_parts))

        if parts:
            return " ".join(parts)

        for data, weight in weighted_sources:
            desc = data.get("description")
            if desc and len(str(desc).strip()) > 5:
                return str(desc).strip()

        return f"Product information for UPC {fields.get('upc', 'unknown')}"

    async def _select_images(
        self,
        upc: str,
        weighted_sources: List[Tuple[Dict, float]],
        name: str,
        brand: Optional[str],
    ) -> Tuple[List[Dict], Optional[str]]:
        seen_urls = set()
        candidates = []
        for data, weight in weighted_sources:
            for url in data.get("image_urls", []):
                if url and url not in seen_urls:
                    seen_urls.add(url)
                    candidates.append({"url": url, "source": data.get("source", "Unknown"), "score": round(weight, 3)})

        if not candidates:
            return [], None

        # Run deterministic verification pipeline and return a ranked gallery of
        # verified, marketplace-ready photos. Deduplication with perceptual
        # hashing keeps multi-angle shots while removing near-duplicates.
        try:
            verified_images, best_url = await select_verified_images(
                candidates=candidates,
                product_name=name,
                product_brand=brand,
                max_images=5,
            )
            if verified_images:
                return verified_images, best_url
        except Exception as e:
            logger = logging.getLogger("shelfwise")
            logger.warning(f"UPC {upc}: image verification failed ({e}); falling back to source-weighted ranking")

        # Fallback: use the highest source-weighted candidate raw
        candidates.sort(key=lambda x: x["score"], reverse=True)
        return candidates[:5], candidates[0]["url"] if candidates else None

    def _merge_attributes(self, weighted_sources: List[Tuple[Dict, float]]) -> Dict[str, Any]:
        merged = {}
        for data, weight in reversed(weighted_sources):
            attrs = data.get("attributes", {})
            if isinstance(attrs, dict):
                for key, value in attrs.items():
                    if value is not None and str(value).strip():
                        merged[key] = value
        return merged

    def _compute_confidence(
        self, weighted_sources: List[Tuple[Dict, float]], resolved_fields_count: int, name_sources: List[str]
    ) -> float:
        if not weighted_sources:
            return 0.0

        total_weight = sum(w for _, w in weighted_sources)
        avg_weight = total_weight / len(weighted_sources)
        confidence = avg_weight

        num_sources = len(weighted_sources)
        if num_sources > 1:
            confidence += min(0.1 * (num_sources - 1), 0.3)
        else:
            confidence -= 0.2

        confidence += min(0.05 * resolved_fields_count, 0.15)

        unique_agreeing = len(set(name_sources))
        if unique_agreeing > 1:
            confidence += min(0.05 * (unique_agreeing - 1), 0.15)

        source_names = {s.get("source", "") for s, _ in weighted_sources}
        if source_names == {"Demo Fallback"}:
            confidence -= 0.3

        return max(0.0, min(1.0, confidence))

    def _foundry_iq_ground(self, resolved_fields: Dict, weighted_sources: List[Tuple[Dict, float]]) -> List[Dict]:
        citations = []
        for data, weight in weighted_sources:
            source_name = data.get("source", "Unknown")
            source_url = data.get("source_url")
            fields = []
            if data.get("name") and resolved_fields.get("name"):
                fields.append("name")
            if data.get("brand") and resolved_fields.get("brand"):
                fields.append("brand")
            if data.get("category") and resolved_fields.get("category"):
                fields.append("category")
            if data.get("image_urls"):
                fields.append("images")
            if data.get("attributes"):
                fields.append("attributes")
            if data.get("description"):
                fields.append("description")
            if not fields:
                fields = ["raw data"]

            note = f"Contributed {', '.join(fields)}"
            elapsed = data.get("_elapsed_ms")
            if elapsed is not None:
                note += f" ({elapsed}ms)"

            citations.append(
                {
                    "source": source_name,
                    "source_url": source_url,
                    "fields": fields,
                    "confidence": round(weight, 3),
                    "note": note,
                }
            )
        return citations
