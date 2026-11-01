#!/usr/bin/env python3
"""Import all first product images from the OchDenis XL shaker category."""
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
CATEGORY = "XL"
EXPECTED = 11
REPO = "Sukram2008/holy-images"

session = requests.Session()
session.headers.update({
    "User-Agent": "Mozilla/5.0 (compatible; HOLY-XL-Shaker-Importer/1.0)",
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

def discover_xl_images(html: str):
    soup = BeautifulSoup(html, "html.parser")
    active_xl = False
    items = OrderedDict()

    # Reset at every category heading; only images under the exact XL section
    # are accepted. No images from adjacent categories can leak into XL.
    for node in soup.find_all(["h2", "h3", "h4", "img"]):
        if node.name == "h2":
            active_xl = normalize(node.get_text(" ", strip=True)).casefold() == CATEGORY.casefold()
            continue
        if node.name in {"h3", "h4"} or not active_xl:
            continue

        name = normalize(node.get("alt") or "")
        if not name or name.casefold() in {"image", "produktbild"}:
            continue
        url = image_source(node)
        if url:
            items.setdefault(name, {"category": CATEGORY, "name": name, "url": url})
    return list(items.values())

def main():
    response = session.get(PAGE, timeout=60)
    response.raise_for_status()
    items = discover_xl_images(response.text)

    print(f"Discovered {len(items)} unique products in '{CATEGORY}':")
    for i, item in enumerate(items, start=1):
        print(f"{i:02d}. {item['name']}")

    if len(items) != EXPECTED:
        print(f"ERROR: expected exactly {EXPECTED} XL products, found {len(items)}.")
        print("No commit will be made. Check the current OchDenis category before importing.")
        sys.exit(2)

    original_dir = Path("shaker") / "xl"
    alias_dir = Path("s")
    original_dir.mkdir(parents=True, exist_ok=True)
    alias_dir.mkdir(parents=True, exist_ok=True)

    imported = []
    mapping = {}
    errors = []
    for i, item in enumerate(items, start=1):
        host = urlparse(item["url"]).hostname or ""
        if host != "ochdenis.de" and not host.endswith(".ochdenis.de"):
            errors.append(f"Rejected non-OchDenis image host for {item['name']}: {item['url']}")
            continue

        try:
            r = session.get(item["url"], timeout=60)
            r.raise_for_status()
            if not r.headers.get("Content-Type", "").lower().startswith("image/"):
                raise ValueError("URL did not return image content")

            with Image.open(BytesIO(r.content)) as image:
                image.verify()
                fmt = (image.format or "").upper()
            ext = {"WEBP": ".webp", "PNG": ".png", "JPEG": ".jpg"}.get(fmt)
            if not ext:
                raise ValueError(f"Unsupported image format: {fmt}")

            original_name = f"XL_{i:02d}_{slug(item['name'])}{ext}"
            original_path = original_dir / original_name
            alias_path = alias_dir / f"x{i:02d}{ext}"
            original_path.write_bytes(r.content)
            alias_path.write_bytes(r.content)

            cdn_url = f"https://cdn.jsdelivr.net/gh/{REPO}@main/{alias_path.as_posix()}"
            mapping[f"Shaker|XL|{i-1}"] = cdn_url
            imported.append({
                "category": CATEGORY,
                "name": item["name"],
                "path": original_path.as_posix(),
                "cdnPath": alias_path.as_posix(),
                "url": cdn_url,
                "source": item["url"],
            })
            print(f"OK {original_path} -> {alias_path}")
        except Exception as exc:
            errors.append(f"{item['name']}: {exc}")

    if errors:
        print("ERROR: image validation/download failed:")
        for error in errors:
            print(f" - {error}")
        sys.exit(3)
    if len(imported) != EXPECTED or len(mapping) != EXPECTED:
        print(f"ERROR: expected {EXPECTED} image/mapping pairs, got {len(imported)}/{len(mapping)}.")
        sys.exit(4)

    (original_dir / "catalog.json").write_text(
        json.dumps(imported, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    (original_dir / "image-url-map.json").write_text(
        json.dumps(mapping, ensure_ascii=False, indent=2) + "\n", encoding="utf-8"
    )
    Path("/tmp/xl-shaker-summary.md").write_text(
        "# OchDenis XL shaker import\n\n"
        f"Successfully downloaded and verified **{len(imported)}** XL shaker images.\n\n"
        + "\n".join(f"- {item['name']}" for item in imported),
        encoding="utf-8",
    )
    print(f"SUCCESS: {len(imported)} XL images and compact CDN aliases ready for commit.")

if __name__ == "__main__":
    main()
