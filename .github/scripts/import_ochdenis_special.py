#!/usr/bin/env python3
"""Import all 66 first product images from the OchDenis 'Spezial' category."""
from __future__ import annotations

import json
import re
import sys
import unicodedata
from collections import OrderedDict
from io import BytesIO
from pathlib import Path
from urllib.parse import urljoin, urlparse, quote

import requests
from bs4 import BeautifulSoup
from PIL import Image

PAGE = "https://ochdenis.de/holy/shaker"
CATEGORY = "Spezial"
EXPECTED = 66
REPO = "Sukram2008/holy-images"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-Special-Shaker-Importer/1.0)",
    "Referer": PAGE,
})

def normalize(text: str) -> str:
    return re.sub(r"\s+", " ", text or "").strip()

def slug(text: str) -> str:
    text = unicodedata.normalize("NFKD", text).encode("ascii", "ignore").decode("ascii")
    return re.sub(r"-+", "-", re.sub(r"[^A-Za-z0-9]+", "-", text)).strip("-")

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

def discover_special_images(html: str):
    soup = BeautifulSoup(html, "html.parser")
    active_special = False
    items = OrderedDict()

    # Category headings are H2; product headings are H3/H4. The state resets
    # at EVERY H2 so items from adjacent categories can never leak into Spezial.
    for node in soup.find_all(["h2", "h3", "h4", "img"]):
        if node.name == "h2":
            active_special = normalize(node.get_text(" ", strip=True)).casefold() == "spezial"
            continue
        if node.name in {"h3", "h4"}:
            continue
        if not active_special:
            continue

        name = normalize(node.get("alt") or "")
        if not name or name.casefold() in {"image", "produktbild"}:
            continue

        url = image_source(node)
        if not url:
            continue

        # Keep the first image for each visible product name in page order.
        items.setdefault(name, {"category": CATEGORY, "name": name, "url": url})

    return list(items.values())

def main():
    response = session.get(PAGE, timeout=60)
    response.raise_for_status()
    items = discover_special_images(response.text)

    print(f"Discovered {len(items)} unique products in '{CATEGORY}':")
    for index, item in enumerate(items, start=1):
        print(f"{index:02d}. {item['name']}")

    if len(items) != EXPECTED:
        print(f"ERROR: expected exactly {EXPECTED} entries, found {len(items)}.")
        print("No files were committed. The source may have changed or the category markup may need updating.")
        sys.exit(2)

    destination_dir = Path("shaker") / "spezial"
    destination_dir.mkdir(parents=True, exist_ok=True)

    imported = []
    errors = []
    mapping = {}

    for index, item in enumerate(items, start=1):
        parsed = urlparse(item["url"])
        host = parsed.hostname or ""
        if host != "ochdenis.de" and not host.endswith(".ochdenis.de"):
            errors.append(f"Rejected non-OchDenis host for {item['name']}: {item['url']}")
            continue

        try:
            img_response = session.get(item["url"], timeout=60)
            img_response.raise_for_status()
            if not img_response.headers.get("Content-Type", "").lower().startswith("image/"):
                raise ValueError("URL did not return an image content type")

            with Image.open(BytesIO(img_response.content)) as image:
                image.verify()
                fmt = (image.format or "").upper()

            extension = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg"}.get(fmt)
            if not extension:
                raise ValueError(f"unsupported image format: {fmt}")

            filename = f"Spezial_{index:02d}_{slug(item['name'])}{extension}"
            target = destination_dir / filename
            target.write_bytes(img_response.content)

            relative_path = target.as_posix()
            cdn_path = quote(relative_path, safe="/")
            cdn_url = f"https://cdn.jsdelivr.net/gh/{REPO}@main/{cdn_path}"
            mapping[f"Shaker|Spezial|{item['name']}"] = cdn_url
            imported.append({
                "category": CATEGORY,
                "name": item["name"],
                "path": relative_path,
                "url": cdn_url,
                "source": item["url"],
            })
            print(f"OK {filename}")
        except Exception as exc:
            errors.append(f"{item['name']}: {exc}")

    if errors:
        print("ERROR: image validation/download failed:")
        for error in errors:
            print(f" - {error}")
        sys.exit(3)

    if len(imported) != EXPECTED or len(mapping) != EXPECTED:
        print(f"ERROR: expected {EXPECTED} images and mappings, got {len(imported)} / {len(mapping)}.")
        sys.exit(4)

    # Export an exact manifest so the same names and URLs can be transferred to SCNX.
    (destination_dir / "image-url-map.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    (destination_dir / "catalog.json").write_text(
        json.dumps(imported, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )

    Path("/tmp/special-shaker-summary.md").write_text(
        "# OchDenis Spezial shaker import\n\n"
        f"Successfully downloaded and verified **{len(imported)}** first product images.\n\n"
        + "\n".join(f"- {item['name']}" for item in imported),
        encoding="utf-8",
    )
    print(f"SUCCESS: {len(imported)} Spezial images and mappings ready for commit.")

if __name__ == "__main__":
    main()
