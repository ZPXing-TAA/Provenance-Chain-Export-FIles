#!/usr/bin/env python3
"""Create JPEG recompression samples from existing digital-export PNG manifests.

This is the post-export stage:

digital source -> file export/rasterization -> PNG master -> JPEG recompression

The output manifest keeps:

initial_digital_event = digital_to_digital_file_export
chain_events += digital_recompression
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
import shutil
import sys
from pathlib import Path
from typing import Any

from PIL import Image


SCRIPT_DIR = Path(__file__).resolve().parent
DEFAULT_INPUT_MANIFEST = SCRIPT_DIR / "generated_pilot_v2_1000" / "manifests" / "samples.jsonl"

SUBSAMPLING_TO_PIL = {
    "4:4:4": 0,
    "4:2:2": 1,
    "4:2:0": 2,
}


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def decoded_pixel_hash(path: Path) -> str:
    with Image.open(path) as image:
        image = image.convert("RGBA")
        payload = image.size[0].to_bytes(4, "big")
        payload += image.size[1].to_bytes(4, "big")
        payload += image.tobytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def ensure_empty_or_create(path: Path, overwrite: bool) -> None:
    if path.exists() and overwrite:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def load_jsonl(path: Path) -> list[dict[str, Any]]:
    rows = []
    with path.open("r", encoding="utf-8") as handle:
        for line_number, line in enumerate(handle, 1):
            line = line.strip()
            if not line:
                continue
            try:
                rows.append(json.loads(line))
            except json.JSONDecodeError as exc:
                raise ValueError(f"invalid JSON on {path}:{line_number}: {exc}") from exc
    return rows


def relative_string(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def resolve_source_dataset_root(input_manifest: Path, explicit_root: Path | None) -> Path:
    if explicit_root is not None:
        return explicit_root.resolve()
    # Expected layout: <dataset>/manifests/samples.jsonl
    if input_manifest.parent.name == "manifests":
        return input_manifest.parent.parent.resolve()
    return input_manifest.parent.resolve()


def next_event_order(chain_events: list[dict[str, Any]]) -> int:
    orders = [event.get("order") for event in chain_events if isinstance(event.get("order"), int)]
    return max(orders, default=0) + 1


def make_recompression_event(
    source_row: dict[str, Any],
    quality: int,
    subsampling: str,
    pillow_version: str,
) -> dict[str, Any]:
    prior_events = source_row.get("chain_events") or []
    return {
        "event_type": "digital_recompression",
        "event_kind": "manipulation_or_processing",
        "order": next_event_order(prior_events),
        "scope": "global",
        "semantic_change_degree": "none",
        "mask_path": None,
        "operation_registry_ref": "pillow_jpeg_recompression",
        "parameters": {
            "codec": "jpeg",
            "quality": quality,
            "subsampling": subsampling,
            "optimize": False,
            "progressive": False,
            "software": "Pillow",
            "software_version": pillow_version,
            "source_output_format": source_row.get("output_format"),
        },
    }


def build_jpeg_manifest(
    source_row: dict[str, Any],
    source_dataset_root: Path,
    output_dir: Path,
    jpeg_path: Path,
    quality: int,
    subsampling: str,
    pillow_version: str,
) -> dict[str, Any]:
    source_chain_events = list(source_row.get("chain_events") or [])
    recompression_event = make_recompression_event(source_row, quality, subsampling, pillow_version)
    source_sample_id = source_row["sample_id"]
    sample_id = f"{source_sample_id}_jpeg_q{quality}_{subsampling.replace(':', '')}"

    source_html_path = source_row.get("html_path")
    html_path = None
    if source_html_path:
        source_html_abs = (source_dataset_root / source_html_path).resolve()
        if source_html_abs.exists():
            html_dir = output_dir / "html"
            html_dir.mkdir(parents=True, exist_ok=True)
            html_copy = html_dir / f"{source_sample_id}.html"
            if not html_copy.exists():
                shutil.copy2(source_html_abs, html_copy)
            html_path = relative_string(html_copy, output_dir)

    return {
        **source_row,
        "sample_id": sample_id,
        "parent_sample_id": source_sample_id,
        "parent_asset_hashes": [source_row["output_asset_hash"]],
        "source_manifest_path": str(source_dataset_root / "manifests" / "samples.jsonl"),
        "source_output_path": source_row.get("output_path"),
        "html_path": html_path if html_path is not None else source_html_path,
        "output_path": relative_string(jpeg_path, output_dir),
        "output_format": "jpeg",
        "output_asset_hash": sha256_file(jpeg_path),
        "decoded_pixel_hash": decoded_pixel_hash(jpeg_path),
        "label_status": source_row.get("label_status", "controlled_complete"),
        "initial_digital_event": "digital_to_digital_file_export",
        "last_acquisition_event": source_row.get("last_acquisition_event", "none"),
        "chain_events": source_chain_events + [recompression_event],
        "jpeg_recompression": {
            "quality": quality,
            "subsampling": subsampling,
            "optimize": False,
            "progressive": False,
            "software": "Pillow",
            "software_version": pillow_version,
        },
    }


def recompress_rows(
    rows: list[dict[str, Any]],
    source_dataset_root: Path,
    output_dir: Path,
    quality: int,
    subsampling: str,
    limit: int | None,
) -> list[dict[str, Any]]:
    image_dir = output_dir / "images"
    manifest_dir = output_dir / "manifests"
    image_dir.mkdir(parents=True, exist_ok=True)
    manifest_dir.mkdir(parents=True, exist_ok=True)
    pillow_version = importlib.metadata.version("pillow")

    eligible_rows = []
    for row in rows:
        if row.get("output_format") != "png":
            continue
        if row.get("initial_digital_event") != "digital_to_digital_file_export":
            raise ValueError(
                f"{row.get('sample_id')} has initial_digital_event={row.get('initial_digital_event')}; "
                "JPEG recompression stage expects digital_to_digital_file_export parents."
            )
        if not row.get("output_path") or not row.get("output_asset_hash"):
            raise ValueError(f"{row.get('sample_id')} is missing output_path or output_asset_hash")
        eligible_rows.append(row)
    if limit is not None:
        eligible_rows = eligible_rows[:limit]

    manifests = []
    pil_subsampling = SUBSAMPLING_TO_PIL[subsampling]
    for row in eligible_rows:
        source_image_path = (source_dataset_root / row["output_path"]).resolve()
        if not source_image_path.exists():
            raise FileNotFoundError(f"source image not found for {row['sample_id']}: {source_image_path}")
        sample_id = f"{row['sample_id']}_jpeg_q{quality}_{subsampling.replace(':', '')}"
        jpeg_path = image_dir / f"{sample_id}.jpg"
        with Image.open(source_image_path) as image:
            image.convert("RGB").save(
                jpeg_path,
                "JPEG",
                quality=quality,
                subsampling=pil_subsampling,
                optimize=False,
                progressive=False,
            )
        manifest = build_jpeg_manifest(
            row,
            source_dataset_root,
            output_dir,
            jpeg_path,
            quality,
            subsampling,
            pillow_version,
        )
        manifests.append(manifest)
        (manifest_dir / f"{sample_id}.json").write_text(
            json.dumps(manifest, indent=2, sort_keys=True) + "\n",
            encoding="utf-8",
        )
    return manifests


def write_outputs(manifests: list[dict[str, Any]], output_dir: Path, quality: int, subsampling: str) -> None:
    manifest_dir = output_dir / "manifests"
    qa_dir = output_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)

    with (manifest_dir / "samples.jsonl").open("w", encoding="utf-8") as handle:
        for manifest in manifests:
            handle.write(json.dumps(manifest, sort_keys=True) + "\n")

    family_counts: dict[str, int] = {}
    style_counts: dict[str, int] = {}
    for manifest in manifests:
        family_counts[manifest.get("template_family", "unknown")] = family_counts.get(manifest.get("template_family", "unknown"), 0) + 1
        style_counts[manifest.get("style_id", "unknown")] = style_counts.get(manifest.get("style_id", "unknown"), 0) + 1

    summary = {
        "sample_count": len(manifests),
        "output_format": "jpeg",
        "quality": quality,
        "subsampling": subsampling,
        "initial_digital_event": "digital_to_digital_file_export",
        "appended_chain_event": "digital_recompression",
        "templates": dict(sorted(family_counts.items())),
        "styles": dict(sorted(style_counts.items())),
        "ai_inference_used": False,
        "external_assets_used": False,
    }
    (qa_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Create JPEG recompression variants from digital-export PNG manifests.")
    parser.add_argument("--input-manifest", type=Path, default=DEFAULT_INPUT_MANIFEST)
    parser.add_argument("--source-root", type=Path, default=None, help="Dataset root for paths in input manifest.")
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "generated_pilot_v2_1000_jpeg_q90",
        help="Output directory for JPEG images and manifests.",
    )
    parser.add_argument("--quality", type=int, default=90)
    parser.add_argument("--subsampling", choices=sorted(SUBSAMPLING_TO_PIL), default="4:2:0")
    parser.add_argument("--limit", type=int, default=None)
    parser.add_argument("--overwrite", action="store_true")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if not (1 <= args.quality <= 100):
        parser.error("--quality must be between 1 and 100")
    if args.limit is not None and args.limit <= 0:
        parser.error("--limit must be greater than zero")

    input_manifest = args.input_manifest.resolve()
    source_dataset_root = resolve_source_dataset_root(input_manifest, args.source_root)
    output_dir = args.output_dir.resolve()
    ensure_empty_or_create(output_dir, args.overwrite)

    rows = load_jsonl(input_manifest)
    manifests = recompress_rows(
        rows=rows,
        source_dataset_root=source_dataset_root,
        output_dir=output_dir,
        quality=args.quality,
        subsampling=args.subsampling,
        limit=args.limit,
    )
    write_outputs(manifests, output_dir, args.quality, args.subsampling)
    print(f"Generated {len(manifests)} JPEG recompression samples in {output_dir}")
    print(f"Manifest JSONL: {output_dir / 'manifests' / 'samples.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
