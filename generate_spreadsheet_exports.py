#!/usr/bin/env python3
"""Generate native XLSX/ODS spreadsheet exports rasterized via LibreOffice Calc."""

from __future__ import annotations

from additional_export_cli import run_single_pipeline


if __name__ == "__main__":
    raise SystemExit(run_single_pipeline("spreadsheet_export"))
