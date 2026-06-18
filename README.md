# Non-AI Digital Export Image Generator

This workflow creates fully controlled, non-AI, born-digital export images for
the pilot provenance dataset.

Current formal scope is limited to six source classes:

1. HTML
2. SVG
3. PDF
4. DOCX / ODT
5. XLSX / ODS
6. PPTX / ODP

No generator calls an LLM, image generation model, online API, remote image, or
external web asset. PNG masters use:

```text
initial_digital_event = digital_to_digital_file_export
chain_events = []
```

JPEG recompression is a separate downstream stage:

```text
chain_events += digital_recompression
```

## Install

```bash
python3 -m pip install -r pilot_export_workflow/requirements.txt
python3 -m playwright install chromium
brew install --cask libreoffice
```

LibreOffice is required for DOCX/ODT, XLSX/ODS, and PPTX/ODP rasterization.

## Official Entry Points

### HTML

```bash
python3 pilot_export_workflow/generate_html_exports.py \
  --count 1000 \
  --seed 20260615 \
  --output-dir pilot_export_workflow/generated_html_v1_1000 \
  --overwrite
```

Source path: `html/sample_000001.html`

Renderer: `playwright_chromium`

### SVG

```bash
python3 pilot_export_workflow/generate_svg_exports.py \
  --count 1000 \
  --seed 20260615 \
  --output-dir pilot_export_workflow/generated_svg_v1_1000 \
  --overwrite
```

Source path: `svg/sample_000001.svg`

Renderer: `playwright_chromium_svg_rasterizer`

### PDF

```bash
python3 pilot_export_workflow/generate_pdf_exports.py \
  --count 1000 \
  --seed 20260615 \
  --output-dir pilot_export_workflow/generated_pdf_v1_1000 \
  --overwrite
```

Source path: `pdf/sample_000001.pdf`

Renderer: `pymupdf_pdf_rasterizer`

### DOCX / ODT

```bash
python3 pilot_export_workflow/generate_document_exports.py \
  --count 1000 \
  --seed 20260615 \
  --source-format docx \
  --output-dir pilot_export_workflow/generated_docx_v1_1000 \
  --overwrite

python3 pilot_export_workflow/generate_document_exports.py \
  --count 1000 \
  --seed 20260615 \
  --source-format odt \
  --output-dir pilot_export_workflow/generated_odt_v1_1000 \
  --overwrite
```

Source path: `documents/sample_000001.docx` or `documents/sample_000001.odt`

Renderer: `libreoffice_docx_pdf_pymupdf_rasterizer` or
`libreoffice_odt_pdf_pymupdf_rasterizer`

### XLSX / ODS

```bash
python3 pilot_export_workflow/generate_spreadsheet_exports.py \
  --count 1000 \
  --seed 20260615 \
  --source-format xlsx \
  --output-dir pilot_export_workflow/generated_xlsx_v1_1000 \
  --overwrite

python3 pilot_export_workflow/generate_spreadsheet_exports.py \
  --count 1000 \
  --seed 20260615 \
  --source-format ods \
  --output-dir pilot_export_workflow/generated_ods_v1_1000 \
  --overwrite
```

Source path: `spreadsheets/sample_000001.xlsx` or
`spreadsheets/sample_000001.ods`

Renderer: `libreoffice_calc_xlsx_pdf_pymupdf_rasterizer` or
`libreoffice_calc_ods_pdf_pymupdf_rasterizer`

### PPTX / ODP

```bash
python3 pilot_export_workflow/generate_presentation_exports.py \
  --count 1000 \
  --seed 20260615 \
  --source-format pptx \
  --output-dir pilot_export_workflow/generated_pptx_v1_1000 \
  --overwrite

python3 pilot_export_workflow/generate_presentation_exports.py \
  --count 1000 \
  --seed 20260615 \
  --source-format odp \
  --output-dir pilot_export_workflow/generated_odp_v1_1000 \
  --overwrite
```

Source path: `presentations/sample_000001.pptx` or
`presentations/sample_000001.odp`

Renderer: `libreoffice_impress_pptx_pdf_pymupdf_rasterizer` or
`libreoffice_impress_odp_pdf_pymupdf_rasterizer`

## Shared Office/PDF Backend

`generate_additional_exports.py` is the shared backend for PDF and Office
exports. It can run the four backend pipelines directly:

```bash
python3 pilot_export_workflow/generate_additional_exports.py \
  --pipeline all \
  --count 10 \
  --seed 20260615 \
  --output-dir pilot_export_workflow/generated_pdf_office_smoke \
  --overwrite
```

`--pipeline all` covers:

```text
pdf
document_export      # default source-format: docx
spreadsheet_export   # default source-format: xlsx
presentation_export  # default source-format: pptx
```

Use `--source-format` only with a single office pipeline.

## Output Layout

Each source class writes source files, PNG masters, per-sample JSON manifests,
a JSONL manifest, and a QA summary:

```text
generated_<class>/
  <source-dir>/
    sample_000001.<source-extension>
  images/
    sample_000001.png
  manifests/
    sample_000001.json
    samples.jsonl
  qa/
    summary.json
```

Office exports also keep LibreOffice PDF intermediates:

```text
pdf_intermediate/
  sample_000001.pdf
```

## Manifest Contract

Every PNG master manifest includes:

```text
schema_version
sample_id
source_type
source_path
source_asset_hash
parent_asset_hashes
template_family
style_id
layout_id
random_seed
renderer
renderer_version
canvas_size
output_format
output_path
output_asset_hash
decoded_pixel_hash
label_status
initial_digital_event
last_acquisition_event
chain_events
ai_inference_used
external_assets_used
```

## JPEG Recompression Stage

Run JPEG recompression from any PNG master JSONL manifest:

```bash
python3 pilot_export_workflow/jpeg_recompress_exports.py \
  --input-manifest pilot_export_workflow/generated_html_v1_1000/manifests/samples.jsonl \
  --output-dir pilot_export_workflow/generated_html_v1_1000_jpeg_q90 \
  --quality 90 \
  --subsampling '4:2:0' \
  --overwrite
```

JPEG derivative manifests keep:

```text
initial_digital_event = digital_to_digital_file_export
chain_events = [digital_recompression]
parent_asset_hashes = [PNG master output_asset_hash]
```

## Current Scope Report

See `pilot_export_workflow/SIX_SOURCE_SCOPE_REPORT.md` for the current
implementation status, smoke QA, and one rendered example per class.
