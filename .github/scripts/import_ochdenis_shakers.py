#!/usr/bin/env python3
"""Import the first product image for the four standard OchDenis shaker categories."""
from __future__ import annotations

import re
import sys
import unicodedata
from collections import Counter
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

PAGE = "https://ochdenis.de/holy/shaker"
CATEGORIES = {
    "Energy": "energy",
    "Iced Tea": "iced-tea",
    "Hydration": "hydration",
    "Milkshake": "milkshake",
}
FILE_PREFIX = {
    "Energy": "Energy",
    "Iced Tea": "Iced-Tea",
    "Hydration": "Hydration",
    "Milkshake": "Milkshake",
}
session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Shaker-Image-Importer/1.0)",
    "Referer": PAGE,
})

def slug(value: str) -> str:
    value = unicodedata.normalize("NFKD", value).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", value)).strip("-")

def category_heading(text: str) -> str | None:
    text = re.sub(r"\s+", " ", text or "").strip()
    return text if text in CATEGORIES else None

def source_for_image(img) -> str | None:
    for key in ("data-src", "data-lazy-src", "data-original", "src"):
        value = (img.get(key) or "").strip()
        if value and not value.startswith("data:"):
            return urljoin(PAGE, value)
    srcset = (img.get("data-srcset") or img.get("srcset") or "").strip()
    if srcset:
        # The final srcset candidate normally carries the largest image.
        candidate = srcset.split(",")[-1].strip().split()[0]
        return urljoin(PAGE, candidate)
    link = img.find_parent("a")
    if link and link.get("href"):
        return urljoin(PAGE, link["href"])
    return None

def card_details(img):
    """Find the nearest enclosing product card with a numbered shaker heading."""
    for parent in img.parents:
        if getattr(parent, "name", None) in {"body", "html"}:
            break
        headings = parent.find_all(["h3", "h4"])
        candidates = []
        for heading in headings:
            title = re.sub(r"\s+", " ", heading.get_text(" ", strip=True)).strip()
            match = re.search(r"#\s*(\d{1,3}(?:\.\d+)?)\s*(?:[-–—:]\s*)?(.+)?$", title)
            if match:
                candidates.append((match.group(1), (match.group(2) or "").strip(), title))
        if len(candidates) == 1:
            number, name, full_title = candidates[0]
            return number, name or (img.get("alt") or "").strip() or full_title
    alt = (img.get("alt") or "").strip()
    match = re.search(r"#\s*(\d{1,3}(?:\.\d+)?)\s*(?:[-–—:]\s*)?(.+)?$", alt)
    if match:
        return match.group(1), (match.group(2) or "").strip() or alt
    return None

def discover(html: str):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    current_category = None

    # Follow the page's displayed order: a category heading applies to the
    # product cards below it, until the next category heading.
    for node in soup.find_all(["h2", "h3", "h4", "img"]):
        if node.name in {"h2", "h3", "h4"}:
            current_category = category_heading(node.get_text(" ", strip=True)) or current_category
            continue
        if current_category not in CATEGORIES:
            continue

        details = card_details(node)
        if not details:
            continue
        number, product_name = details
        url = source_for_image(node)
        if not url:
            continue

        items.append({
            "category": current_category,
            "number": number,
            "name": product_name,
            "url": url,
        })

    # A card may expose responsive/retina copies of the same product image.
    # Keep the first image in document order for each product.
    unique = {}
    for item in items:
        unique.setdefault((item["category"], item["number"]), item)
    return list(unique.values())

def main():
    response = session.get(PAGE, timeout=60)
    response.raise_for_status()
    products = discover(response.text)
    counts = Counter(item["category"] for item in products)

    print("Discovered standard shaker categories:")
    for category in CATEGORIES:
        print(f"  {category}: {counts.get(category, 0)}")
    print("Other categories such as Energy (Alt Bunt), Energy (Alt Schwarz), and Iced Tea (Alt Schwarz) are intentionally excluded.")

    missing = [category for category in CATEGORIES if counts.get(category, 0) == 0]
    if missing:
        print(f"ERROR: no product images found for: {', '.join(missing)}")
        print("No images were committed. The source page structure may have changed.")
        sys.exit(2)

    imported = []
    errors = []
    for item in sorted(products, key=lambda x: (list(CATEGORIES).index(x["category"]), x["number"])):
        parsed = urlparse(item["url"])
        if parsed.hostname != "ochdenis.de" and not (parsed.hostname or "").endswith(".ochdenis.de"):
            errors.append(f"Rejected non-OchDenis image host: {item['url']}")
            continue

        try:
            image_response = session.get(item["url"], timeout=60)
            image_response.raise_for_status()
            content_type = image_response.headers.get("Content-Type", "").lower()
            if not content_type.startswith("image/"):
                raise ValueError(f"unexpected content type {content_type!r}")

            with Image.open(BytesIO(image_response.content)) as image:
                image.verify()
                image_format = (image.format or "").upper()

            extension = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg"}.get(image_format)
            if not extension:
                raise ValueError(f"unsupported image format {image_format!r}")

            filename = f"{FILE_PREFIX[item['category']]}_#{item['number']}_{slug(item['name'])}{extension}"
            target = Path("shaker") / CATEGORIES[item["category"]] / filename
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(image_response.content)
            imported.append(target.as_posix())
            print(f"OK {target}")
        except Exception as exc:
            errors.append(f"{item['category']} #{item['number']} {item['name']}: {exc}")

    if errors:
        print("ERROR: one or more images could not be validated/downloaded:")
        for error in errors:
            print(f"  - {error}")
        sys.exit(3)

    if not imported:
        print("ERROR: no shaker images were imported.")
        sys.exit(4)

    summary = [
        "# OchDenis shaker image import",
        "",
        f"Successfully downloaded and validated **{len(imported)}** first product images.",
        "",
    ]
    summary.extend(f"- {category}: {counts.get(category, 0)}" for category in CATEGORIES)
    Path("/tmp/ochdenis-shaker-summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"SUCCESS: {len(imported)} shaker images ready for commit.")

if __name__ == "__main__":
    main()
