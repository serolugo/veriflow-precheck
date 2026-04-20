from pathlib import Path


def _parse_ports(ports_text: str) -> list[tuple[str, str]]:
    """Parse port lines into (port_name, description) tuples."""
    ports = []
    for line in ports_text.strip().splitlines():
        line = line.strip()
        if not line:
            continue
        if " - " in line:
            name, desc = line.split(" - ", 1)
        elif " — " in line:
            name, desc = line.split(" — ", 1)
        else:
            name, desc = line, ""
        ports.append((name.strip(), desc.strip()))
    return ports


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
    shuttle_str = tile_config.shuttle if tile_config.shuttle else "-"
    commit_str = commit_sha[:7] if commit_sha else "-"

    # Build ports grid as HTML table (2 columns)
    ports = _parse_ports(tile_config.ports)
    if ports:
        rows = ""
        for i in range(0, len(ports), 2):
            left_name, left_desc = ports[i]
            if i + 1 < len(ports):
                right_name, right_desc = ports[i + 1]
                right_td = f"<td><code>{right_name}</code> — {right_desc}</td>"
            else:
                right_td = "<td></td>"
            rows += f"<tr><td><code>{left_name}</code> — {left_desc}</td>{right_td}</tr>\n"
        ports_section = f"""<table>
{rows}</table>"""
    else:
        ports_section = "_No ports defined._"

    # Usage guide — preserve line breaks
    usage_lines = tile_config.usage_guide.strip().splitlines()
    usage_md = "  \n".join(usage_lines)

    content = f"""# {repo_name}

![Precheck Status]({badge_url})
![Cells](https://img.shields.io/badge/Cells-{cells_str}-blue)
![Status](https://img.shields.io/badge/Status-{status}-{'brightgreen' if status == 'PASS' else 'red'})

---

**{tile_config.tile_name}** · {tile_config.tile_author} · `{tile_config.top_module}` · Shuttle: {shuttle_str}

{tile_config.description.strip()}

---

## Ports

{ports_section}

## Usage guide

{usage_md}

---

## Precheck result

| Stage | Result |
|---|---|
| Connectivity | {connectivity} |
| Synthesis | {synthesis} |
| Cells | {cells_str} |
| **Status** | **{status_emoji} {status}** |

Last run: `{run_id}` · Commit: `{commit_str}` · {run_date}

---

## Netlist

![Netlist](docs/netlist.svg)

📄 [Datasheet](docs/datasheet.pdf) · 📊 [results.json](docs/results.json)
"""
    output_path.write_text(content, encoding="utf-8")
