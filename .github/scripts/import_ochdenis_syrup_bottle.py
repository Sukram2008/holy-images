#!/usr/bin/env python3
"""Import the first product image for every entry in the exact OchDenis Syrup Bottle category."""
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
CATEGORY = "Syrup Bottle"
EXPECTED = 3
REPO = "Sukram2008/holy-images"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Syrup-Bottle-Importer/1.0)",
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

def discover_products(soup: BeautifulSoup):
    products = []
    active = False
    seen_cards = set()

    for node in soup.find_all(["h2", "h3", "h4"]):
        if node.name == "h2":
            active = normalize(node.get_text(" ", strip=True)).casefold() == CATEGORY.casefold()
            continue
        if not active or node.name not in {"h3", "h4"}:
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
                if previous_h2 and normalize(previous_h2.get_text(" ", strip=True)).casefold() == CATEGORY.casefold():
                    img = previous
        if img is None:
            raise ValueError(f"No product image element found for {name}")

        url = image_source(img)
        if not url:
            raise ValueError(f"No image URL found for {name}")

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
    products = discover_products(soup)

    print(f"Discovered {len(products)} products in '{CATEGORY}' (expected {EXPECTED}):")
    for i, item in enumerate(products, 1):
        print(f"{i:02d}. {item['name']}")

    if len(products) != EXPECTED:
        print(f"ERROR: expected exactly {EXPECTED} Syrup Bottle products, found {len(products)}.")
        print("No image files or success commit will be made.")
        sys.exit(2)

    original_dir = Path("shaker") / "syrup-bottle"
    alias_dir = Path("s")
    original_dir.mkdir(parents=True, exist_ok=True)
    alias_dir.mkdir(parents=True, exist_ok=True)

    catalog = []
    image_map = {}
    errors = []
    duplicate_counts = {}
    for item in products:
        duplicate_counts[item["name"]] = duplicate_counts.get(item["name"], 0) + 1
    duplicate_seen = {}

    for index, item in enumerate(products):
        host = urlparse(item["url"]).hostname or ""
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
                raise ValueError(f"Unsupported image format: {image_format}")

            number = index + 1
            original_path = original_dir / f"Syrup-Bottle_{number:02d}_{slug(item['name'])}{extension}"
            alias_path = alias_dir / f"sb{number:02d}{extension}"
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
            image_map[f"Shaker|{CATEGORY}|{index}"] = cdn_url
            print(f"OK {original_path} -> {alias_path}")
        except Exception as exc:
            errors.append(f"{item['name']}: {exc}")

    if errors or len(catalog) != EXPECTED or len(image_map) != EXPECTED:
        print("ERROR: Syrup Bottle import incomplete; no success commit will be made.")
        for error in errors:
            print(f" - {error}")
        print(f"Verified {len(catalog)} images and {len(image_map)} URLs, expected {EXPECTED}.")
        sys.exit(3)

    (original_dir / "catalog.json").write_text(
        json.dumps(catalog, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (original_dir / "image-url-map.json").write_text(
        json.dumps(image_map, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path("/tmp/syrup-bottle-shaker-summary.md").write_text(
        "# OchDenis Syrup Bottle shaker import\n\n"
        f"Successfully downloaded and verified **{len(catalog)}** Syrup Bottle images.\n\n"
        + "\n".join(f"- {item['name']}" for item in catalog),
        encoding="utf-8",
    )
    print(f"SUCCESS: {len(catalog)} original images and CDN aliases are ready for commit.")

if __name__ == "__main__":
    main()
