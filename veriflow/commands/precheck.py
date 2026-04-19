"""
VeriFlow Precheck Command
Designed for CI use in semicolab IP tile repos.
Runs connectivity check + synthesis, generates documentation.
"""

import csv
import json
import os
import re
import tempfile
from datetime import date
from pathlib import Path

import yaml

from veriflow.core import VeriFlowError
from veriflow.core.sim_runner import run_connectivity_check
from veriflow.core.synth_runner import run_synthesis
from veriflow.core.validator import validate_tools
from veriflow.models.tile_config_ci import TileConfigCI


RECORDS_HEADER = [
    "run", "date", "commit", "author", "connectivity",
    "synthesis", "cells", "status", "tile_id",
]


def _get_run_id(runs_dir: Path) -> str:
    """Determine next run ID by scanning existing run-NNN dirs."""
    pattern = re.compile(r"^run-(\d{3})$")
    max_num = 0
    if runs_dir.exists():
        for d in runs_dir.iterdir():
            m = pattern.match(d.name)
            if m:
                n = int(m.group(1))
                if n > max_num:
                    max_num = n
    return f"run-{max_num + 1:03d}"


def _read_records(records_path: Path) -> list[dict]:
    if not records_path.exists() or not records_path.stat().st_size:
        return []
    content = records_path.read_text(encoding="utf-8").strip()
    if not content:
        return []
    return list(csv.DictReader(content.splitlines()))


def _append_record(records_path: Path, row: dict) -> None:
    records_path.parent.mkdir(parents=True, exist_ok=True)
    write_header = not records_path.exists() or not records_path.stat().st_size
    with records_path.open("a", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=RECORDS_HEADER)
        if write_header:
            writer.writeheader()
        writer.writerow(row)


def cmd_precheck(
    repo_root: Path,
    run_number: str,
    commit_sha: str = "",
    commit_author: str = "",
) -> None:
    """
    Run SemiCoLab IP tile precheck from the repo root.
    Designed for GitHub Actions CI.
    """

    # ── Validate tools ────────────────────────────────────────────────────────
    validate_tools()

    # ── Read tile_config.yaml ─────────────────────────────────────────────────
    tile_cfg_path = repo_root / "tile_config.yaml"
    if not tile_cfg_path.exists():
        raise VeriFlowError(f"tile_config.yaml not found at repo root: {repo_root}")

    raw = yaml.safe_load(tile_cfg_path.read_text(encoding="utf-8")) or {}
    tile_config = TileConfigCI.from_dict(raw)

    if not tile_config.top_module:
        raise VeriFlowError("top_module is empty in tile_config.yaml")

    # ── Find RTL sources ──────────────────────────────────────────────────────
    src_dir = repo_root / "src"
    if not src_dir.exists():
        raise VeriFlowError(f"src/ directory not found at: {src_dir}")

    rtl_files = sorted(src_dir.glob("*.v"))
    if not rtl_files:
        raise VeriFlowError(f"No .v files found in src/")

    top_file = src_dir / f"{tile_config.top_module}.v"
    if not top_file.exists():
        raise VeriFlowError(
            f"No .v file found for top_module='{tile_config.top_module}' in src/"
        )

    # ── Setup directories ─────────────────────────────────────────────────────
    runs_dir  = repo_root / "runs"
    docs_dir  = repo_root / "docs"
    run_id    = _get_run_id(runs_dir)
    run_dir   = runs_dir / run_id
    today_str = date.today().isoformat()
    repo_name = repo_root.name
    tile_id   = repo_name  # e.g. ip_adder_tile

    run_dir.mkdir(parents=True, exist_ok=True)
    docs_dir.mkdir(parents=True, exist_ok=True)

    # Copy RTL snapshot to run dir
    run_src = run_dir / "src"
    run_src.mkdir(exist_ok=True)
    import shutil
    for f in rtl_files:
        shutil.copy2(f, run_src / f.name)

    print(f"[precheck] Tile     : {tile_config.tile_name} ({tile_id})")
    print(f"[precheck] Run      : {run_id}")
    print(f"[precheck] Commit   : {commit_sha[:7] if commit_sha else 'local'}")

    # ── Template files ────────────────────────────────────────────────────────
    template_dir  = Path(__file__).parent.parent / "template"
    tb_base_path  = template_dir / "tb_base.v"
    tb_tasks_path = template_dir / "tb_tasks.v"

    if not tb_base_path.exists():
        raise VeriFlowError(f"tb_base.v not found: {tb_base_path}")
    if not tb_tasks_path.exists():
        raise VeriFlowError(f"tb_tasks.v not found: {tb_tasks_path}")

    # ── Result accumulators ───────────────────────────────────────────────────
    conn_result   = "SKIPPED"
    synth_result  = "SKIPPED"
    synth_parsed  = {"cells": "", "warnings": "0", "errors": "0", "has_latches": False}

    conn_log_path  = run_dir / "connectivity.log"
    synth_log_path = run_dir / "synth.log"

    # ── Connectivity check ────────────────────────────────────────────────────
    print(f"[precheck] Running connectivity check...")
    conn_result = run_connectivity_check(
        rtl_files=rtl_files,
        tb_base_path=tb_base_path,
        tb_tasks_path=tb_tasks_path,
        top_module=tile_config.top_module,
        log_path=conn_log_path,
    )
    print(f"[precheck] Connectivity: {conn_result}")

    if conn_result == "FAIL":
        print(f"[precheck] Connectivity FAILED — stopping")
        _finalize(
            repo_root=repo_root, docs_dir=docs_dir, run_dir=run_dir,
            run_id=run_id, today_str=today_str, tile_id=tile_id,
            repo_name=repo_name, tile_config=tile_config,
            conn_result=conn_result, synth_result=synth_result,
            synth_parsed=synth_parsed, commit_sha=commit_sha,
            commit_author=commit_author, rtl_files=rtl_files,
        )
        raise VeriFlowError(f"Precheck FAILED — connectivity check did not pass")

    # ── Synthesis ─────────────────────────────────────────────────────────────
    print(f"[precheck] Running synthesis...")
    synth_result, synth_parsed = run_synthesis(
        rtl_files=rtl_files,
        top_module=tile_config.top_module,
        synth_log_path=synth_log_path,
    )
    print(f"[precheck] Synthesis: {synth_result}")

    # ── Finalize ──────────────────────────────────────────────────────────────
    _finalize(
        repo_root=repo_root, docs_dir=docs_dir, run_dir=run_dir,
        run_id=run_id, today_str=today_str, tile_id=tile_id,
        repo_name=repo_name, tile_config=tile_config,
        conn_result=conn_result, synth_result=synth_result,
        synth_parsed=synth_parsed, commit_sha=commit_sha,
        commit_author=commit_author, rtl_files=rtl_files,
    )


def _finalize(
    repo_root, docs_dir, run_dir, run_id, today_str,
    tile_id, repo_name, tile_config,
    conn_result, synth_result, synth_parsed,
    commit_sha, commit_author, rtl_files,
):
    cells  = synth_parsed.get("cells", "")
    status = "PASS" if conn_result == "PASS" and synth_result == "PASS" else "FAIL"

    # ── manifest.yaml ─────────────────────────────────────────────────────────
    manifest = {
        "tile_id":      tile_id,
        "run_id":       run_id,
        "date":         today_str,
        "commit":       commit_sha,
        "author":       commit_author,
        "tile_name":    tile_config.tile_name,
        "top_module":   tile_config.top_module,
        "shuttle":      tile_config.shuttle,
        "connectivity": conn_result,
        "synthesis":    synth_result,
        "cells":        cells,
        "status":       status,
    }
    _write_yaml(run_dir / "manifest.yaml", manifest)
    print(f"[precheck] Generated manifest.yaml")

    # ── summary.md ───────────────────────────────────────────────────────────
    cells_str  = f"{cells} cells" if cells else "-"
    status_sym = "PASS" if status == "PASS" else "FAIL"
    summary = f"""# Precheck Summary

**Tile:** {tile_config.tile_name}
**Run:** {run_id}
**Date:** {today_str}
**Commit:** {commit_sha[:7] if commit_sha else "-"}

---

| Stage | Result | Details |
|-------|--------|---------|
| Connectivity | {conn_result} | |
| Synthesis | {synth_result} | {cells_str} |

---

**Status: {status_sym}**
"""
    (run_dir / "summary.md").write_text(summary, encoding="utf-8")
    print(f"[precheck] Generated summary.md")

    # ── records.csv ───────────────────────────────────────────────────────────
    records_path = docs_dir / "records.csv"
    _append_record(records_path, {
        "run":          run_id,
        "date":         today_str,
        "commit":       commit_sha[:7] if commit_sha else "",
        "author":       commit_author,
        "connectivity": conn_result,
        "synthesis":    synth_result,
        "cells":        cells,
        "status":       status,
        "tile_id":      tile_id,
    })
    print(f"[precheck] Updated records.csv")

    # ── results.json ──────────────────────────────────────────────────────────
    results = {
        "tile_id":      tile_id,
        "shuttle":      tile_config.shuttle,
        "status":       status,
        "connectivity": conn_result,
        "synthesis":    synth_result,
        "cells":        int(cells) if cells else 0,
        "date":         today_str,
        "commit":       commit_sha,
        "author":       commit_author,
        "run":          run_id,
        "rtl_path":     f"runs/{run_id}/src",
    }
    (docs_dir / "results.json").write_text(
        json.dumps(results, indent=2), encoding="utf-8"
    )
    print(f"[precheck] Updated results.json")

    # ── netlist.svg ───────────────────────────────────────────────────────────
    from veriflow.generators.netlist_svg import generate_netlist_svg
    svg_ok = generate_netlist_svg(
        rtl_files=rtl_files,
        top_module=tile_config.top_module,
        output_path=docs_dir / "netlist.svg",
    )
    if svg_ok:
        print(f"[precheck] Generated netlist.svg")
    else:
        print(f"[precheck] netlist.svg skipped (netlistsvg not available)")

    # ── datasheet.pdf ─────────────────────────────────────────────────────────
    from veriflow.generators.datasheet import generate_datasheet_md, convert_md_to_pdf
    md_path = docs_dir / "datasheet.md"
    generate_datasheet_md(
        repo_name=repo_name,
        tile_config=tile_config,
        run_id=run_id,
        run_date=today_str,
        connectivity=conn_result,
        synthesis=synth_result,
        cells=cells,
        status=status,
        commit_sha=commit_sha,
        output_path=md_path,
    )
    pdf_ok = convert_md_to_pdf(md_path, docs_dir / "datasheet.pdf")
    if pdf_ok:
        md_path.unlink(missing_ok=True)
        print(f"[precheck] Generated datasheet.pdf")
    else:
        print(f"[precheck] datasheet.pdf skipped (pandoc not available)")

    # ── README.md ─────────────────────────────────────────────────────────────
    records = _read_records(docs_dir / "records.csv")
    badge_url = (
        f"https://github.com/{repo_root.name}/"
        f"actions/workflows/precheck.yml/badge.svg"
    )
    from veriflow.generators.readme_ci import generate_readme_ci
    generate_readme_ci(
        repo_name=repo_root.name,
        tile_config=tile_config,
        run_id=run_id,
        run_date=today_str,
        connectivity=conn_result,
        synthesis=synth_result,
        cells=cells,
        status=status,
        commit_sha=commit_sha,
        history_rows=list(reversed(records)),
        badge_url=badge_url,
        output_path=repo_root / "README.md",
    )
    print(f"[precheck] Updated README.md")

    print()
    if status == "PASS":
        print(f"Precheck PASSED.")
    else:
        print(f"Precheck FAILED.")
    print(f"  Run    : {run_id}")
    print(f"  Tile   : {tile_config.tile_name}")
    print(f"  Status : {status}")


def _write_yaml(path: Path, data: dict) -> None:
    lines = []
    for k, v in data.items():
        lines.append(f"{k}: \"{v}\"")
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
