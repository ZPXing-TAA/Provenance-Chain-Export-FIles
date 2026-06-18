# Six Source Digital Export Scope Report

Date: 2026-06-18

## Summary

The pilot digital export workflow is now scoped to these six controlled
non-AI source classes:

1. HTML
2. SVG
3. PDF
4. DOCX / ODT
5. XLSX / ODS
6. PPTX / ODP

Removed from the formal workflow:

- deterministic layered composite
- multi-source composite
- procedural rendered scene
- legacy CSV/HTML table export
- legacy HTML slide export

All PNG masters keep:

```text
initial_digital_event = digital_to_digital_file_export
chain_events = []
ai_inference_used = false
external_assets_used = false
```

## Current Entry Points

| Source class | CLI | Source formats | Renderer |
|---|---|---|---|
| HTML | `generate_html_exports.py` | `.html` | `playwright_chromium` |
| SVG | `generate_svg_exports.py` | `.svg` | `playwright_chromium_svg_rasterizer` |
| PDF | `generate_pdf_exports.py` | `.pdf` | `pymupdf_pdf_rasterizer` |
| DOCX / ODT | `generate_document_exports.py` | `.docx`, `.odt` | LibreOffice -> PDF -> PyMuPDF |
| XLSX / ODS | `generate_spreadsheet_exports.py` | `.xlsx`, `.ods` | LibreOffice Calc -> PDF -> PyMuPDF |
| PPTX / ODP | `generate_presentation_exports.py` | `.pptx`, `.odp` | LibreOffice Impress -> PDF -> PyMuPDF |

The shared backend for PDF and Office exports is:

```text
pilot_export_workflow/generate_additional_exports.py
```

It now exposes only:

```text
pdf
document_export
spreadsheet_export
presentation_export
```

## Example Artifacts

Examples come from:

```text
pilot_export_workflow/generated_six_class_qa_a/
```

### 1. HTML

Pipeline:

```text
self-authored HTML source -> Chromium screenshot -> PNG master
```

Artifacts:

- Source: `generated_six_class_qa_a/html/html/sample_000001.html`
- PNG master: `generated_six_class_qa_a/html/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/html/manifests/sample_000001.json`

Renderer:

```text
playwright_chromium
```

Rendered example:

![HTML export example](generated_six_class_qa_a/html/images/sample_000001.png)

### 2. SVG

Pipeline:

```text
self-authored standalone SVG source -> Chromium SVG rasterization -> PNG master
```

Artifacts:

- Source: `generated_six_class_qa_a/svg/svg/sample_000001.svg`
- PNG master: `generated_six_class_qa_a/svg/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/svg/manifests/sample_000001.json`

Renderer:

```text
playwright_chromium_svg_rasterizer
```

Rendered example:

![SVG export example](generated_six_class_qa_a/svg/images/sample_000001.png)

### 3. PDF

Pipeline:

```text
self-authored PDF source -> PyMuPDF rasterization -> PNG master
```

Artifacts:

- Source: `generated_six_class_qa_a/pdf/pdf/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/pdf/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/pdf/manifests/sample_000001.json`

Renderer:

```text
pymupdf_pdf_rasterizer
```

Rendered example:

![PDF export example](generated_six_class_qa_a/pdf/images/sample_000001.png)

### 4. DOCX / ODT

Pipeline:

```text
self-authored document source -> LibreOffice PDF export -> PyMuPDF rasterization -> PNG master
```

DOCX artifacts:

- Source: `generated_six_class_qa_a/docx/documents/sample_000001.docx`
- Intermediate PDF: `generated_six_class_qa_a/docx/pdf_intermediate/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/docx/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/docx/manifests/sample_000001.json`

ODT artifacts:

- Source: `generated_six_class_qa_a/odt/documents/sample_000001.odt`
- Intermediate PDF: `generated_six_class_qa_a/odt/pdf_intermediate/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/odt/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/odt/manifests/sample_000001.json`

Renderers:

```text
libreoffice_docx_pdf_pymupdf_rasterizer
libreoffice_odt_pdf_pymupdf_rasterizer
```

Rendered examples:

![DOCX export example](generated_six_class_qa_a/docx/images/sample_000001.png)

![ODT export example](generated_six_class_qa_a/odt/images/sample_000001.png)

### 5. XLSX / ODS

Pipeline:

```text
self-authored spreadsheet source -> LibreOffice Calc PDF export -> PyMuPDF rasterization -> PNG master
```

XLSX artifacts:

- Source: `generated_six_class_qa_a/xlsx/spreadsheets/sample_000001.xlsx`
- Intermediate PDF: `generated_six_class_qa_a/xlsx/pdf_intermediate/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/xlsx/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/xlsx/manifests/sample_000001.json`

ODS artifacts:

- Source: `generated_six_class_qa_a/ods/spreadsheets/sample_000001.ods`
- Intermediate PDF: `generated_six_class_qa_a/ods/pdf_intermediate/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/ods/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/ods/manifests/sample_000001.json`

Renderers:

```text
libreoffice_calc_xlsx_pdf_pymupdf_rasterizer
libreoffice_calc_ods_pdf_pymupdf_rasterizer
```

Rendered examples:

![XLSX export example](generated_six_class_qa_a/xlsx/images/sample_000001.png)

![ODS export example](generated_six_class_qa_a/ods/images/sample_000001.png)

### 6. PPTX / ODP

Pipeline:

```text
self-authored presentation source -> LibreOffice Impress PDF export -> PyMuPDF rasterization -> PNG master
```

PPTX artifacts:

- Source: `generated_six_class_qa_a/pptx/presentations/sample_000001.pptx`
- Intermediate PDF: `generated_six_class_qa_a/pptx/pdf_intermediate/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/pptx/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/pptx/manifests/sample_000001.json`

ODP artifacts:

- Source: `generated_six_class_qa_a/odp/presentations/sample_000001.odp`
- Intermediate PDF: `generated_six_class_qa_a/odp/pdf_intermediate/sample_000001.pdf`
- PNG master: `generated_six_class_qa_a/odp/images/sample_000001.png`
- Manifest: `generated_six_class_qa_a/odp/manifests/sample_000001.json`

Renderers:

```text
libreoffice_impress_pptx_pdf_pymupdf_rasterizer
libreoffice_impress_odp_pdf_pymupdf_rasterizer
```

Rendered examples:

![PPTX export example](generated_six_class_qa_a/pptx/images/sample_000001.png)

![ODP export example](generated_six_class_qa_a/odp/images/sample_000001.png)

## QA Result

Two same-seed QA runs were generated:

```text
pilot_export_workflow/generated_six_class_qa_a
pilot_export_workflow/generated_six_class_qa_b
```

Checked classes/formats:

```text
html
svg
pdf
docx
odt
xlsx
ods
pptx
odp
```

Validation checks:

- manifest has `source_type`, `source_path`, and `source_asset_hash`
- `initial_digital_event = digital_to_digital_file_export`
- `chain_events = []`
- `ai_inference_used = false`
- `external_assets_used = false`
- PNG dimensions match manifest `canvas_size`
- same-seed `source_asset_hash` exact match
- same-seed `output_asset_hash` exact match
- same-seed `decoded_pixel_hash` exact match

Result:

```text
All six source classes and all Office variants passed same-seed reproducibility QA.
```

## Renderer Summary From QA

```json
{
  "docx": "libreoffice_docx_pdf_pymupdf_rasterizer",
  "html": "playwright_chromium",
  "odp": "libreoffice_impress_odp_pdf_pymupdf_rasterizer",
  "ods": "libreoffice_calc_ods_pdf_pymupdf_rasterizer",
  "odt": "libreoffice_odt_pdf_pymupdf_rasterizer",
  "pdf": "pymupdf_pdf_rasterizer",
  "pptx": "libreoffice_impress_pptx_pdf_pymupdf_rasterizer",
  "svg": "playwright_chromium_svg_rasterizer",
  "xlsx": "libreoffice_calc_xlsx_pdf_pymupdf_rasterizer"
}
```

## Notes

- LibreOffice binary used during QA: `/opt/homebrew/bin/soffice`.
- Verified LibreOffice version: `LibreOffice 26.2.4.2 0229ac93fcf0d7cbc6376066c6f35021cef002dc`.
- Office XML/ODF ZIP containers are normalized for deterministic source hashes.
- HTML and SVG remain separate generators because their template/rendering stacks are materially different from Office/PDF.
