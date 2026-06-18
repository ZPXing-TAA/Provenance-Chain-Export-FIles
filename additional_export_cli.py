#!/usr/bin/env python3
"""Shared CLI wrapper for one additional digital-export pipeline."""

from __future__ import annotations

import argparse
from pathlib import Path

from generate_additional_exports import parse_canvas, run_pipeline


def run_single_pipeline(
    pipeline: str,
    argv: list[str] | None = None,
    *,
    default_count: int = 1000,
) -> int:
    parser = argparse.ArgumentParser(
        description=f"Generate controlled {pipeline} digital-to-digital PNG export samples."
    )
    parser.add_argument("--count", type=int, default=default_count)
    parser.add_argument("--seed", type=int, default=20260615)
    parser.add_argument("--canvas", type=parse_canvas, default=None, help="Optional fixed canvas, e.g. 1024x1024.")
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--overwrite", action="store_true")
    parser.add_argument(
        "--source-format",
        choices=["docx", "odt", "xlsx", "ods", "pptx", "odp"],
        default=None,
        help="Office source format for document/spreadsheet/presentation exports.",
    )
    args = parser.parse_args(argv)
    if args.count < 1:
        parser.error("--count must be >= 1")
    run_pipeline(
        pipeline=pipeline,
        count=args.count,
        seed=args.seed,
        fixed_canvas=args.canvas,
        output_dir=args.output_dir,
        overwrite=args.overwrite,
        source_format=args.source_format,
    )
    return 0
