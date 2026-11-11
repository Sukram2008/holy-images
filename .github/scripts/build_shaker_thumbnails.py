#!/usr/bin/env python3
"""Build square, contain-fit WebP thumbnails from every existing shaker image."""
from __future__ import annotations

from io import BytesIO
from pathlib import Path

from PIL import Image, UnidentifiedImageError

SOURCE_DIR = Path("shaker")
OUTPUT_DIR = Path("thumbs")
ALIAS_SOURCE_DIR = Path("s")
SIZE = 512
INSET = 24
EXTENSIONS = {".webp", ".png", ".jpg", ".jpeg"}


def render(data: bytes) -> bytes:
    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGBA")
        image.thumbnail((SIZE - 2 * INSET, SIZE - 2 * INSET), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((SIZE - image.width) // 2, (SIZE - image.height) // 2))
        output = BytesIO()
        canvas.save(output, "WEBP", lossless=True, method=6)
        return output.getvalue()


def main() -> None:
    sources = sorted(
        path for path in SOURCE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in EXTENSIONS
    )
    if not sources:
        raise SystemExit("No shaker source images found; refusing to create an empty thumbnail set.")

    aliases = sorted(
        path for path in ALIAS_SOURCE_DIR.rglob("*")
        if path.is_file() and path.suffix.lower() in EXTENSIONS
    )
    if not aliases:
        raise SystemExit("No compact image aliases found in s/; refusing to leave the Discord thumbnail URLs incomplete.")

    failures: list[str] = []
    for source in sources + aliases:
        base_dir = SOURCE_DIR if SOURCE_DIR in source.parents else ALIAS_SOURCE_DIR
        target = OUTPUT_DIR / base_dir.name / source.relative_to(base_dir).with_suffix(".webp")
        try:
            rendered = render(source.read_bytes())
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_bytes(rendered)
            print(f"OK {source} -> {target}")
        except (OSError, ValueError, UnidentifiedImageError) as exc:
            failures.append(f"{source}: {exc}")

    if failures:
        print("Thumbnail generation failed:")
        for failure in failures:
            print(f" - {failure}")
        raise SystemExit(2)

    print(f"Generated {len(sources)} product-folder thumbnails and {len(aliases)} compact-alias thumbnails.")


if __name__ == "__main__":
    main()
