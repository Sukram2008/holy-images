#!/usr/bin/env python3
"""Import first product images for three exact OchDenis Creator-DE shaker categories."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse

import requests
from bs4 import BeautifulSoup
from PIL import Image

PAGE = "https://ochdenis.de/holy/shaker"
REPO = "Sukram2008/holy-images"
CATEGORIES = [
    {"name": "Creator - DE", "folder": "creator-de", "prefix": "Creator-DE", "alias": "cd", "expected": 58, "digits": 3},
    {"name": "Creator - DE - XL", "folder": "creator-de-xl", "prefix": "Creator-DE-XL", "alias": "cx", "expected": 8, "digits": 2},
    {"name": "Creator - DE - Thermo", "folder": "creator-de-thermo", "prefix": "Creator-DE-Thermo", "alias": "ct", "expected": 9, "digits": 2},
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Creator-DE-Importer/1.0)",
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
    """Find the closest card containing one product heading and at least one image."""
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
    seen_cards = set()

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
            previous = node.find_previous("img")
            if previous is not None:
                previous_h2 = previous.find_previous("h2")
                if previous_h2 and normalize(previous_h2.get_text(" ", strip=True)) == category_name:
                    img = previous

        if img is None:
            raise ValueError(f"No product image element found for {category_name} / {name}")

        url = image_source(img)
        if not url:
            raise ValueError(f"No image URL found for {category_name} / {name}")

        # Ignore duplicate responsive cards, but keep equal names if they have distinct URLs.
        identity = (name, url)
        if identity in seen_cards:
            continue
        seen_cards.add(identity)
        products.append({"name": name, "url": url})

    return products

def main():
    response = session.get(PAGE, timeout=60)
    response.raise_for_status()
    soup = BeautifulSoup(response.text, "html.parser")

    discovered = {}
    for category in CATEGORIES:
        items = discover_category(soup, category["name"])
        print(f"\n{category['name']}: {len(items)} products (expected {category['expected']})")
        for index, item in enumerate(items, 1):
            print(f"{index:02d}. {item['name']}")

        if len(items) != category["expected"]:
            print(
                f"ERROR: expected {category['expected']} entries in '{category['name']}', "
                f"found {len(items)}. No category images will be committed."
            )
            sys.exit(2)
        discovered[category["name"]] = items

    errors = []
    for category in CATEGORIES:
        items = discovered[category["name"]]
        original_dir = Path("shaker") / category["folder"]
        alias_dir = Path("s")
        original_dir.mkdir(parents=True, exist_ok=True)
        alias_dir.mkdir(parents=True, exist_ok=True)

        catalog = []
        image_map = {}
        duplicate_counts = {}
        for item in items:
            duplicate_counts[item["name"]] = duplicate_counts.get(item["name"], 0) + 1
        duplicate_seen = {}

        for index, item in enumerate(items):
            host = urlparse(item["url"]).hostname or ""
            if host != "ochdenis.de" and not host.endswith(".ochdenis.de"):
                errors.append(f"Rejected non-OchDenis image host for {category['name']} / {item['name']}")
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
                    raise ValueError(f"Unsupported image format: {image_format}")

                number = index + 1
                digits = category["digits"]
                original_name = f"{category['prefix']}_{number:0{digits}d}_{slug(item['name'])}{extension}"
                original_path = original_dir / original_name
                alias_path = alias_dir / f"{category['alias']}{number:0{digits}d}{extension}"
                original_path.write_bytes(image_response.content)
                alias_path.write_bytes(image_response.content)

                cdn_url = f"https://cdn.jsdelivr.net/gh/{REPO}@main/{alias_path.as_posix()}"
                same_name_seen = duplicate_seen.get(item["name"], 0)
                duplicate_seen[item["name"]] = same_name_seen + 1
                display_name = item["name"]
                if duplicate_counts[item["name"]] > 1:
                    display_name = f"{item['name']} (Variante {same_name_seen + 1})"

                catalog.append({
                    "index": index,
                    "name": display_name,
                    "sourceName": item["name"],
                    "path": original_path.as_posix(),
                    "cdnPath": alias_path.as_posix(),
                    "url": cdn_url,
                    "source": item["url"],
                })
                image_map[f"Shaker|{category['name']}|{index}"] = cdn_url
                print(f"OK {original_path} -> {alias_path}")
            except Exception as exc:
                errors.append(f"{category['name']} / {item['name']}: {exc}")

        if len(catalog) != category["expected"] or len(image_map) != category["expected"]:
            errors.append(
                f"{category['name']}: expected {category['expected']} images/mappings, "
                f"got {len(catalog)}/{len(image_map)}"
            )

        if not errors:
            (original_dir / "catalog.json").write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (original_dir / "image-url-map.json").write_text(
                json.dumps(image_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )

    if errors:
        print("\nERROR: import incomplete; no success commit will be made.")
        for error in errors:
            print(f" - {error}")
        sys.exit(3)

    total = sum(len(discovered[x["name"]]) for x in CATEGORIES)
    summary = ["# OchDenis Creator-DE shaker import", "", f"Imported and validated **{total}** product images.", ""]
    for category in CATEGORIES:
        summary.append(f"## {category['name']} ({len(discovered[category['name']])})")
        summary.extend(f"- {item['name']}" for item in discovered[category["name"]])
        summary.append("")
    Path("/tmp/creator-de-shaker-summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"\nSUCCESS: {total} images and CDN aliases ready for commit.")

if __name__ == "__main__":
    main()
