#!/usr/bin/env python3
"""Generate controlled standalone SVG digital-export PNG samples.

This pipeline creates self-authored SVG source files from local Jinja templates
and local wordlists, then rasterizes them with Playwright Chromium. It does not
call any LLM, image generation model, online API, remote asset, or raster input.
"""

from __future__ import annotations

import argparse
import importlib.metadata
import json
import random
import re
import shutil
import sys
from pathlib import Path
from typing import Any, Callable

from jinja2 import Environment, FileSystemLoader, select_autoescape

from generate_non_ai_exports import (
    CANVAS_CHOICES,
    LOCAL_SAFE_FONTS,
    VISUAL_STYLES,
    WORDLIST_PATH,
    Canvas,
    choose,
    decoded_pixel_hash,
    ensure_empty_or_create,
    number_choice,
    phrase,
    sentence,
    sha256_file,
    sha256_text,
)


SCRIPT_DIR = Path(__file__).resolve().parent
SVG_TEMPLATE_DIR = SCRIPT_DIR / "svg_templates"

SVG_TEMPLATE_ORDER = [
    "svg_infographic_card",
    "svg_flowchart_diagram",
    "svg_timeline_strip",
    "svg_chart_poster",
    "svg_process_map",
    "svg_geometric_notice",
    "svg_data_badge_sheet",
    "svg_route_or_network_map",
]

SVG_TEMPLATE_FILES = {
    "svg_infographic_card": "infographic_card.svg.j2",
    "svg_flowchart_diagram": "flowchart_diagram.svg.j2",
    "svg_timeline_strip": "timeline_strip.svg.j2",
    "svg_chart_poster": "chart_poster.svg.j2",
    "svg_process_map": "process_map.svg.j2",
    "svg_geometric_notice": "geometric_notice.svg.j2",
    "svg_data_badge_sheet": "data_badge_sheet.svg.j2",
    "svg_route_or_network_map": "route_or_network_map.svg.j2",
}

DISALLOWED_SVG_PATTERNS = [
    re.compile(pattern, re.IGNORECASE)
    for pattern in [
        r"<\s*image\b",
        r"<\s*script\b",
        r"href\s*=\s*['\"]\s*https?://",
        r"xlink:href\s*=\s*['\"]\s*https?://",
        r"https://",
        r"data:image",
    ]
]


def parse_canvas(value: str) -> Canvas:
    match = re.fullmatch(r"(\d+)x(\d+)", value.strip().lower())
    if not match:
        raise argparse.ArgumentTypeError("canvas size must use WIDTHxHEIGHT, e.g. 1024x1024")
    width, height = int(match.group(1)), int(match.group(2))
    if (width, height) not in CANVAS_CHOICES:
        choices = ", ".join(f"{w}x{h}" for w, h in CANVAS_CHOICES)
        raise argparse.ArgumentTypeError(f"canvas must be one of: {choices}")
    return Canvas(width=width, height=height)


def load_wordlists() -> dict[str, Any]:
    with WORDLIST_PATH.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def create_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(SVG_TEMPLATE_DIR)),
        autoescape=select_autoescape(enabled_extensions=("svg", "xml", "j2"), default=True),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def get_playwright_version() -> str:
    try:
        return importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def canvas_for_sample(rng: random.Random, fixed_canvas: Canvas | None) -> Canvas:
    if fixed_canvas:
        return fixed_canvas
    width, height = choose(rng, CANVAS_CHOICES)
    return Canvas(width=width, height=height)


def make_code(rng: random.Random, words: dict[str, Any]) -> str:
    prefix = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3))
    return f"{prefix}-{number_choice(rng, words, 'code_blocks')}-{number_choice(rng, words, 'code_pairs')}"


def fit_text(text: str, max_chars: int) -> str:
    return text if len(text) <= max_chars else text[: max_chars - 1].rstrip() + "."


def pct_x(canvas: Canvas, value: float) -> int:
    return round(canvas.width * value)


def pct_y(canvas: Canvas, value: float) -> int:
    return round(canvas.height * value)


def make_layout_id(template_family: str, style_id: str, canvas: Canvas, counts: dict[str, int]) -> str:
    return (
        f"{template_family}__{style_id}__{canvas.width}x{canvas.height}"
        f"__n{counts['nodes']}_c{counts['cards']}_b{counts['bars']}_p{counts['paths']}"
    )


def base_context(
    rng: random.Random,
    words: dict[str, Any],
    canvas: Canvas,
    style: dict[str, Any],
    template_family: str,
) -> dict[str, Any]:
    font = choose(rng, LOCAL_SAFE_FONTS)
    compact = canvas.width <= 760 or canvas.height <= 760
    margin = rng.choice([36, 44, 52, 60]) if not compact else rng.choice([24, 28, 32])
    title_size = rng.randint(38, 54) if compact else rng.randint(54, 84)
    body_size = rng.randint(16, 20) if compact else rng.randint(18, 24)
    counts = {
        "nodes": rng.randint(4, 8),
        "cards": rng.randint(3, 7),
        "bars": rng.randint(4, 8),
        "paths": rng.randint(2, 5),
    }
    palette = dict(style)
    return {
        "canvas": {"width": canvas.width, "height": canvas.height},
        "palette": palette,
        "style_id": style["style_id"],
        "template_family": template_family,
        "layout": {"margin": margin},
        "layout_counts": counts,
        "layout_id": make_layout_id(template_family, style["style_id"], canvas, counts),
        "typography": {
            "title_size": title_size,
            "body_size": body_size,
            "small_size": max(12, body_size - 4),
            "font_family_id": font["id"],
            "font_family_css": font["css"],
        },
        "org": choose(rng, words["organizations"]),
        "department": choose(rng, words["departments"]),
        "city": choose(rng, words["cities"]),
        "month": choose(rng, words["months"]),
        "day": number_choice(rng, words, "days"),
        "year": number_choice(rng, words, "years"),
        "code": make_code(rng, words),
        "title": phrase(rng, words, 3, 5),
        "subtitle": sentence(rng, words, 8, 12),
    }


def make_cards(rng: random.Random, words: dict[str, Any], canvas: Canvas, count: int) -> list[dict[str, Any]]:
    columns = 2 if canvas.width >= canvas.height else 1
    margin_x = pct_x(canvas, 0.08)
    start_y = pct_y(canvas, 0.28)
    gap = pct_x(canvas, 0.035)
    card_w = (canvas.width - margin_x * 2 - gap * (columns - 1)) // columns
    card_h = max(92, round(canvas.height * 0.12))
    cards = []
    for idx in range(count):
        col = idx % columns
        row = idx // columns
        x = margin_x + col * (card_w + gap)
        y = start_y + row * (card_h + round(card_h * 0.22))
        cards.append(
            {
                "x": x,
                "y": y,
                "w": card_w,
                "h": card_h,
                "num": str(idx + 1),
                "title": phrase(rng, words, 2, 4),
                "text": fit_text(sentence(rng, words, 6, 10), 74),
                "value": number_choice(rng, words, "percentages"),
            }
        )
    return cards


def make_flow_nodes(rng: random.Random, words: dict[str, Any], canvas: Canvas, count: int) -> list[dict[str, Any]]:
    horizontal = canvas.width >= canvas.height
    nodes = []
    for idx in range(count):
        if horizontal:
            x = round(canvas.width * (0.12 + idx * (0.76 / max(1, count - 1))))
            y = round(canvas.height * (0.48 + (0.10 if idx % 2 else -0.08)))
        else:
            x = round(canvas.width * (0.48 + (0.12 if idx % 2 else -0.12)))
            y = round(canvas.height * (0.18 + idx * (0.68 / max(1, count - 1))))
        nodes.append(
            {
                "x": x,
                "y": y,
                "r": round(min(canvas.width, canvas.height) * 0.055),
                "title": phrase(rng, words, 2, 3),
                "label": fit_text(sentence(rng, words, 4, 7), 48),
            }
        )
    return nodes


def make_edges(nodes: list[dict[str, Any]]) -> list[dict[str, int]]:
    return [
        {"x1": nodes[idx]["x"], "y1": nodes[idx]["y"], "x2": nodes[idx + 1]["x"], "y2": nodes[idx + 1]["y"]}
        for idx in range(len(nodes) - 1)
    ]


def make_bars(rng: random.Random, words: dict[str, Any], canvas: Canvas, count: int) -> list[dict[str, Any]]:
    left = pct_x(canvas, 0.12)
    bottom = pct_y(canvas, 0.78)
    chart_h = pct_y(canvas, 0.42)
    gap = max(12, pct_x(canvas, 0.018))
    bar_w = max(28, (canvas.width - left * 2 - gap * (count - 1)) // count)
    bars = []
    for idx in range(count):
        value = int(number_choice(rng, words, "chart_values"))
        h = max(24, round(chart_h * value / 100))
        bars.append(
            {
                "x": left + idx * (bar_w + gap),
                "y": bottom - h,
                "w": bar_w,
                "h": h,
                "label": choose(rng, words["metrics"]).split()[0],
                "value": str(value),
            }
        )
    return bars


def context_infographic(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    ctx["cards"] = make_cards(rng, words, canvas, ctx["layout_counts"]["cards"])
    return ctx


def context_flowchart(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    nodes = make_flow_nodes(rng, words, canvas, ctx["layout_counts"]["nodes"])
    ctx["nodes"] = nodes
    ctx["edges"] = make_edges(nodes)
    return ctx


def context_timeline(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    count = ctx["layout_counts"]["nodes"]
    axis_y = pct_y(canvas, 0.55)
    start_x = pct_x(canvas, 0.12)
    end_x = pct_x(canvas, 0.88)
    items = []
    for idx in range(count):
        x = round(start_x + idx * ((end_x - start_x) / max(1, count - 1)))
        items.append(
            {
                "x": x,
                "y": axis_y,
                "month": choose(rng, words["months"])[:3],
                "title": phrase(rng, words, 2, 3),
                "text": fit_text(sentence(rng, words, 5, 8), 54),
                "up": idx % 2 == 0,
            }
        )
    ctx["items"] = items
    ctx["axis"] = {"x1": start_x, "x2": end_x, "y": axis_y}
    return ctx


def context_chart_poster(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    ctx["bars"] = make_bars(rng, words, canvas, ctx["layout_counts"]["bars"])
    ctx["callouts"] = [
        {"label": choose(rng, words["metrics"]), "value": number_choice(rng, words, "percentages")}
        for _ in range(3)
    ]
    return ctx


def context_process_map(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    nodes = make_flow_nodes(rng, words, canvas, ctx["layout_counts"]["nodes"])
    ctx["nodes"] = nodes
    ctx["edges"] = make_edges(nodes)
    ctx["lanes"] = [
        {"y": pct_y(canvas, 0.24 + idx * 0.18), "label": choose(rng, words["departments"])}
        for idx in range(4)
    ]
    return ctx


def context_geometric_notice(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    shapes = []
    for idx in range(ctx["layout_counts"]["cards"] + 5):
        size = round(min(canvas.width, canvas.height) * rng.choice([0.055, 0.075, 0.095]))
        shapes.append(
            {
                "x": rng.randint(0, max(1, canvas.width - size)),
                "y": rng.randint(0, max(1, canvas.height - size)),
                "size": size,
                "rotate": rng.choice([0, 15, 30, 45]),
                "shape": rng.choice(["rect", "circle", "diamond"]),
            }
        )
    ctx["shapes"] = shapes
    ctx["notice_lines"] = [sentence(rng, words, 4, 7) for _ in range(3)]
    return ctx


def context_data_badges(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    columns = 3 if canvas.width >= 1000 else 2
    rows = 3
    margin_x = pct_x(canvas, 0.08)
    start_y = pct_y(canvas, 0.32)
    gap = pct_x(canvas, 0.025)
    badge_w = (canvas.width - margin_x * 2 - gap * (columns - 1)) // columns
    badge_h = max(110, round(canvas.height * 0.13))
    badges = []
    for idx in range(columns * rows):
        col = idx % columns
        row = idx // columns
        badges.append(
            {
                "x": margin_x + col * (badge_w + gap),
                "y": start_y + row * (badge_h + gap),
                "w": badge_w,
                "h": badge_h,
                "metric": choose(rng, words["metrics"]),
                "value": number_choice(rng, words, "counts"),
                "status": choose(rng, words["status"]),
            }
        )
    ctx["badges"] = badges
    return ctx


def context_route_map(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any], canvas: Canvas) -> dict[str, Any]:
    count = ctx["layout_counts"]["nodes"] + 2
    nodes = []
    for idx in range(count):
        nodes.append(
            {
                "x": rng.randint(pct_x(canvas, 0.12), pct_x(canvas, 0.88)),
                "y": rng.randint(pct_y(canvas, 0.25), pct_y(canvas, 0.82)),
                "r": rng.choice([9, 11, 13, 15]),
                "label": choose(rng, words["cities"]),
            }
        )
    nodes = sorted(nodes, key=lambda n: (n["x"], n["y"]))
    ctx["nodes"] = nodes
    ctx["edges"] = make_edges(nodes)
    return ctx


CONTEXT_BUILDERS: dict[str, Callable[[random.Random, dict[str, Any], dict[str, Any], Canvas], dict[str, Any]]] = {
    "svg_infographic_card": context_infographic,
    "svg_flowchart_diagram": context_flowchart,
    "svg_timeline_strip": context_timeline,
    "svg_chart_poster": context_chart_poster,
    "svg_process_map": context_process_map,
    "svg_geometric_notice": context_geometric_notice,
    "svg_data_badge_sheet": context_data_badges,
    "svg_route_or_network_map": context_route_map,
}


def validate_svg_source(svg: str, sample_id: str) -> None:
    for pattern in DISALLOWED_SVG_PATTERNS:
        if pattern.search(svg):
            raise ValueError(f"{sample_id} SVG contains disallowed pattern: {pattern.pattern}")


def render_svg_sources(
    count: int,
    base_seed: int,
    fixed_canvas: Canvas | None,
    output_dir: Path,
    wordlists: dict[str, Any],
) -> list[dict[str, Any]]:
    env = create_environment()
    svg_dir = output_dir / "svg"
    svg_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for index in range(count):
        sample_id = f"sample_{index + 1:06d}"
        random_seed = base_seed + index
        rng = random.Random(random_seed)
        canvas = canvas_for_sample(rng, fixed_canvas)
        template_family = SVG_TEMPLATE_ORDER[index % len(SVG_TEMPLATE_ORDER)]
        style = VISUAL_STYLES[(index + rng.randrange(len(VISUAL_STYLES))) % len(VISUAL_STYLES)]
        ctx = base_context(rng, wordlists, canvas, style, template_family)
        ctx = CONTEXT_BUILDERS[template_family](rng, wordlists, ctx, canvas)
        template = env.get_template(SVG_TEMPLATE_FILES[template_family])
        svg = template.render(**ctx)
        validate_svg_source(svg, sample_id)
        svg_path = svg_dir / f"{sample_id}.svg"
        svg_path.write_text(svg, encoding="utf-8")
        source_hash = sha256_text(svg)
        records.append(
            {
                "sample_id": sample_id,
                "source_type": "svg",
                "source_path": svg_path,
                "source_asset_hash": source_hash,
                "parent_asset_hashes": [source_hash],
                "template_family": template_family,
                "style_id": style["style_id"],
                "layout_id": ctx["layout_id"],
                "random_seed": random_seed,
                "canvas_size": {"width": canvas.width, "height": canvas.height},
                "font_family_id": ctx["typography"]["font_family_id"],
                "layout_counts": ctx["layout_counts"],
                "output_path": None,
                "output_asset_hash": None,
                "decoded_pixel_hash": None,
            }
        )
    return records


def rasterize_svg_batch(records: list[dict[str, Any]], output_dir: Path, timeout_ms: int) -> tuple[str, str]:
    try:
        from playwright.sync_api import sync_playwright
    except ModuleNotFoundError as exc:
        raise RuntimeError(
            "Playwright is not installed. Run: python3 -m pip install -r "
            "pilot_export_workflow/requirements.txt && python3 -m playwright install chromium"
        ) from exc

    image_dir = output_dir / "images"
    image_dir.mkdir(parents=True, exist_ok=True)
    playwright_version = get_playwright_version()

    with sync_playwright() as p:
        browser = p.chromium.launch(headless=True)
        chromium_version = browser.version
        page = browser.new_page()
        for record in records:
            canvas = record["canvas_size"]
            page.set_viewport_size({"width": canvas["width"], "height": canvas["height"]})
            page.goto(record["source_path"].resolve().as_uri(), wait_until="load", timeout=timeout_ms)
            output_path = image_dir / f"{record['sample_id']}.png"
            page.screenshot(path=str(output_path), type="png", full_page=False, timeout=timeout_ms)
            record["output_path"] = output_path
            record["output_asset_hash"] = sha256_file(output_path)
            record["decoded_pixel_hash"] = decoded_pixel_hash(output_path)
        browser.close()

    return playwright_version, chromium_version


def relative_string(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def manifest_from_record(record: dict[str, Any], output_dir: Path, renderer_version: str, wordlist_version: str) -> dict[str, Any]:
    return {
        "schema_version": "provenance_chain_v1",
        "sample_id": record["sample_id"],
        "source_type": "svg",
        "source_path": relative_string(record["source_path"], output_dir),
        "source_asset_hash": record["source_asset_hash"],
        "parent_asset_hashes": record["parent_asset_hashes"],
        "template_family": record["template_family"],
        "style_id": record["style_id"],
        "layout_id": record["layout_id"],
        "random_seed": record["random_seed"],
        "renderer": "playwright_chromium_svg_rasterizer",
        "renderer_version": renderer_version,
        "canvas_size": record["canvas_size"],
        "output_format": "png",
        "output_path": relative_string(record["output_path"], output_dir),
        "output_asset_hash": record["output_asset_hash"],
        "decoded_pixel_hash": record["decoded_pixel_hash"],
        "font_family_id": record["font_family_id"],
        "layout_counts": record["layout_counts"],
        "wordlist_version": wordlist_version,
        "label_status": "controlled_complete",
        "initial_digital_event": "digital_to_digital_file_export",
        "last_acquisition_event": "none",
        "chain_events": [],
        "ai_inference_used": False,
        "external_assets_used": False,
    }


def write_manifests(records: list[dict[str, Any]], output_dir: Path, renderer_version: str, wordlist_version: str) -> None:
    manifest_dir = output_dir / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    with (manifest_dir / "samples.jsonl").open("w", encoding="utf-8") as handle:
        for record in records:
            manifest = manifest_from_record(record, output_dir, renderer_version, wordlist_version)
            (manifest_dir / f"{record['sample_id']}.json").write_text(
                json.dumps(manifest, indent=2, sort_keys=True) + "\n",
                encoding="utf-8",
            )
            handle.write(json.dumps(manifest, sort_keys=True) + "\n")


def write_summary(records: list[dict[str, Any]], output_dir: Path, renderer_version: str) -> None:
    qa_dir = output_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    by_template = {template_family: 0 for template_family in SVG_TEMPLATE_ORDER}
    by_style = {style["style_id"]: 0 for style in VISUAL_STYLES}
    by_canvas = {f"{w}x{h}": 0 for w, h in CANVAS_CHOICES}
    for record in records:
        by_template[record["template_family"]] += 1
        by_style[record["style_id"]] += 1
        canvas = record["canvas_size"]
        by_canvas[f"{canvas['width']}x{canvas['height']}"] += 1
    summary = {
        "sample_count": len(records),
        "source_type": "svg",
        "png_count": len(records),
        "templates": by_template,
        "styles": by_style,
        "canvas_sizes": by_canvas,
        "renderer": "playwright_chromium_svg_rasterizer",
        "renderer_version": renderer_version,
        "initial_digital_event": "digital_to_digital_file_export",
        "chain_events_for_png_master": [],
        "ai_inference_used": False,
        "external_assets_used": False,
        "missing_images": [record["sample_id"] for record in records if record["output_path"] is None],
    }
    (qa_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate standalone SVG digital-export PNG samples.")
    parser.add_argument("--count", type=int, default=1000)
    parser.add_argument("--seed", type=int, default=20260615)
    parser.add_argument("--canvas", type=parse_canvas, default=None)
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "generated_svg_v1_1000",
        help="Output directory for SVG, PNG, manifests, and QA.",
    )
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument("--timeout-ms", type=int, default=30000)
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error("--count must be greater than zero")

    output_dir = args.output_dir.resolve()
    ensure_empty_or_create(output_dir, args.overwrite)
    for child in ["svg", "images", "manifests", "qa"]:
        (output_dir / child).mkdir(parents=True, exist_ok=True)

    wordlists = load_wordlists()
    records = render_svg_sources(args.count, args.seed, args.canvas, output_dir, wordlists)
    playwright_version, chromium_version = rasterize_svg_batch(records, output_dir, args.timeout_ms)
    renderer_version = f"playwright {playwright_version}; chromium {chromium_version}"
    write_manifests(records, output_dir, renderer_version, wordlists.get("version", "unknown"))
    write_summary(records, output_dir, renderer_version)

    print(f"Generated {len(records)} SVG digital-export PNG samples in {output_dir}")
    print(f"Manifest JSONL: {output_dir / 'manifests' / 'samples.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
