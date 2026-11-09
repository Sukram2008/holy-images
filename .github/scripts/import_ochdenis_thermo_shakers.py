#!/usr/bin/env python3
"""Import every first product image from the exact OchDenis Thermo category."""
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
CATEGORY = "Thermo"
EXPECTED = 95
REPO = "Sukram2008/holy-images"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Thermo-Importer/1.0)",
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
        # Prefer the largest advertised image candidate.
        return urljoin(PAGE, srcset.split(",")[-1].strip().split()[0])
    link = img.find_parent("a")
    if link and link.get("href"):
        return urljoin(PAGE, link["href"])
    return None

def product_card_for_heading(heading):
    """Find the nearest card containing one product heading and an image."""
    for parent in heading.parents:
        if getattr(parent, "name", None) in {"body", "html"}:
            break
        headings = parent.find_all(["h3", "h4"])
        images = parent.find_all("img")
        if len(headings) == 1 and images:
            return parent
    return None

def discover_thermo(html: str):
    soup = BeautifulSoup(html, "html.parser")
    active = False
    products = []
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
            print(f"WARNING: no product image node for {name}")
            continue
        url = image_source(img)
        if not url:
            print(f"WARNING: no image URL for {name}")
            continue
        products.append({"name": name, "url": url})

    return products

def main():
    response = session.get(PAGE, timeout=60)
    response.raise_for_status()
    products = discover_thermo(response.text)

    print(f"Discovered {len(products)} products in exact category '{CATEGORY}' (expected {EXPECTED}):")
    for i, item in enumerate(products, start=1):
        print(f"{i:02d}. {item['name']}")

    if len(products) != EXPECTED:
        print(f"ERROR: expected {EXPECTED} Thermo products, found {len(products)}.")
        print("No image files or success commit will be made. Check the live OchDenis category.")
        sys.exit(2)

    original_dir = Path("shaker") / "thermo"
    alias_dir = Path("s")
    original_dir.mkdir(parents=True, exist_ok=True)
    alias_dir.mkdir(parents=True, exist_ok=True)

    catalog = []
    image_map = {}
    errors = []
    totals = {}
    for i, item in enumerate(products):
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

            number = i + 1
            original_name = f"Thermo_{number:03d}_{slug(item['name'])}{extension}"
            original_path = original_dir / original_name
            alias_path = alias_dir / f"th{number:03d}{extension}"

            original_path.write_bytes(image_response.content)
            alias_path.write_bytes(image_response.content)

            cdn_url = f"https://cdn.jsdelivr.net/gh/{REPO}@main/{alias_path.as_posix()}"
            mapping_key = f"Shaker|Thermo|{i}"
            same_name_indices = [j for j, product in enumerate(products) if product["name"] == item["name"]]
            display_name = item["name"]
            if len(same_name_indices) > 1:
                display_name = f"{item['name']} (Variante {same_name_indices.index(i) + 1})"

            catalog.append({
                "index": i,
                "name": display_name,
                "sourceName": item["name"],
                "path": original_path.as_posix(),
                "cdnPath": alias_path.as_posix(),
                "url": cdn_url,
                "source": item["url"],
            })
            image_map[mapping_key] = cdn_url
            print(f"OK {number:03d} {item['name']} -> {alias_path}")
        except Exception as exc:
            errors.append(f"{item['name']}: {exc}")

    if errors or len(catalog) != EXPECTED or len(image_map) != EXPECTED:
        print("ERROR: Thermo import incomplete; no success commit will be made.")
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
    Path("/tmp/thermo-shaker-summary.md").write_text(
        "# OchDenis Thermo shaker import\n\n"
        f"Successfully downloaded and verified **{len(catalog)}** Thermo shaker images.\n\n"
        + "\n".join(f"- {item['name']}" for item in catalog),
        encoding="utf-8",
    )
    print(f"SUCCESS: {len(catalog)} Thermo original images and compact jsDelivr aliases are ready for commit.")

if __name__ == "__main__":
    main()
