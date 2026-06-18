# Pilot Digital Export Workflow Implementation Report

Date: 2026-06-18

## Current Status

The implementation is now organized around the current formal six-source pilot
scope:

1. HTML
2. SVG
3. PDF
4. DOCX / ODT
5. XLSX / ODS
6. PPTX / ODP

The current implementation details, examples, renderer list, and reproducibility
QA are documented in:

```text
pilot_export_workflow/SIX_SOURCE_SCOPE_REPORT.md
```

## Provenance Contract

Every PNG master remains a controlled initial digital export:

```text
initial_digital_event = digital_to_digital_file_export
chain_events = []
ai_inference_used = false
external_assets_used = false
```

JPEG recompression is kept as a separate downstream transform:

```text
chain_events += digital_recompression
```

## Active Code Structure

Official source-class CLIs:

- `generate_html_exports.py`
- `generate_svg_exports.py`
- `generate_pdf_exports.py`
- `generate_document_exports.py`
- `generate_spreadsheet_exports.py`
- `generate_presentation_exports.py`

Shared implementation files:

- `generate_non_ai_exports.py`: HTML generator backend
- `generate_additional_exports.py`: PDF and Office generator backend
- `additional_export_cli.py`: shared PDF/Office CLI wrapper
- `jpeg_recompress_exports.py`: downstream JPEG recompression stage

Historical experimental paths documented in earlier iterations are no longer
formal workflow entry points.
