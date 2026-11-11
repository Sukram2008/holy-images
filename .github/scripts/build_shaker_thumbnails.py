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
        # A previously generated thumbnail is already square and has a
        # transparent corner. Keep it byte-for-byte to prevent repeated
        # runs from shrinking the product again.
        corners = (
            image.getpixel((0, 0))[3],
            image.getpixel((SIZE - 1, 0))[3],
            image.getpixel((0, SIZE - 1))[3],
            image.getpixel((SIZE - 1, SIZE - 1))[3],
        ) if image.size == (SIZE, SIZE) else ()
        if image.size == (SIZE, SIZE) and all(alpha == 0 for alpha in corners):
            return data
        image.thumbnail((SIZE - 2 * INSET, SIZE - 2 * INSET), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((SIZE - image.width) // 2, (SIZE - image.height) // 2))
        output = BytesIO()
        canvas.save(output, "WEBP", lossless=True, method=6)
        return output.getvalue()


def render_discord_safe(data: bytes) -> bytes:
    """Scale a complete square preview down to leave room for Discord's crop."""
    with Image.open(BytesIO(data)) as source:
        image = source.convert("RGBA")
        if image.size != (SIZE, SIZE):
            normalized = render(data)
            with Image.open(BytesIO(normalized)) as fitted:
                image = fitted.convert("RGBA")
        scaled_size = int(SIZE * 0.65)
        image = image.resize((scaled_size, scaled_size), Image.Resampling.LANCZOS)
        canvas = Image.new("RGBA", (SIZE, SIZE), (0, 0, 0, 0))
        canvas.alpha_composite(image, ((SIZE - scaled_size) // 2, (SIZE - scaled_size) // 2))
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
        path for path in ALIAS_SOURCE_DIR.iterdir()
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
            # Compact s/ aliases are the paths already used by the HOLY
            # ranking. Replace those aliases with thumbnail bytes while
            # keeping the full-resolution originals untouched in shaker/.
            if base_dir == ALIAS_SOURCE_DIR:
                safe_rendered = render_discord_safe(source.read_bytes())
                safe_target = ALIAS_SOURCE_DIR / "v2" / source.name
                safe_thumb_target = OUTPUT_DIR / ALIAS_SOURCE_DIR.name / "v2" / source.name
                safe_target.parent.mkdir(parents=True, exist_ok=True)
                safe_thumb_target.parent.mkdir(parents=True, exist_ok=True)
                safe_target.write_bytes(safe_rendered)
                safe_thumb_target.write_bytes(safe_rendered)
                print(f"OK {source} -> {safe_target} (Discord-safe 65%)")
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
