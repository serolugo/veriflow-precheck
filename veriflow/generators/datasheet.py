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
    Convert Markdown to PDF using pandoc.
    Returns True if successful.
    """
    # Try wkhtmltopdf first (pre-installed on GitHub Actions Ubuntu runners)
    # Fall back to pdflatex if available
    for engine in ["wkhtmltopdf", "pdflatex", "xelatex"]:
        try:
            if engine == "wkhtmltopdf":
                result = subprocess.run(
                    [
                        "pandoc", str(md_path),
                        "-o", str(pdf_path),
                        "--pdf-engine=wkhtmltopdf",
                        "-V", "margin-top=2cm",
                        "-V", "margin-bottom=2cm",
                        "-V", "margin-left=2.5cm",
                        "-V", "margin-right=2.5cm",
                    ],
                    capture_output=True, text=True,
                )
            else:
                result = subprocess.run(
                    [
                        "pandoc", str(md_path),
                        "-o", str(pdf_path),
                        f"--pdf-engine={engine}",
                        "-V", "geometry:margin=2.5cm",
                        "-V", "fontsize=11pt",
                    ],
                    capture_output=True, text=True,
                )
            if result.returncode == 0 and pdf_path.exists():
                return True
            else:
                print(f"[precheck] PDF engine {engine} failed: {result.stderr[:200]}")
        except FileNotFoundError:
            print(f"[precheck] PDF engine {engine} not found")
            continue
    return False
