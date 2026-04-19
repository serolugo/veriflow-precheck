from pathlib import Path
import subprocess


def generate_datasheet_md(
    repo_name: str,
    tile_config,
    run_id: str,
    run_date: str,
    connectivity: str,
    synthesis: str,
    cells: str,
    status: str,
    commit_sha: str,
    output_path: Path,
) -> Path:
    """
    Generate a Markdown datasheet for the tile.
    Returns the path to the generated .md file.
    """
    cells_str = cells if cells else "-"
    status_str = "PASS" if status == "PASS" else "FAIL"

    content = f"""---
title: "{tile_config.tile_name}"
author: "{tile_config.tile_author}"
date: "{run_date}"
---

# {tile_config.tile_name}

**Repository:** {repo_name}  
**Author:** {tile_config.tile_author}  
**Top Module:** `{tile_config.top_module}`  
**Shuttle:** {tile_config.shuttle if tile_config.shuttle else "-"}  
**Date:** {run_date}  

---

## Description

{tile_config.description.strip()}

---

## Port Convention (SemiCoLab)

| Port | Direction | Width | Description |
|------|-----------|-------|-------------|
| `clk` | input | 1 | Clock |
| `arst_n` | input | 1 | Async reset, active low |
| `csr_in` | input | 16 | Control/Status Register input |
| `data_reg_a` | input | 32 | Operand A |
| `data_reg_b` | input | 32 | Operand B |
| `data_reg_c` | output | 32 | Result |
| `csr_out` | output | 16 | Control/Status Register output |
| `csr_in_re` | output | 1 | CSR input read enable |
| `csr_out_we` | output | 1 | CSR output write enable |

### Tile Port Usage

{tile_config.ports.strip()}

---

## Usage Guide

{tile_config.usage_guide.strip()}

---

## Precheck Result

| Stage | Result |
|-------|--------|
| Connectivity Check | {connectivity} |
| Synthesis | {synthesis} |
| Cell Count | {cells_str} |
| **Status** | **{status_str}** |

**Run:** {run_id}  
**Commit:** `{commit_sha[:7]}`  
"""

    output_path.write_text(content, encoding="utf-8")
    return output_path


def convert_md_to_pdf(md_path: Path, pdf_path: Path) -> bool:
    """
    Convert Markdown to PDF using WeasyPrint.
    Returns True if successful.
    """
    try:
        import markdown
        from weasyprint import HTML, CSS

        md_text = md_path.read_text(encoding="utf-8")
        html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

        html = f"""<!DOCTYPE html>
<html>
<head>
<meta charset="utf-8">
<style>
  body {{
    font-family: Helvetica, Arial, sans-serif;
    font-size: 11pt;
    margin: 2.5cm;
    color: #262626;
    line-height: 1.5;
  }}
  h1 {{ font-size: 18pt; border-bottom: 1px solid #999; padding-bottom: 4px; }}
  h2 {{ font-size: 13pt; margin-top: 1.5em; }}
  table {{ border-collapse: collapse; width: 100%; margin: 1em 0; }}
  th {{ background: #ebebeb; padding: 6px 10px; text-align: left; font-size: 10pt; }}
  td {{ padding: 5px 10px; border-bottom: 1px solid #ddd; font-size: 10pt; }}
  code {{ background: #f5f5f5; padding: 1px 4px; font-family: monospace; font-size: 10pt; }}
  pre {{ background: #f5f5f5; padding: 10px; font-size: 9pt; }}
  hr {{ border: none; border-top: 1px solid #ccc; margin: 1.5em 0; }}
</style>
</head>
<body>
{html_body}
</body>
</html>"""

        HTML(string=html).write_pdf(str(pdf_path))
        return pdf_path.exists()

    except ImportError as e:
        print(f"[precheck] WeasyPrint not available: {e}")
        return False
    except Exception as e:
        print(f"[precheck] PDF generation failed: {e}")
        return False
