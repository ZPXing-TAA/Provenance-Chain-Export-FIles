#!/usr/bin/env python3
"""Generate native PPTX/ODP presentation exports rasterized via LibreOffice."""

from __future__ import annotations

from additional_export_cli import run_single_pipeline


if __name__ == "__main__":
    raise SystemExit(run_single_pipeline("presentation_export"))
