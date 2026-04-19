from datetime import date
from pathlib import Path


def generate_readme_ci(
    repo_name: str,
    tile_config,
    run_id: str,
    run_date: str,
    connectivity: str,
    synthesis: str,
    cells: str,
    status: str,
    commit_sha: str,
    history_rows: list[dict],
    badge_url: str,
    output_path: Path,
) -> None:
    """
    Generate the tile README for CI mode.
    Includes badge, tile info card, netlist SVG, and precheck history table.
    """

    status_emoji = "✅" if status == "PASS" else "❌"
    cells_str = cells if cells else "-"

    # Build history table rows (newest first)
    history_md = ""
    for row in history_rows:
        e = "✅" if row["status"] == "PASS" else "❌"
        sha = row.get("commit", "")[:7]
        history_md += (
            f"| {row['run']} | {row['date']} | `{sha}` | "
            f"{row['connectivity']} | {row['synthesis']} | "
            f"{row.get('cells', '-')} | {e} {row['status']} |\n"
        )

    content = f"""# {repo_name}

![Precheck Status]({badge_url})

---

## Tile Information

| | |
|---|---|
| **Tile Name** | {tile_config.tile_name} |
| **Author** | {tile_config.tile_author} |
| **Top Module** | `{tile_config.top_module}` |
| **Shuttle** | {tile_config.shuttle if tile_config.shuttle else "-"} |
| **Cells** | {cells_str} |
| **Last Run** | {run_date} |
| **Status** | {status_emoji} {status} |

## Description

{tile_config.description.strip()}

## Port Convention

{tile_config.ports.strip()}

## Netlist

![Netlist](docs/netlist.svg)

📄 [Datasheet](docs/datasheet.pdf)

---

## Precheck History

| Run | Date | Commit | Connectivity | Synthesis | Cells | Status |
|-----|------|--------|--------------|-----------|-------|--------|
{history_md}
"""
    output_path.write_text(content, encoding="utf-8")
