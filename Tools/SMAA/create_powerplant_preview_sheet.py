"""Build a reproducible Power Plant section-preview contact sheet.

The gradient statistics are scene-triage aids, not anti-aliasing quality
metrics.  They help identify views containing abundant screen-space edges
before a researcher inspects the actual geometry and defines a camera path.
"""

from __future__ import annotations

import argparse
import csv
import json
import re
from pathlib import Path

import numpy as np
from PIL import Image, ImageDraw, ImageFont


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Create a labeled contact sheet for Power Plant section previews."
    )
    parser.add_argument("preview_dir", type=Path, help="Directory containing secN.png files.")
    parser.add_argument(
        "--cache-manifest", type=Path, required=True, help="Converter cache manifest JSON."
    )
    parser.add_argument("--output", type=Path, required=True, help="Output directory.")
    parser.add_argument("--columns", type=int, default=4)
    parser.add_argument("--tile-width", type=int, default=440)
    return parser.parse_args()


def section_key(path: Path) -> int:
    match = re.fullmatch(r"sec(\d+)", path.stem)
    if match is None:
        raise ValueError(f"Unexpected preview name: {path.name}")
    return int(match.group(1))


def luma_metrics(image: Image.Image) -> dict[str, float]:
    rgb = np.asarray(image.convert("RGB"), dtype=np.float32) / 255.0
    luma = rgb[..., 0] * 0.2126 + rgb[..., 1] * 0.7152 + rgb[..., 2] * 0.0722
    gradient_x = np.zeros_like(luma)
    gradient_y = np.zeros_like(luma)
    gradient_x[:, 1:] = np.abs(luma[:, 1:] - luma[:, :-1])
    gradient_y[1:, :] = np.abs(luma[1:, :] - luma[:-1, :])
    gradient = np.maximum(gradient_x, gradient_y)
    return {
        "mean_luma": float(np.mean(luma)),
        "dark_pixel_ratio": float(np.mean(luma < 0.08)),
        "gradient_mean": float(np.mean(gradient)),
        "edge_ratio_0_06": float(np.mean(gradient >= 0.06)),
        "strong_edge_ratio_0_15": float(np.mean(gradient >= 0.15)),
    }


def main() -> None:
    args = parse_args()
    if args.columns <= 0 or args.tile_width < 160:
        raise ValueError("Invalid contact-sheet layout")
    preview_paths = sorted(args.preview_dir.glob("sec*.png"), key=section_key)
    if not preview_paths:
        raise FileNotFoundError(f"No secN.png files in {args.preview_dir}")

    manifest = json.loads(args.cache_manifest.read_text(encoding="utf-8"))
    cache_by_section = {entry["section"]: entry for entry in manifest["caches"]}
    preview_names = {path.stem for path in preview_paths}
    if preview_names != set(cache_by_section):
        raise RuntimeError(
            "Preview/cache section mismatch: "
            f"preview-only={sorted(preview_names - set(cache_by_section))}, "
            f"cache-only={sorted(set(cache_by_section) - preview_names)}"
        )

    rows: list[dict[str, object]] = []
    images: dict[str, Image.Image] = {}
    expected_size: tuple[int, int] | None = None
    for path in preview_paths:
        image = Image.open(path).convert("RGB")
        if expected_size is None:
            expected_size = image.size
        elif image.size != expected_size:
            raise RuntimeError(f"Resolution mismatch for {path}: {image.size} != {expected_size}")
        images[path.stem] = image
        cache = cache_by_section[path.stem]
        metrics = luma_metrics(image)
        rows.append(
            {
                "section": path.stem,
                "width": image.width,
                "height": image.height,
                "triangles": cache["triangles"],
                "vertices": cache["vertices"],
                **metrics,
            }
        )

    args.output.mkdir(parents=True, exist_ok=True)
    csv_path = args.output / "powerplant_preview_metrics.csv"
    with csv_path.open("w", newline="", encoding="utf-8-sig") as stream:
        writer = csv.DictWriter(stream, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)

    tile_width = args.tile_width
    source_width, source_height = expected_size or (1, 1)
    image_height = round(tile_width * source_height / source_width)
    label_height = 48
    tile_height = image_height + label_height
    row_count = (len(rows) + args.columns - 1) // args.columns
    sheet = Image.new(
        "RGB", (tile_width * args.columns, tile_height * row_count), (20, 23, 27)
    )
    draw = ImageDraw.Draw(sheet)
    font = ImageFont.load_default(size=18)
    small_font = ImageFont.load_default(size=14)
    for index, row in enumerate(rows):
        section = str(row["section"])
        x = (index % args.columns) * tile_width
        y = (index // args.columns) * tile_height
        thumb = images[section].resize((tile_width, image_height), Image.Resampling.LANCZOS)
        sheet.paste(thumb, (x, y + label_height))
        draw.text((x + 8, y + 4), section, font=font, fill=(245, 245, 245))
        draw.text(
            (x + 78, y + 6),
            f"tri {int(row['triangles']):,} | edge {float(row['edge_ratio_0_06']) * 100:.2f}%",
            font=small_font,
            fill=(185, 198, 210),
        )
        draw.rectangle((x, y, x + tile_width - 1, y + tile_height - 1), outline=(65, 72, 82))

    sheet_path = args.output / "powerplant_preview_contact_sheet.png"
    sheet.save(sheet_path, optimize=True)
    ranked = sorted(rows, key=lambda row: float(row["edge_ratio_0_06"]), reverse=True)
    print(f"PASS: {len(rows)} previews, resolution={expected_size}")
    print("Top edge-density screening candidates:")
    for row in ranked[:8]:
        print(
            f"  {row['section']}: edge={float(row['edge_ratio_0_06']) * 100:.3f}%, "
            f"strong={float(row['strong_edge_ratio_0_15']) * 100:.3f}%, "
            f"triangles={int(row['triangles']):,}"
        )
    print(csv_path)
    print(sheet_path)


if __name__ == "__main__":
    main()
