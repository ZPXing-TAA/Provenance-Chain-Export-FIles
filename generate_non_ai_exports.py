#!/usr/bin/env python3
"""Generate controlled non-AI digital-export image samples.

This tool creates born-digital HTML pages from local Jinja templates and local
wordlists, then rasterizes them with Playwright Chromium. It does not call any
LLM, image generation model, online API, or remote asset.
"""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import io
import json
import math
import random
import re
import shutil
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Callable

import matplotlib

matplotlib.use("Agg")
import matplotlib.pyplot as plt
from jinja2 import Environment, FileSystemLoader, select_autoescape


SCRIPT_DIR = Path(__file__).resolve().parent
TEMPLATE_DIR = SCRIPT_DIR / "templates"
WORDLIST_PATH = SCRIPT_DIR / "wordlists" / "local_wordlists.json"

CANVAS_CHOICES = [
    (1024, 1024),
    (1280, 720),
    (720, 1280),
    (1240, 1754),
]

LOCAL_SAFE_FONTS = [
    {"id": "arial", "css": "Arial, Helvetica, sans-serif"},
    {"id": "georgia", "css": "Georgia, 'Times New Roman', serif"},
    {"id": "times", "css": "'Times New Roman', Times, serif"},
    {"id": "trebuchet", "css": "'Trebuchet MS', Arial, sans-serif"},
    {"id": "verdana", "css": "Verdana, Geneva, sans-serif"},
    {"id": "courier", "css": "'Courier New', Courier, monospace"},
]

VISUAL_STYLES = [
    {
        "style_id": "minimal_white",
        "bg": "#f8fafc",
        "panel": "#ffffff",
        "ink": "#172033",
        "muted": "#647084",
        "accent": "#2f5f8f",
        "accent2": "#8fb3d9",
        "line": "#dce3ec",
        "radius": 6,
        "shadow": "none",
        "contrast": "light",
    },
    {
        "style_id": "corporate_blue_gray",
        "bg": "#eef3f8",
        "panel": "#ffffff",
        "ink": "#152337",
        "muted": "#5f6f83",
        "accent": "#244f78",
        "accent2": "#718faa",
        "line": "#d2dce7",
        "radius": 8,
        "shadow": "0 10px 28px rgba(28, 45, 70, 0.10)",
        "contrast": "light",
    },
    {
        "style_id": "academic_paper",
        "bg": "#f6f2e8",
        "panel": "#fffdf7",
        "ink": "#1e1b16",
        "muted": "#6f6759",
        "accent": "#604b2f",
        "accent2": "#b79d74",
        "line": "#ded4be",
        "radius": 2,
        "shadow": "none",
        "contrast": "paper",
    },
    {
        "style_id": "dark_dashboard",
        "bg": "#0d1424",
        "panel": "#151f33",
        "ink": "#eef4ff",
        "muted": "#99aac3",
        "accent": "#6db7ff",
        "accent2": "#60d0a8",
        "line": "#293850",
        "radius": 8,
        "shadow": "0 12px 34px rgba(0, 0, 0, 0.28)",
        "contrast": "dark",
    },
    {
        "style_id": "bold_poster",
        "bg": "#f8e9d0",
        "panel": "#fffaf0",
        "ink": "#201612",
        "muted": "#725f4a",
        "accent": "#d4472f",
        "accent2": "#ffc857",
        "line": "#ead0a8",
        "radius": 8,
        "shadow": "8px 8px 0 rgba(32, 22, 18, 0.18)",
        "contrast": "poster",
    },
    {
        "style_id": "mobile_app",
        "bg": "#eef7f6",
        "panel": "#ffffff",
        "ink": "#102524",
        "muted": "#637d7a",
        "accent": "#168174",
        "accent2": "#74c9bd",
        "line": "#cfebe7",
        "radius": 16,
        "shadow": "0 12px 30px rgba(15, 84, 77, 0.12)",
        "contrast": "light",
    },
    {
        "style_id": "retro_newspaper",
        "bg": "#efe4cc",
        "panel": "#f8efd9",
        "ink": "#1f1a12",
        "muted": "#6f614a",
        "accent": "#6b2d20",
        "accent2": "#af7d42",
        "line": "#cdbb98",
        "radius": 0,
        "shadow": "none",
        "contrast": "paper",
    },
    {
        "style_id": "government_form",
        "bg": "#eef1f3",
        "panel": "#ffffff",
        "ink": "#17202a",
        "muted": "#596677",
        "accent": "#2c5279",
        "accent2": "#8c9cad",
        "line": "#bfc9d4",
        "radius": 3,
        "shadow": "none",
        "contrast": "form",
    },
]

TEMPLATE_ORDER = [
    "announcement_notice",
    "report_academic_abstract",
    "dashboard_with_charts",
    "table_form_menu",
    "poster_event_card",
    "news_article_page",
    "ecommerce_product_card",
    "mobile_chat_social_card",
    "infographic_timeline_flowchart",
    "education_slide_lecture_page",
]

TEMPLATE_FILES = {
    "announcement_notice": "announcement_page.html.j2",
    "report_academic_abstract": "report_page.html.j2",
    "dashboard_with_charts": "dashboard_with_charts.html.j2",
    "table_form_menu": "table_document_page.html.j2",
    "poster_event_card": "poster_info_card.html.j2",
    "news_article_page": "news_article_page.html.j2",
    "ecommerce_product_card": "ecommerce_product_card.html.j2",
    "mobile_chat_social_card": "mobile_chat_social_card.html.j2",
    "infographic_timeline_flowchart": "infographic_timeline_flowchart.html.j2",
    "education_slide_lecture_page": "education_slide_lecture_page.html.j2",
}


@dataclass(frozen=True)
class Canvas:
    width: int
    height: int


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


def ensure_empty_or_create(path: Path, overwrite: bool) -> None:
    if path.exists() and overwrite:
        shutil.rmtree(path)
    path.mkdir(parents=True, exist_ok=True)


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return "sha256:" + digest.hexdigest()


def sha256_text(text: str) -> str:
    return "sha256:" + hashlib.sha256(text.encode("utf-8")).hexdigest()


def decoded_pixel_hash(path: Path) -> str:
    from PIL import Image

    with Image.open(path) as image:
        image = image.convert("RGBA")
        payload = image.size[0].to_bytes(4, "big")
        payload += image.size[1].to_bytes(4, "big")
        payload += image.tobytes()
    return "sha256:" + hashlib.sha256(payload).hexdigest()


def choose(rng: random.Random, items: list[Any]) -> Any:
    return items[rng.randrange(len(items))]


def number_choice(rng: random.Random, words: dict[str, Any], key: str) -> Any:
    return choose(rng, words["numbers"][key])


def sentence(rng: random.Random, words: dict[str, Any], min_parts: int = 7, max_parts: int = 12) -> str:
    pools = [
        words["adjectives"],
        words["topics"],
        words["verbs"],
        words["nouns"],
        words["departments"],
        words["products"],
    ]
    parts = [str(choose(rng, choose(rng, pools))) for _ in range(rng.randint(min_parts, max_parts))]
    text = " ".join(parts)
    return text[:1].upper() + text[1:] + "."


def phrase(rng: random.Random, words: dict[str, Any], min_words: int = 3, max_words: int = 6) -> str:
    pools = [words["adjectives"], words["topics"], words["nouns"]]
    parts = [str(choose(rng, choose(rng, pools))) for _ in range(rng.randint(min_words, max_words))]
    return " ".join(parts).title()


def make_code(rng: random.Random, words: dict[str, Any]) -> str:
    prefix = "".join(rng.choice("ABCDEFGHJKLMNPQRSTUVWXYZ") for _ in range(3))
    return f"{prefix}-{number_choice(rng, words, 'code_blocks')}-{number_choice(rng, words, 'code_pairs')}"


def clean_svg(svg: str) -> str:
    start = svg.find("<svg")
    if start >= 0:
        svg = svg[start:]
    return re.sub(r"<metadata>.*?</metadata>", "", svg, flags=re.DOTALL)


def icon_svg(shape: str, palette: dict[str, Any], size: int = 72) -> str:
    accent = palette["accent"]
    accent2 = palette["accent2"]
    line = palette["line"]
    if shape == "circle":
        body = f'<circle cx="{size/2}" cy="{size/2}" r="{size*0.32}" fill="{accent}"/><circle cx="{size*0.62}" cy="{size*0.36}" r="{size*0.13}" fill="{accent2}"/>'
    elif shape == "bars":
        body = "".join(
            f'<rect x="{10+i*16}" y="{size-12-h}" width="10" height="{h}" rx="3" fill="{accent if i % 2 else accent2}"/>'
            for i, h in enumerate([24, 42, 31, 50])
        )
    elif shape == "nodes":
        body = f'<path d="M18 22 L54 24 L42 54 L18 22" fill="none" stroke="{accent}" stroke-width="5"/><circle cx="18" cy="22" r="7" fill="{accent2}"/><circle cx="54" cy="24" r="7" fill="{accent}"/><circle cx="42" cy="54" r="7" fill="{accent2}"/>'
    elif shape == "diamond":
        body = f'<path d="M36 8 L64 36 L36 64 L8 36 Z" fill="{accent}"/><path d="M36 20 L52 36 L36 52 L20 36 Z" fill="{accent2}"/>'
    else:
        body = f'<rect x="12" y="12" width="48" height="48" rx="8" fill="{accent}"/><path d="M22 45 L36 24 L52 45 Z" fill="{accent2}"/>'
    return f'<svg class="geo-icon" width="{size}" height="{size}" viewBox="0 0 {size} {size}" xmlns="http://www.w3.org/2000/svg"><rect width="{size}" height="{size}" rx="12" fill="{line}" opacity="0.35"/>{body}</svg>'


def matplotlib_svg(
    rng: random.Random,
    words: dict[str, Any],
    palette: dict[str, Any],
    chart_kind: str,
    labels: list[str],
    width: float,
    height: float,
) -> str:
    matplotlib.rcParams["svg.hashsalt"] = str(rng.random())
    fig, ax = plt.subplots(figsize=(width, height), dpi=100)
    fig.patch.set_facecolor("none")
    ax.set_facecolor("none")

    if chart_kind == "line":
        x_values = list(range(len(labels)))
        values = [int(number_choice(rng, words, "chart_values")) for _ in labels]
        ax.plot(x_values, values, color=palette["accent"], linewidth=3, marker="o", markersize=5)
        ax.fill_between(x_values, values, min(values) - 6, color=palette["accent2"], alpha=0.22)
        ax.set_xticks(x_values)
        ax.set_xticklabels(labels)
    elif chart_kind == "bar":
        values = [int(number_choice(rng, words, "chart_values")) for _ in labels]
        ax.bar(labels, values, color=[palette["accent"], palette["accent2"]] * math.ceil(len(labels) / 2))
    elif chart_kind == "donut":
        values = [int(number_choice(rng, words, "chart_values")) for _ in labels[:4]]
        ax.pie(
            values,
            labels=labels[:4],
            colors=[palette["accent"], palette["accent2"], "#9aa6b2", "#c8d0d8"],
            startangle=90,
            wedgeprops={"width": 0.42},
        )
    else:
        raise ValueError(f"unknown chart kind: {chart_kind}")

    if chart_kind != "donut":
        ax.grid(True, axis="y", color=palette["line"], linewidth=0.8)
        ax.spines["top"].set_visible(False)
        ax.spines["right"].set_visible(False)
        ax.spines["left"].set_color(palette["line"])
        ax.spines["bottom"].set_color(palette["line"])
        ax.tick_params(colors=palette["muted"], labelsize=9)
    else:
        ax.tick_params(colors=palette["muted"], labelsize=9)

    fig.tight_layout(pad=0.3)
    buffer = io.StringIO()
    fig.savefig(buffer, format="svg", transparent=True, metadata={"Date": None})
    plt.close(fig)
    return clean_svg(buffer.getvalue())


def canvas_for_sample(rng: random.Random, fixed_canvas: Canvas | None) -> Canvas:
    if fixed_canvas:
        return fixed_canvas
    width, height = choose(rng, CANVAS_CHOICES)
    return Canvas(width=width, height=height)


def base_context(
    rng: random.Random,
    words: dict[str, Any],
    canvas: Canvas,
    style: dict[str, Any],
    template_family: str,
) -> dict[str, Any]:
    font = choose(rng, LOCAL_SAFE_FONTS)
    compact = canvas.width <= 760 or canvas.height <= 760
    margin = rng.choice([24, 28, 32, 36]) if compact else rng.choice([36, 42, 48, 56, 64])
    title_size = rng.randint(34, 48) if compact else rng.randint(46, 74)
    body_size = rng.randint(14, 17) if compact else rng.randint(16, 20)
    line_height = rng.choice(["1.28", "1.36", "1.45", "1.55"])
    section_count = rng.randint(2, 5)
    card_count = rng.randint(2, 6)
    table_count = rng.randint(0, 2)
    chart_count = rng.randint(0, 3)
    layout_id = (
        f"{template_family}__{style['style_id']}__{canvas.width}x{canvas.height}"
        f"__s{section_count}_c{card_count}_t{table_count}_ch{chart_count}"
    )
    palette = dict(style)
    return {
        "canvas": {"width": canvas.width, "height": canvas.height},
        "palette": palette,
        "style_id": style["style_id"],
        "body_class": f"style-{style['style_id']}",
        "layout_id": layout_id,
        "layout_counts": {
            "sections": section_count,
            "cards": card_count,
            "tables": table_count,
            "charts": chart_count,
        },
        "layout": {"margin": margin},
        "typography": {
            "title_size": title_size,
            "body_size": body_size,
            "line_height": line_height,
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
        "icons": [
            icon_svg(shape, palette, rng.choice([52, 64, 72]))
            for shape in rng.sample(["circle", "bars", "nodes", "diamond", "image"], k=3)
        ],
    }


def context_announcement(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ctx.update(
        {
            "title": f"{phrase(rng, words, 3, 5)} {choose(rng, words['verbs']).title()} {choose(rng, words['nouns']).title()}",
            "subtitle": sentence(rng, words, 8, 13),
            "bullets": [sentence(rng, words, 5, 8) for _ in range(ctx["layout_counts"]["sections"] + 1)],
            "reference_text": sentence(rng, words, 10, 14),
        }
    )
    return ctx


def context_report(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    labels = [m[:3] for m in words["months"][: rng.randint(5, 8)]]
    ctx.update(
        {
            "title": f"{choose(rng, words['adjectives']).title()} {choose(rng, words['topics']).title()} Abstract Report",
            "summary": " ".join(sentence(rng, words, 8, 12) for _ in range(3)),
            "kpis": [
                {
                    "label": choose(rng, words["metrics"]),
                    "value": number_choice(rng, words, "percentages"),
                    "note": f"{rng.choice(['up', 'down', 'flat'])} {number_choice(rng, words, 'deltas')} pts",
                }
                for _ in range(min(4, ctx["layout_counts"]["cards"]))
            ],
            "chart_title": choose(rng, words["metrics"]),
            "chart_svg": matplotlib_svg(rng, words, ctx["palette"], "line", labels, 5.0, 3.1),
            "notes": [sentence(rng, words, 6, 10) for _ in range(ctx["layout_counts"]["sections"] + 1)],
        }
    )
    ctx["layout_counts"]["charts"] = max(1, ctx["layout_counts"]["charts"])
    return ctx


def context_dashboard(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    labels = [choose(rng, words["departments"]).split()[0] for _ in range(6)]
    ctx.update(
        {
            "title": f"{choose(rng, words['topics']).title()} Dashboard",
            "metrics": [
                {
                    "label": choose(rng, words["metrics"]),
                    "value": str(number_choice(rng, words, "counts")),
                    "delta": f"{rng.choice(['+', '-'])}{number_choice(rng, words, 'deltas')} since last review",
                }
                for _ in range(4)
            ],
            "primary_chart_title": f"{choose(rng, words['metrics'])} Trend",
            "secondary_chart_title": f"{choose(rng, words['metrics'])} by Unit",
            "line_chart_svg": matplotlib_svg(rng, words, ctx["palette"], "line", [m[:3] for m in words["months"][:8]], 5.7, 4.2),
            "bar_chart_svg": matplotlib_svg(rng, words, ctx["palette"], "bar", labels, 4.1, 2.55),
            "status_rows": [
                {"name": choose(rng, words["products"]).title(), "status": choose(rng, words["status"])}
                for _ in range(6)
            ],
        }
    )
    ctx["layout_counts"]["charts"] = max(2, ctx["layout_counts"]["charts"])
    return ctx


def make_table_rows(rng: random.Random, words: dict[str, Any], count: int) -> list[list[str]]:
    rows = []
    for _ in range(count):
        rows.append(
            [
                choose(rng, words["products"]).title(),
                choose(rng, words["departments"]),
                choose(rng, words["status"]),
                str(number_choice(rng, words, "scores")),
                f"{choose(rng, words['months'])[:3]} {number_choice(rng, words, 'days')}",
            ]
        )
    return rows


def context_table(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ctx.update(
        {
            "title": f"{choose(rng, words['adjectives']).title()} {choose(rng, words['nouns']).title()} Register",
            "intro": " ".join(sentence(rng, words, 8, 12) for _ in range(2)),
            "columns": ["Item", "Owner", "Status", "Score", "Date"],
            "rows": make_table_rows(rng, words, rng.randint(8, 14)),
            "footer_left": choose(rng, words["topics"]).title(),
            "footer_right": "Generated from local template source",
        }
    )
    ctx["layout_counts"]["tables"] = max(1, ctx["layout_counts"]["tables"])
    return ctx


def context_poster(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    labels = [choose(rng, words["metrics"]).split()[0] for _ in range(4)]
    ctx.update(
        {
            "title": f"{choose(rng, words['adjectives']).title()} {choose(rng, words['topics']).title()}",
            "tagline": sentence(rng, words, 8, 12),
            "details": [
                f"{choose(rng, words['departments'])}: {choose(rng, words['status'])}",
                f"{choose(rng, words['products']).title()} review window",
                sentence(rng, words, 5, 8),
            ],
            "chart_title": f"{choose(rng, words['metrics'])} Mix",
            "chart_svg": matplotlib_svg(rng, words, ctx["palette"], "donut", labels, 4.8, 2.2),
            "footer_note": "Local digital export source",
        }
    )
    ctx["layout_counts"]["charts"] = max(1, ctx["layout_counts"]["charts"])
    return ctx


def context_news(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ctx.update(
        {
            "headline": f"{choose(rng, words['cities'])} {choose(rng, words['verbs'])} {phrase(rng, words, 3, 5)}",
            "dek": sentence(rng, words, 10, 15),
            "byline": f"{choose(rng, words['departments'])} Desk",
            "paragraphs": [sentence(rng, words, 15, 22) for _ in range(rng.randint(5, 8))],
            "side_items": [sentence(rng, words, 6, 9) for _ in range(4)],
        }
    )
    return ctx


def context_ecommerce(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ctx.update(
        {
            "title": choose(rng, words["products"]).title(),
            "subtitle": sentence(rng, words, 7, 11),
            "price": f"${number_choice(rng, words, 'scores')}.{number_choice(rng, words, 'code_pairs')}",
            "rating": f"{rng.choice(['4.1', '4.3', '4.5', '4.7', '4.9'])} / 5",
            "features": [sentence(rng, words, 5, 8) for _ in range(rng.randint(4, 6))],
            "spec_rows": make_table_rows(rng, words, 5),
        }
    )
    ctx["layout_counts"]["cards"] = max(4, ctx["layout_counts"]["cards"])
    return ctx


def context_mobile_social(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    messages = []
    for idx in range(rng.randint(6, 10)):
        messages.append(
            {
                "side": "right" if idx % 3 == 1 else "left",
                "sender": choose(rng, words["departments"]),
                "text": sentence(rng, words, 5, 10),
                "time": f"{number_choice(rng, words, 'code_pairs')}:{number_choice(rng, words, 'code_pairs')}",
            }
        )
    ctx.update(
        {
            "title": f"{choose(rng, words['topics']).title()} Thread",
            "subtitle": f"{choose(rng, words['organizations'])} / {choose(rng, words['cities'])}",
            "messages": messages,
            "social_cards": [
                {"label": choose(rng, words["metrics"]), "value": number_choice(rng, words, "counts")}
                for _ in range(3)
            ],
        }
    )
    return ctx


def context_infographic(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    steps = []
    for idx in range(rng.randint(4, 6)):
        steps.append(
            {
                "num": str(idx + 1),
                "title": phrase(rng, words, 2, 4),
                "text": sentence(rng, words, 6, 10),
                "icon": icon_svg(choose(rng, ["circle", "bars", "nodes", "diamond"]), ctx["palette"], 58),
            }
        )
    ctx.update(
        {
            "title": f"{phrase(rng, words, 3, 5)} Flow",
            "subtitle": sentence(rng, words, 8, 12),
            "steps": steps,
            "chart_svg": matplotlib_svg(rng, words, ctx["palette"], "bar", [s["num"] for s in steps], 5.2, 2.4),
        }
    )
    ctx["layout_counts"]["charts"] = max(1, ctx["layout_counts"]["charts"])
    return ctx


def context_education(rng: random.Random, words: dict[str, Any], ctx: dict[str, Any]) -> dict[str, Any]:
    ctx.update(
        {
            "title": f"{choose(rng, words['topics']).title()} Lecture",
            "subtitle": f"Module {number_choice(rng, words, 'code_pairs')} / {choose(rng, words['departments'])}",
            "objectives": [sentence(rng, words, 5, 8) for _ in range(4)],
            "callout": sentence(rng, words, 10, 14),
            "chart_svg": matplotlib_svg(rng, words, ctx["palette"], "line", [m[:3] for m in words["months"][:6]], 4.8, 2.6),
        }
    )
    ctx["layout_counts"]["charts"] = max(1, ctx["layout_counts"]["charts"])
    return ctx


CONTEXT_BUILDERS: dict[str, Callable[[random.Random, dict[str, Any], dict[str, Any]], dict[str, Any]]] = {
    "announcement_notice": context_announcement,
    "report_academic_abstract": context_report,
    "dashboard_with_charts": context_dashboard,
    "table_form_menu": context_table,
    "poster_event_card": context_poster,
    "news_article_page": context_news,
    "ecommerce_product_card": context_ecommerce,
    "mobile_chat_social_card": context_mobile_social,
    "infographic_timeline_flowchart": context_infographic,
    "education_slide_lecture_page": context_education,
}


def create_environment() -> Environment:
    return Environment(
        loader=FileSystemLoader(str(TEMPLATE_DIR)),
        autoescape=select_autoescape(["html", "xml"]),
        trim_blocks=True,
        lstrip_blocks=True,
    )


def get_playwright_version() -> str:
    try:
        return importlib.metadata.version("playwright")
    except importlib.metadata.PackageNotFoundError:
        return "unknown"


def render_html_batch(
    count: int,
    base_seed: int,
    fixed_canvas: Canvas | None,
    output_dir: Path,
    wordlists: dict[str, Any],
) -> list[dict[str, Any]]:
    env = create_environment()
    html_dir = output_dir / "html"
    html_dir.mkdir(parents=True, exist_ok=True)
    records = []

    for index in range(count):
        sample_id = f"sample_{index + 1:06d}"
        random_seed = base_seed + index
        rng = random.Random(random_seed)
        canvas = canvas_for_sample(rng, fixed_canvas)
        template_family = TEMPLATE_ORDER[index % len(TEMPLATE_ORDER)]
        style = VISUAL_STYLES[(index + rng.randrange(len(VISUAL_STYLES))) % len(VISUAL_STYLES)]
        context = base_context(rng, wordlists, canvas, style, template_family)
        context = CONTEXT_BUILDERS[template_family](rng, wordlists, context)
        template = env.get_template(TEMPLATE_FILES[template_family])
        html = template.render(**context)
        html_path = html_dir / f"{sample_id}.html"
        html_path.write_text(html, encoding="utf-8")
        records.append(
            {
                "sample_id": sample_id,
                "template_family": template_family,
                "style_id": style["style_id"],
                "layout_id": context["layout_id"],
                "random_seed": random_seed,
                "canvas_size": {"width": canvas.width, "height": canvas.height},
                "font_family_id": context["typography"]["font_family_id"],
                "layout_counts": context["layout_counts"],
                "html_path": html_path,
                "html_sha256": sha256_text(html),
                "image_path": None,
                "output_asset_hash": None,
                "decoded_pixel_hash": None,
                "jpeg_variant": None,
            }
        )
    return records


def screenshot_batch(records: list[dict[str, Any]], output_dir: Path, timeout_ms: int) -> tuple[str, str]:
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
            page.goto(record["html_path"].resolve().as_uri(), wait_until="networkidle", timeout=timeout_ms)
            output_path = image_dir / f"{record['sample_id']}.png"
            page.screenshot(path=str(output_path), type="png", full_page=False, timeout=timeout_ms)
            record["image_path"] = output_path
            record["output_asset_hash"] = sha256_file(output_path)
            record["decoded_pixel_hash"] = decoded_pixel_hash(output_path)
        browser.close()

    return playwright_version, chromium_version


def make_jpeg_variants(records: list[dict[str, Any]], output_dir: Path, quality: int | None) -> None:
    if quality is None:
        return
    from PIL import Image

    jpeg_dir = output_dir / "jpeg"
    jpeg_dir.mkdir(parents=True, exist_ok=True)
    for record in records:
        png_path = record["image_path"]
        if png_path is None:
            continue
        jpeg_path = jpeg_dir / f"{record['sample_id']}_q{quality}.jpg"
        with Image.open(png_path) as image:
            image.convert("RGB").save(jpeg_path, "JPEG", quality=quality, optimize=False, progressive=False)
        record["jpeg_variant"] = {
            "sample_id": f"{record['sample_id']}_jpeg_q{quality}",
            "output_path": jpeg_path,
            "output_format": "jpeg",
            "jpeg_quality": quality,
            "output_asset_hash": sha256_file(jpeg_path),
            "decoded_pixel_hash": decoded_pixel_hash(jpeg_path),
        }


def manifest_from_record(
    record: dict[str, Any],
    output_dir: Path,
    renderer_version: str,
    wordlist_version: str,
    output_format: str,
) -> dict[str, Any]:
    if output_format == "png":
        sample_id = record["sample_id"]
        output_path = record["image_path"]
        output_asset_hash = record["output_asset_hash"]
        pixel_hash = record["decoded_pixel_hash"]
        parent_sample_id = None
        parent_asset_hashes = [record["html_sha256"]]
        chain_events: list[dict[str, Any]] = []
    else:
        variant = record["jpeg_variant"]
        sample_id = variant["sample_id"]
        output_path = variant["output_path"]
        output_asset_hash = variant["output_asset_hash"]
        pixel_hash = variant["decoded_pixel_hash"]
        parent_sample_id = record["sample_id"]
        parent_asset_hashes = [record["output_asset_hash"]]
        chain_events = [
            {
                "event_type": "digital_recompression",
                "event_kind": "manipulation_or_processing",
                "order": 1,
                "scope": "global",
                "semantic_change_degree": "none",
                "mask_path": None,
                "operation_registry_ref": "pillow_jpeg_recompression",
                "parameters": {
                    "codec": "jpeg",
                    "quality": variant["jpeg_quality"],
                    "optimize": False,
                    "progressive": False,
                },
            }
        ]

    return {
        "schema_version": "provenance_chain_v1",
        "sample_id": sample_id,
        "parent_sample_id": parent_sample_id,
        "parent_asset_hashes": parent_asset_hashes,
        "source_type": "html",
        "source_path": relative_string(record["html_path"], output_dir),
        "source_asset_hash": record["html_sha256"],
        "template_family": record["template_family"],
        "style_id": record["style_id"],
        "layout_id": record["layout_id"],
        "random_seed": record["random_seed"],
        "renderer": "playwright_chromium",
        "renderer_version": renderer_version,
        "canvas_size": record["canvas_size"],
        "output_format": output_format,
        "html_path": relative_string(record["html_path"], output_dir),
        "output_path": relative_string(output_path, output_dir),
        "html_sha256": record["html_sha256"],
        "output_asset_hash": output_asset_hash,
        "decoded_pixel_hash": pixel_hash,
        "font_family_id": record["font_family_id"],
        "layout_counts": record["layout_counts"],
        "wordlist_version": wordlist_version,
        "non_ai_generation": True,
        "ai_inference_used": False,
        "external_assets_used": False,
        "label_status": "controlled_complete",
        "initial_digital_event": "digital_to_digital_file_export",
        "last_acquisition_event": "none",
        "chain_events": chain_events,
    }


def write_manifests(
    records: list[dict[str, Any]],
    output_dir: Path,
    renderer_version: str,
    wordlist_version: str,
) -> None:
    manifest_dir = output_dir / "manifests"
    manifest_dir.mkdir(parents=True, exist_ok=True)
    jsonl_path = manifest_dir / "samples.jsonl"
    with jsonl_path.open("w", encoding="utf-8") as jsonl:
        for record in records:
            manifests = [manifest_from_record(record, output_dir, renderer_version, wordlist_version, "png")]
            if record.get("jpeg_variant"):
                manifests.append(manifest_from_record(record, output_dir, renderer_version, wordlist_version, "jpeg"))
            for manifest in manifests:
                per_sample_path = manifest_dir / f"{manifest['sample_id']}.json"
                per_sample_path.write_text(json.dumps(manifest, indent=2, sort_keys=True) + "\n", encoding="utf-8")
                jsonl.write(json.dumps(manifest, sort_keys=True) + "\n")


def relative_string(path: Path | None, base: Path) -> str | None:
    if path is None:
        return None
    try:
        return str(path.resolve().relative_to(base.resolve()))
    except ValueError:
        return str(path)


def write_summary(records: list[dict[str, Any]], output_dir: Path, renderer_version: str) -> None:
    qa_dir = output_dir / "qa"
    qa_dir.mkdir(parents=True, exist_ok=True)
    by_template = {template_family: 0 for template_family in TEMPLATE_ORDER}
    by_style = {style["style_id"]: 0 for style in VISUAL_STYLES}
    by_canvas: dict[str, int] = {f"{w}x{h}": 0 for w, h in CANVAS_CHOICES}
    jpeg_count = 0
    for record in records:
        by_template[record["template_family"]] += 1
        by_style[record["style_id"]] += 1
        canvas = record["canvas_size"]
        by_canvas[f"{canvas['width']}x{canvas['height']}"] += 1
        if record.get("jpeg_variant"):
            jpeg_count += 1
    summary = {
        "sample_count": len(records),
        "png_count": len(records),
        "jpeg_variant_count": jpeg_count,
        "templates": by_template,
        "styles": by_style,
        "canvas_sizes": by_canvas,
        "renderer": "playwright_chromium",
        "renderer_version": renderer_version,
        "ai_inference_used": False,
        "external_assets_used": False,
        "missing_images": [record["sample_id"] for record in records if record["image_path"] is None],
    }
    (qa_dir / "summary.json").write_text(json.dumps(summary, indent=2, sort_keys=True) + "\n", encoding="utf-8")


def build_arg_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Generate non-AI digital-export raster samples.")
    parser.add_argument("--count", type=int, default=1000, help="Number of source PNG samples to generate.")
    parser.add_argument("--seed", type=int, default=20260615, help="Base random seed.")
    parser.add_argument(
        "--canvas",
        type=parse_canvas,
        default=None,
        help="Optional fixed canvas WIDTHxHEIGHT. If omitted, each sample randomly uses one allowed size.",
    )
    parser.add_argument(
        "--jpeg-quality",
        type=int,
        default=None,
        help="Optional JPEG recompression quality. If set, one JPEG variant is produced per PNG.",
    )
    parser.add_argument(
        "--output-dir",
        type=Path,
        default=SCRIPT_DIR / "generated_pilot_v2_1000",
        help="Output directory for HTML, PNG, optional JPEG, manifests, and QA.",
    )
    parser.add_argument("--overwrite", action="store_true", help="Delete output directory before generation.")
    parser.add_argument("--timeout-ms", type=int, default=30000, help="Playwright navigation/screenshot timeout.")
    return parser


def main(argv: list[str] | None = None) -> int:
    parser = build_arg_parser()
    args = parser.parse_args(argv)
    if args.count <= 0:
        parser.error("--count must be greater than zero")
    if args.jpeg_quality is not None and not (1 <= args.jpeg_quality <= 100):
        parser.error("--jpeg-quality must be between 1 and 100")

    output_dir = args.output_dir.resolve()
    ensure_empty_or_create(output_dir, args.overwrite)
    for child in ["html", "images", "manifests", "qa"]:
        (output_dir / child).mkdir(parents=True, exist_ok=True)

    wordlists = load_wordlists()
    records = render_html_batch(args.count, args.seed, args.canvas, output_dir, wordlists)
    playwright_version, chromium_version = screenshot_batch(records, output_dir, args.timeout_ms)
    make_jpeg_variants(records, output_dir, args.jpeg_quality)
    renderer_version = f"playwright {playwright_version}; chromium {chromium_version}"
    write_manifests(records, output_dir, renderer_version, wordlists.get("version", "unknown"))
    write_summary(records, output_dir, renderer_version)

    print(f"Generated {len(records)} PNG samples in {output_dir}")
    if args.jpeg_quality is not None:
        print(f"Generated {len(records)} JPEG variants at quality {args.jpeg_quality}")
    print(f"Manifest JSONL: {output_dir / 'manifests' / 'samples.jsonl'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
