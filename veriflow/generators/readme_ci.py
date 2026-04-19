from pathlib import Path


def _format_ports(ports_text: str) -> str:
    """Format ports as a markdown list, one per line."""
    lines = [l.strip() for l in ports_text.strip().splitlines() if l.strip()]
    return "\n".join(f"- `{l}`" for l in lines)


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
    badge_url: str,
    output_path: Path,
) -> None:
    """Generate the tile README for CI mode."""

    status_emoji = "✅" if status == "PASS" else "❌"
    cells_str = cells if cells else "-"
    ports_md = _format_ports(tile_config.ports) if tile_config.ports.strip() else "-"

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

## Ports

{ports_md}

## Usage Guide

{tile_config.usage_guide.strip()}

## Netlist

![Netlist](docs/netlist.svg)

📄 [Datasheet](docs/datasheet.pdf)
"""
    output_path.write_text(content, encoding="utf-8")
