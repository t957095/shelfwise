"""ShelfWise Verified Product Image Pipeline.

Downloads candidate product images and scores them on:
- White / clean background
- Resolution and aspect ratio quality
- Visual clarity / central product focus
- Deduplication across sources

The deterministic scorer runs locally with Pillow. If a Microsoft Foundry /
Azure OpenAI vision endpoint is configured, an optional LLM-vision check can
further verify that the image actually depicts the named product.
"""

from __future__ import annotations

import asyncio
import io
import logging
import os
from typing import Any, Dict, List, Optional, Tuple
from urllib.parse import urlparse

import httpx
from PIL import Image, ImageStat

try:
    from openai import AsyncOpenAI
    _OPENAI_AVAILABLE = True
except Exception:
    _OPENAI_AVAILABLE = False

logger = logging.getLogger("shelfwise.image_verifier")

# Minimum acceptable image dimensions
MIN_WIDTH = 300
MIN_HEIGHT = 300
MAX_ASPECT_RATIO = 3.0  # width / height

# Background scoring thresholds
WHITE_BG_THRESHOLD = 240  # 0-255; corner pixels must average above this
CLEAN_EDGE_RATIO = 0.75  # fraction of edge pixels that must be near-white


def _is_valid_image_url(url: str) -> bool:
    if not url or not url.startswith("http"):
        return False
    parsed = urlparse(url)
    if not parsed.netloc or not parsed.path:
        return False
    ext = os.path.splitext(parsed.path.lower())[1]
    if ext and ext not in {".jpg", ".jpeg", ".png", ".webp", ".gif", ".bmp"}:
        return False
    blocked = {"googletagmanager.com", "doubleclick.net", "google-analytics.com"}
    return not any(d in parsed.netloc for d in blocked)


async def _download_image(client: httpx.AsyncClient, url: str, timeout: float = 15.0) -> Optional[Image.Image]:
    """Download and open an image."""
    try:
        response = await client.get(url, timeout=timeout, follow_redirects=True)
        response.raise_for_status()
        content = response.content
        if not content:
            return None
        img = Image.open(io.BytesIO(content))
        img.load()  # force load so we can close the bytes buffer
        if img.mode in ("RGBA", "P"):
            img = img.convert("RGB")
        return img
    except Exception as e:
        logger.debug(f"Failed to download image {url}: {e}")
        return None


def _white_background_score(img: Image.Image) -> float:
    """Score how clean/white the background is based on corner/edge samples."""
    width, height = img.size
    if width < 20 or height < 20:
        return 0.0

    # Sample a 10% border strip
    border_w = max(1, width // 10)
    border_h = max(1, height // 10)

    # Edge regions: top, bottom, left, right strips
    regions = [
        img.crop((0, 0, width, border_h)),
        img.crop((0, height - border_h, width, height)),
        img.crop((0, 0, border_w, height)),
        img.crop((width - border_w, 0, width, height)),
    ]

    total_pixels = 0
    clean_pixels = 0
    brightness_sum = 0.0
    for region in regions:
        stat = ImageStat.Stat(region)
        # Convert mean (R, G, B) to perceived brightness
        r_mean, g_mean, b_mean = stat.mean[:3]
        brightness = 0.299 * r_mean + 0.587 * g_mean + 0.114 * b_mean
        brightness_sum += brightness
        region_pixels = region.size[0] * region.size[1]
        total_pixels += region_pixels
        # Count pixels close to white
        region_data = list(region.get_flattened_data())
        for pixel in region_data:
            pr, pg, pb = pixel[:3]
            if pr >= WHITE_BG_THRESHOLD and pg >= WHITE_BG_THRESHOLD and pb >= WHITE_BG_THRESHOLD:
                clean_pixels += 1

    if total_pixels == 0:
        return 0.0

    avg_brightness = brightness_sum / len(regions)
    clean_ratio = clean_pixels / total_pixels

    # Combine brightness and clean ratio into 0-1 score
    brightness_score = min(avg_brightness / 255.0, 1.0)
    score = 0.4 * brightness_score + 0.6 * clean_ratio
    return round(score, 3)


def _quality_score(img: Image.Image) -> float:
    """Score image resolution and aspect ratio suitability for e-commerce."""
    width, height = img.size
    if width < MIN_WIDTH or height < MIN_HEIGHT:
        return 0.0

    # Prefer square-ish images typical for product listings
    aspect = width / max(height, 1)
    if aspect > MAX_ASPECT_RATIO or aspect < 1 / MAX_ASPECT_RATIO:
        aspect_score = 0.3
    else:
        aspect_score = 1.0 - min(abs(aspect - 1.0), 1.0) * 0.7

    # Resolution score: larger is better, with diminishing returns
    mpixels = (width * height) / 1_000_000
    resolution_score = min(mpixels / 1.0, 1.0)

    return round(0.5 * aspect_score + 0.5 * resolution_score, 3)


def _focus_score(img: Image.Image) -> float:
    """Estimate central product focus using simple edge density contrast."""
    width, height = img.size
    if width < 40 or height < 40:
        return 0.0

    # Convert to grayscale and compute center vs edge brightness variance
    gray = img.convert("L")

    # Center crop (60% of image)
    left = width * 0.2
    top = height * 0.2
    right = width * 0.8
    bottom = height * 0.8
    center = gray.crop((left, top, right, bottom))
    edge = gray.crop((0, 0, width, height))

    center_var = ImageStat.Stat(center).var[0]
    edge_var = ImageStat.Stat(edge).var[0]

    # Higher center variance relative to overall variance suggests product detail in center
    if edge_var == 0:
        return 0.5
    ratio = center_var / edge_var
    score = min(ratio / 1.5, 1.0)
    return round(max(0.0, score), 3)


def _image_hash(img: Image.Image, hash_size: int = 8) -> str:
    """Compute a simple perceptual hash for deduplication."""
    gray = img.convert("L")
    resized = gray.resize((hash_size + 1, hash_size), Image.Resampling.LANCZOS)
    pixels = list(resized.get_flattened_data())
    diff = []
    for row in range(hash_size):
        for col in range(hash_size):
            left = pixels[row * (hash_size + 1) + col]
            right = pixels[row * (hash_size + 1) + col + 1]
            diff.append(left > right)
    bits = "".join(str(int(b)) for b in diff)
    return hex(int(bits, 2))[2:].zfill(hash_size * hash_size // 4)


def _hamming_distance(a: str, b: str) -> int:
    """Compute Hamming distance between two hex hashes."""
    if len(a) != len(b):
        return 999
    try:
        x = int(a, 16) ^ int(b, 16)
    except ValueError:
        return 999
    return bin(x).count("1")


class VerifiedImageResult:
    """Result of verifying a single candidate image."""

    def __init__(
        self,
        url: str,
        source: str,
        white_bg_score: float,
        quality_score: float,
        focus_score: float,
        phash: str,
        width: int,
        height: int,
        content_type: Optional[str] = None,
    ):
        self.url = url
        self.source = source
        self.white_bg_score = white_bg_score
        self.quality_score = quality_score
        self.focus_score = focus_score
        self.phash = phash
        self.width = width
        self.height = height
        self.content_type = content_type
        self.overall_score = round(
            0.45 * white_bg_score + 0.30 * quality_score + 0.25 * focus_score, 3
        )

    def to_dict(self) -> Dict[str, Any]:
        return {
            "url": self.url,
            "source": self.source,
            "score": self.overall_score,
            "white_background_score": self.white_bg_score,
            "quality_score": self.quality_score,
            "focus_score": self.focus_score,
            "width": self.width,
            "height": self.height,
            "verified": self.is_verified(),
        }

    def is_verified(self, threshold: float = 0.55) -> bool:
        return self.overall_score >= threshold and self.quality_score > 0.0


class ProductImageVerifier:
    """Verify and rank product images from multiple sources."""

    def __init__(self, client: Optional[httpx.AsyncClient] = None):
        self.client = client or httpx.AsyncClient(timeout=15.0, follow_redirects=True)
        self._owned = client is None

    async def verify_images(
        self,
        candidates: List[Dict[str, Any]],
        product_name: Optional[str] = None,
        product_brand: Optional[str] = None,
    ) -> List[VerifiedImageResult]:
        """Verify a list of candidate images.

        candidates: list of {"url": str, "source": str, "score": float}
        Returns: ranked list of VerifiedImageResult
        """
        tasks = []
        for cand in candidates:
            url = cand.get("url", "")
            if not _is_valid_image_url(url):
                continue
            tasks.append(self._verify_one(url, cand.get("source", "Unknown")))

        if not tasks:
            return []

        results = await asyncio.gather(*tasks)
        results = [r for r in results if r is not None]

        # Deduplicate near-identical images, keeping highest score
        deduped: List[VerifiedImageResult] = []
        for r in sorted(results, key=lambda x: x.overall_score, reverse=True):
            if not any(_hamming_distance(r.phash, existing.phash) <= 5 for existing in deduped):
                deduped.append(r)

        return deduped

    async def _verify_one(self, url: str, source: str) -> Optional[VerifiedImageResult]:
        img = await _download_image(self.client, url)
        if img is None:
            return None
        try:
            white = _white_background_score(img)
            quality = _quality_score(img)
            focus = _focus_score(img)
            phash = _image_hash(img)
            return VerifiedImageResult(
                url=url,
                source=source,
                white_bg_score=white,
                quality_score=quality,
                focus_score=focus,
                phash=phash,
                width=img.width,
                height=img.height,
            )
        except Exception as e:
            logger.debug(f"Error scoring image {url}: {e}")
            return None
        finally:
            img.close()

    async def vision_verify(
        self,
        image_url: str,
        product_name: str,
        product_brand: Optional[str] = None,
    ) -> Optional[Dict[str, Any]]:
        """Optional LLM vision verification if an OpenAI-compatible endpoint is configured."""
        endpoint = os.environ.get("FOUNDRY_ENDPOINT", "") or os.environ.get("AZURE_FOUNDRY_ENDPOINT", "")
        api_key = os.environ.get("FOUNDRY_API_KEY", "") or os.environ.get("AZURE_FOUNDRY_KEY", "")
        if not endpoint or not api_key or not _OPENAI_AVAILABLE:
            return None
        try:
            client = AsyncOpenAI(base_url=endpoint, api_key=api_key)
            brand_hint = f" made by {product_brand}" if product_brand else ""
            prompt = (
                f"Does this image clearly show the product '{product_name}'{brand_hint}? "
                "Answer with a JSON object only: {\"matches\": true/false, \"confidence\": 0.0-1.0, \"white_background\": true/false, \"issues\": [\"issue1\", ...]}"
            )
            response = await client.chat.completions.create(
                model=os.environ.get("FOUNDRY_MODEL", "gpt-4o"),
                messages=[
                    {"role": "system", "content": "You are a product image verifier."},
                    {"role": "user", "content": [
                        {"type": "text", "text": prompt},
                        {"type": "image_url", "image_url": {"url": image_url}},
                    ]},
                ],
                max_tokens=300,
                temperature=0.2,
            )
            content = response.choices[0].message.content
            # Parse JSON roughly
            import json
            try:
                data = json.loads(content.strip().strip("`").replace("json", ""))
                return data
            except Exception:
                return {"raw": content}
        except Exception as e:
            logger.debug(f"Vision verification failed for {image_url}: {e}")
            return None

    async def close(self):
        if self._owned:
            await self.client.aclose()


async def select_verified_images(
    candidates: List[Dict[str, Any]],
    product_name: Optional[str] = None,
    product_brand: Optional[str] = None,
    max_images: int = 5,
    client: Optional[httpx.AsyncClient] = None,
) -> Tuple[List[Dict[str, Any]], Optional[str]]:
    """Convenience function: verify candidates and return top images + best URL.

    Returns ranked list of verified image dicts and the best image URL.
    """
    verifier = ProductImageVerifier(client=client)
    try:
        verified = await verifier.verify_images(candidates, product_name, product_brand)
        verified = [v for v in verified if v.is_verified()]
        verified.sort(key=lambda x: x.overall_score, reverse=True)
        top = verified[:max_images]
        images = [v.to_dict() for v in top]
        best_url = top[0].url if top else None
        return images, best_url
    finally:
        await verifier.close()
