#!/usr/bin/env python3
"""Import every first product image from the OchDenis Giga Gallon and Glasflasche categories."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

PAGE = "https://ochdenis.de/holy/shaker"
CATEGORIES = [
    {"name": "Giga Gallon", "folder": "giga-gallon", "prefix": "Giga-Gallon", "alias": "gg", "expected": 7},
    {"name": "Glasflasche", "folder": "glasflasche", "prefix": "Glasflasche", "alias": "gf", "expected": 26},
]
REPO = "Sukram2008/holy-images"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Glass-and-Giga-Importer/1.0)",
    "Referer": PAGE,
})

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", text)).strip("-") or "product"

def image_source(img) -> str | None:
    for attr in ("data-src", "data-lazy-src", "data-original", "src"):
        value = (img.get(attr) or "").strip()
        if value and not value.startswith("data:"):
            return urljoin(PAGE, value)
    srcset = (img.get("data-srcset") or img.get("srcset") or "").strip()
    if srcset:
        return urljoin(PAGE, srcset.split(",")[-1].strip().split()[0])
    link = img.find_parent("a")
    if link and link.get("href"):
        return urljoin(PAGE, link["href"])
    return None

def product_card_for_heading(heading):
    """Find the nearest card containing exactly this one product heading and an image."""
    for parent in heading.parents:
        if getattr(parent, "name", None) in {"body", "html"}:
            break
        headings = parent.find_all(["h3", "h4"])
        images = parent.find_all("img")
        if len(headings) == 1 and images:
            return parent
    return None

def discover_category(soup: BeautifulSoup, category_name: str):
    products = []
    active_category = None
    seen_card_images = set()

    # Use h2 to identify category boundaries and h3/h4 as product records.
    # This preserves repeated product names when they are separate cards.
    for node in soup.find_all(["h2", "h3", "h4"]):
        if node.name == "h2":
            active_category = normalize(node.get_text(" ", strip=True))
            continue
        if active_category != category_name or node.name not in {"h3", "h4"}:
            continue

        name = normalize(node.get_text(" ", strip=True))
        if not name:
            continue

        card = product_card_for_heading(node)
        img = card.find("img") if card else None
        if img is None:
            # Some page layouts put image and heading in sibling wrappers.
            # Fall back to the closest preceding product image before this heading.
            previous = node.find_previous("img")
            if previous is not None:
                previous_h2 = previous.find_previous("h2")
                if previous_h2 and normalize(previous_h2.get_text(" ", strip=True)) == category_name:
                    img = previous

        if img is None:
            print(f"WARNING: no product image node found for {category_name} / {name}")
            continue

        url = image_source(img)
        if not url:
            print(f"WARNING: no image URL found for {category_name} / {name}")
            continue

        # A product card may include responsive duplicates, but separate cards
        # with the same visible name are retained as distinct catalog entries.
        card_identity = id(card) if card is not None else (name, url)
        if card_identity in seen_card_images:
            continue
        seen_card_images.add(card_identity)
        products.append({"category": category_name, "name": name, "url": url})

    return products

def main():
    response = session.get(PAGE, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    all_products = {}
    for category in CATEGORIES:
        products = discover_category(soup, category["name"])
        print(f"\n{category['name']}: {len(products)} products (expected {category['expected']})")
        for i, item in enumerate(products, 1):
            print(f"  {i:02d}. {item['name']}")

        if len(products) != category["expected"]:
            print(
                f"ERROR: expected exactly {category['expected']} products for {category['name']}, "
                f"found {len(products)}. No files will be committed."
            )
            sys.exit(2)
        all_products[category["name"]] = products

    errors = []
    for category in CATEGORIES:
        items = all_products[category["name"]]
        original_dir = Path("shaker") / category["folder"]
        original_dir.mkdir(parents=True, exist_ok=True)
        catalog = []
        image_map = {}

        for index, item in enumerate(items):
            parsed = urlparse(item["url"])
            host = parsed.hostname or ""
            if host != "ochdenis.de" and not host.endswith(".ochdenis.de"):
                errors.append(f"Rejected non-OchDenis image host for {item['name']}: {item['url']}")
                continue

            try:
                image_response = session.get(item["url"], timeout=60)
                image_response.raise_for_status()
                if not image_response.headers.get("Content-Type", "").lower().startswith("image/"):
                    raise ValueError("URL did not return image content")

                with Image.open(BytesIO(image_response.content)) as image:
                    image.verify()
                    image_format = (image.format or "").upper()

                extension = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg"}.get(image_format)
                if not extension:
                    raise ValueError(f"Unsupported image format {image_format}")

                original_name = f"{category['prefix']}_{index+1:02d}_{slug(item['name'])}{extension}"
                original_path = original_dir / original_name
                alias_name = f"{category['alias']}{index+1:02d}{extension}"
                alias_path = Path("s") / alias_name
                alias_path.parent.mkdir(parents=True, exist_ok=True)

                original_path.write_bytes(image_response.content)
                alias_path.write_bytes(image_response.content)

                cdn_url = f"https://cdn.jsdelivr.net/gh/{REPO}@main/{alias_path.as_posix()}"
                mapping_key = f"Shaker|{category['name']}|{index}"
                image_map[mapping_key] = cdn_url
                catalog.append({
                    "index": index,
                    "name": item["name"],
                    "path": original_path.as_posix(),
                    "cdnPath": alias_path.as_posix(),
                    "url": cdn_url,
                    "source": item["url"],
                })
                print(f"OK {original_path} -> {alias_path}")
            except Exception as exc:
                errors.append(f"{category['name']} / {item['name']}: {exc}")

        if len(catalog) != category["expected"] or len(image_map) != category["expected"]:
            errors.append(
                f"{category['name']}: expected {category['expected']} images, "
                f"got {len(catalog)} images and {len(image_map)} mappings"
            )

        if not errors:
            (original_dir / "catalog.json").write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )
            (original_dir / "image-url-map.json").write_text(
                json.dumps(image_map, ensure_ascii=False, indent=2) + "\n",
                encoding="utf-8",
            )

    if errors:
        print("\nERROR: import incomplete; no success commit will be made.")
        for error in errors:
            print(f" - {error}")
        sys.exit(3)

    total = sum(len(v) for v in all_products.values())
    summary = ["# OchDenis shaker import", "", f"Imported and validated **{total}** product images.", ""]
    for category in CATEGORIES:
        summary.append(f"## {category['name']} ({len(all_products[category['name']])})")
        summary.extend(f"- {item['name']}" for item in all_products[category["name"]])
        summary.append("")
    Path("/tmp/giga-glass-shaker-summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"\nSUCCESS: {total} original images and compact CDN aliases are ready for commit.")

if __name__ == "__main__":
    main()
