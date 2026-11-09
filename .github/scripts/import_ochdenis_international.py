#!/usr/bin/env python3
"""Import five remaining exact OchDenis shaker categories into holy-images."""
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
    {"name": "Creator - FR", "folder": "creator-fr", "prefix": "Creator-FR", "alias": "cf", "expected": 27, "digits": 3},
    {"name": "Creator - FR - Thermo", "folder": "creator-fr-thermo", "prefix": "Creator-FR-Thermo", "alias": "cft", "expected": 18, "digits": 2},
    {"name": "Creator - FR - Glasflasche", "folder": "creator-fr-glasflasche", "prefix": "Creator-FR-Glasflasche", "alias": "cfg", "expected": 2, "digits": 2},
    {"name": "Creator - UK", "folder": "creator-uk", "prefix": "Creator-UK", "alias": "uk", "expected": 3, "digits": 2},
    {"name": "Sport-Flasche", "folder": "sport-flasche", "prefix": "Sport-Flasche", "alias": "sf", "expected": 2, "digits": 2},
]

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-International-Shaker-Importer/1.0)",
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
        products = discover_category(soup, category["name"])
        print(f"\n{category['name']}: {len(products)} products (expected {category['expected']})")
        for index, item in enumerate(products, 1):
            print(f"{index:02d}. {item['name']}")
        if len(products) != category["expected"]:
            print(
                f"ERROR: expected {category['expected']} entries in '{category['name']}', "
                f"found {len(products)}. No batch will be committed."
            )
            sys.exit(2)
        discovered[category["name"]] = products

    errors = []
    total = 0
    for category in CATEGORIES:
        items = discovered[category["name"]]
        original_dir = Path("shaker") / category["folder"]
        alias_dir = Path("s")
        original_dir.mkdir(parents=True, exist_ok=True)
        alias_dir.mkdir(parents=True, exist_ok=True)

        catalog = []
        image_map = {}
        for index, item in enumerate(items):
            host = urlparse(item["url"]).hostname or ""
            if host != "ochdenis.de" and not host.endswith(".ochdenis.de"):
                errors.append(f"Rejected non-OchDenis host for {category['name']} / {item['name']}: {item['url']}")
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
                catalog.append({
                    "index": index,
                    "name": item["name"],
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

        expected = category["expected"]
        if len(catalog) != expected or len(image_map) != expected:
            errors.append(
                f"{category['name']}: expected {expected} images/mappings, "
                f"got {len(catalog)}/{len(image_map)}"
            )

        if not errors:
            (original_dir / "catalog.json").write_text(
                json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
            (original_dir / "image-url-map.json").write_text(
                json.dumps(image_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
            )
        total += len(catalog)

    if errors:
        print("\nERROR: import incomplete; no success commit will be made.")
        for error in errors:
            print(f" - {error}")
        sys.exit(3)

    summary = ["# OchDenis additional shaker categories", "", f"Imported and validated **{total}** product images.", ""]
    for category in CATEGORIES:
        summary.append(f"## {category['name']} ({len(discovered[category['name']])})")
        summary.extend(f"- {item['name']}" for item in discovered[category["name"]])
        summary.append("")
    Path("/tmp/international-shaker-summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"\nSUCCESS: {total} images and CDN aliases ready for commit.")

if __name__ == "__main__":
    main()
