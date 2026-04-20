"""
VeriFlow Precheck Command
Designed for CI use in semicolab IP tile repos.
Runs connectivity check + synthesis, generates documentation.
"""

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


def _get_run_id(run_number: str) -> str:
    return f"run-{int(run_number):03d}"


def cmd_precheck(
    repo_root: Path,
    run_number: str,
    commit_sha: str = "",
    commit_author: str = "",
) -> None:
    """Run SemiCoLab IP tile precheck from the repo root."""

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
        raise VeriFlowError("No .v files found in src/")

    top_file = src_dir / f"{tile_config.top_module}.v"
    if not top_file.exists():
        raise VeriFlowError(
            f"No .v file found for top_module='{tile_config.top_module}' in src/"
        )

    # ── Setup directories ─────────────────────────────────────────────────────
    docs_dir  = repo_root / "docs"
    logs_dir  = repo_root / "logs"
    run_id    = _get_run_id(run_number)
    today_str = date.today().isoformat()
    # Use GITHUB_REPOSITORY (owner/repo) to get correct repo name in CI
    github_repo = os.environ.get("GITHUB_REPOSITORY", "")
    repo_name = github_repo.split("/")[-1] if github_repo else repo_root.name
    tile_id   = repo_name

    docs_dir.mkdir(parents=True, exist_ok=True)
    logs_dir.mkdir(parents=True, exist_ok=True)

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
    conn_result  = "SKIPPED"
    synth_result = "SKIPPED"
    synth_parsed = {"cells": "", "warnings": "0", "errors": "0", "has_latches": False}

    conn_log_path  = logs_dir / "connectivity.log"
    synth_log_path = logs_dir / "synth.log"

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
        print(f"[precheck] Connectivity FAILED — generating report and stopping")
        _finalize(
            repo_root=repo_root, docs_dir=docs_dir,
            run_id=run_id, today_str=today_str,
            tile_id=tile_id, repo_name=repo_name, tile_config=tile_config,
            conn_result=conn_result, synth_result="SKIPPED",
            synth_parsed={"cells": "", "warnings": "0", "errors": "0", "has_latches": False},
            commit_sha=commit_sha, commit_author=commit_author, rtl_files=rtl_files,
        )
        raise VeriFlowError("Precheck FAILED — connectivity check did not pass")

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
        repo_root=repo_root, docs_dir=docs_dir,
        run_id=run_id, today_str=today_str,
        tile_id=tile_id, repo_name=repo_name, tile_config=tile_config,
        conn_result=conn_result, synth_result=synth_result,
        synth_parsed=synth_parsed, commit_sha=commit_sha,
        commit_author=commit_author, rtl_files=rtl_files,
    )


def _finalize(
    repo_root, docs_dir, run_id, today_str,
    tile_id, repo_name, tile_config,
    conn_result, synth_result, synth_parsed,
    commit_sha, commit_author, rtl_files,
):
    cells  = synth_parsed.get("cells", "")
    status = "PASS" if conn_result == "PASS" and synth_result == "PASS" else "FAIL"
    cells_str = f"{cells} cells" if cells else "-"

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
        "rtl_path":     "src",
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
    from veriflow.generators.datasheet import generate_datasheet_md, convert_html_to_pdf
    html_path = docs_dir / "datasheet.html"
    generate_datasheet_md(
        repo_name=repo_name,
        tile_config=tile_config,
        run_date=today_str,
        connectivity=conn_result,
        synthesis=synth_result,
        cells=cells,
        status=status,
        commit_sha=commit_sha,
        output_path=html_path,
    )
    pdf_ok = convert_html_to_pdf(html_path, docs_dir / "datasheet.pdf")
    if pdf_ok:
        html_path.unlink(missing_ok=True)
        print(f"[precheck] Generated datasheet.pdf")
    else:
        print(f"[precheck] datasheet.pdf skipped (WeasyPrint not available)")

    # ── README.md ─────────────────────────────────────────────────────────────
    github_repository = os.environ.get("GITHUB_REPOSITORY", repo_root.name)
    badge_url = (
        f"https://github.com/{github_repository}/"
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
        badge_url=badge_url,
        output_path=repo_root / "README.md",
    )
    print(f"[precheck] Updated README.md")

    print()
    print(f"Precheck {'PASSED' if status == 'PASS' else 'FAILED'}.")
    print(f"  Run    : {run_id}")
    print(f"  Tile   : {tile_config.tile_name}")
    print(f"  Status : {status}")


def _write_yaml(path: Path, data: dict) -> None:
    lines = [f'{k}: "{v}"' for k, v in data.items()]
    path.write_text("\n".join(lines) + "\n", encoding="utf-8")
