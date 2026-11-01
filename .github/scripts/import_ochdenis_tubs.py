#!/usr/bin/env python3
"""Download the first (Tub) image for each product in OchDenis' flavour catalogue."""
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

PAGE = "https://ochdenis.de/holy/sorten"
EXPECTED = {"Energy": 44, "Iced Tea": 23, "Hydration": 20, "Milkshake": 11, "Syrup": 10}
FOLDERS = {"Energy": "energy", "Iced Tea": "iced-tea", "Hydration": "hydration", "Milkshake": "milkshake", "Syrup": "syrup"}

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Images-Importer/1.0)",
    "Referer": PAGE,
})

def slug(text):
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode()
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", text)).strip("-")

def get_img_src(img):
    for key in ("data-src", "data-lazy-src", "data-original", "src"):
        value = img.get(key)
        if value and not value.startswith("data:"):
            return urljoin(PAGE, value)
    srcset = img.get("srcset") or img.get("data-srcset")
    if srcset:
        return urljoin(PAGE, srcset.split(",")[-1].strip().split()[0])
    return None

def parse_catalog(html):
    soup = BeautifulSoup(html, "html.parser")
    items = []
    active_category = None

    # Product groups appear in document order. Their group heading is "HOLY <category>".
    for node in soup.find_all(["h2", "h3", "h4", "img"]):
        if node.name in ("h2", "h3", "h4"):
            heading = node.get_text(" ", strip=True).casefold()
            for category in EXPECTED:
                if "holy" in heading and category.casefold() in heading:
                    active_category = category
                    break
            continue

        if not active_category:
            continue
        alt = (node.get("alt") or "").strip()
        if not alt or alt.casefold() in {"image", "produktbild"}:
            continue

        # Walk up to the smallest card that contains the product number and title.
        card = None
        number = None
        for parent in node.parents:
            if getattr(parent, "name", None) in ("body", "html"):
                break
            text = parent.get_text(" ", strip=True)
            match = re.search(r"#\s*0*(\d{1,2})\b", text)
            if match and alt.casefold() in text.casefold():
                card = parent
                number = int(match.group(1))
                break
        if card is None:
            continue

        title_node = card.find(["h3", "h4"])
        title = title_node.get_text(" ", strip=True) if title_node else alt
        # OchDenis prefixes some display titles with their category name. Our filenames
        # keep the established category prefix separate, so remove that duplicate.
        title = re.sub(r"^(Hydration|Milkshake)\s+", "", title, flags=re.IGNORECASE)
        src = get_img_src(node)
        if src:
            items.append({"category": active_category, "number": number, "title": title, "url": src})

    # Responsive layouts can repeat the same product image; keep the first occurrence.
    unique = {}
    for item in items:
        unique.setdefault((item["category"], item["number"]), item)
    return list(unique.values())

def main():
    response = session.get(PAGE, timeout=45)
    response.raise_for_status()
    products = parse_catalog(response.text)
    counts = Counter(item["category"] for item in products)
    print("Discovered catalogue:", {category: counts.get(category, 0) for category in EXPECTED})

    missing = {}
    for category, expected_count in EXPECTED.items():
        found_numbers = {item["number"] for item in products if item["category"] == category}
        missing_numbers = sorted(set(range(1, expected_count + 1)) - found_numbers)
        if len(found_numbers) != expected_count or missing_numbers:
            missing[category] = {
                "expected": expected_count,
                "found": len(found_numbers),
                "missing_numbers": missing_numbers,
            }
    if missing:
        print("Catalogue incomplete or markup changed; refusing partial import:")
        print(missing)
        sys.exit(2)

    imported = []
    for item in sorted(products, key=lambda value: (value["category"], value["number"])):
        host = urlparse(item["url"]).hostname
        if host not in {"ochdenis.de", "www.ochdenis.de"}:
            raise RuntimeError(f"Image URL is not hosted by OchDenis: {item['url']}")

        image_response = session.get(item["url"], timeout=45)
        image_response.raise_for_status()
        if not image_response.headers.get("Content-Type", "").lower().startswith("image/"):
            raise RuntimeError(f"Not an image: {item['url']}")

        with Image.open(BytesIO(image_response.content)) as image:
            image.verify()
            image_format = (image.format or "").upper()
        extension = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg"}.get(image_format)
        if not extension:
            raise RuntimeError(f"Unsupported image format {image_format}: {item['url']}")

        filename = f"{item['category']}_#{item['number']}_{slug(item['title'])}{extension}"
        target = Path("sorten") / FOLDERS[item["category"]] / filename
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_bytes(image_response.content)
        imported.append(target.as_posix())
        print(f"OK {target}")

    total_expected = sum(EXPECTED.values())
    if len(imported) != total_expected:
        raise RuntimeError(f"Expected {total_expected} images, downloaded {len(imported)}")

    summary = [
        "# OchDenis Tub image import",
        "",
        f"Successfully downloaded and validated **{len(imported)}** first product images (Tubs).",
        "",
    ]
    summary.extend(f"- {category}: {EXPECTED[category]}" for category in EXPECTED)
    Path("/tmp/ochdenis-summary.md").write_text("\n".join(summary), encoding="utf-8")
    print(f"SUCCESS: {len(imported)} images ready for commit.")

if __name__ == "__main__":
    main()
