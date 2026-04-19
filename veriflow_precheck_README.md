# veriflow-precheck

CI-adapted variant of [VeriFlow](https://github.com/tu-usuario/veriflow) for SemiCoLab IP tile repositories. Runs connectivity check and synthesis directly from the repo root, generates documentation, and reports results for integration with the SemiCoLab shuttle management system.

---

## Overview

`veriflow-precheck` is designed to be called from GitHub Actions in an `ip_<design_name>` tile repo. It does not require a local database — it reads directly from the repo structure and writes results back to it.

**What it runs:**
- Connectivity check (Icarus Verilog)
- Synthesis (Yosys)
- Simulation is always skipped — use [VeriFlow](https://github.com/tu-usuario/veriflow) locally for functional verification

**What it generates:**
- `runs/run-NNN/` — manifest, summary, RTL snapshot
- `docs/records.csv` — full run history
- `docs/results.json` — structured output for integration
- `docs/netlist.svg` — synthesized netlist diagram
- `docs/datasheet.pdf` — tile datasheet (pandoc)
- `README.md` — updated with badge, tile info, and run history

---

## Requirements

- Python 3.10+
- [OSS CAD Suite](https://github.com/YosysHQ/oss-cad-suite-build/releases) (`iverilog`, `yosys`)
- PyYAML: `pip install pyyaml`
- Node.js + netlistsvg: `npm install -g netlistsvg` *(for netlist SVG)*
- pandoc *(for datasheet PDF)*

---

## Repo Structure Expected

```
ip_<design_name>/
├── tile_config.yaml    ← tile metadata
├── src/
│   └── top_module.v    ← RTL files
└── .github/
    └── workflows/
        └── precheck.yml
```

---

## tile_config.yaml

```yaml
tile_name: ""
tile_author: ""
top_module: ""      # must match RTL filename
shuttle: ""         # optional — SemiCoLab shuttle identifier

description: |

ports: |

usage_guide: |

tb_description: |
```

---

## CLI Usage

```bash
python veriflow/cli.py precheck \
  --repo .  \
  --run-number 1 \
  --commit abc1234 \
  --author sebastian
```

| Argument | Description |
|---|---|
| `--repo` | Repo root path (default: `.`) |
| `--run-number` | CI run number — use `$GITHUB_RUN_NUMBER` |
| `--commit` | Commit SHA — use `$GITHUB_SHA` |
| `--author` | Commit author — use `$GITHUB_ACTOR` |

---

## Exit Codes

| Code | Condition |
|---|---|
| `0` | Precheck PASS |
| `1` | Precheck FAIL or unrecoverable error |

Note: exit code `1` on FAIL is intentional — it allows GitHub Actions to mark the workflow as failed and block merges if required.

---

## results.json Schema

```json
{
  "tile_id":      "ip_adder_tile",
  "shuttle":      "",
  "status":       "PASS",
  "connectivity": "PASS",
  "synthesis":    "PASS",
  "cells":        3,
  "date":         "2026-04-17",
  "commit":       "abc1234...",
  "author":       "sebastian",
  "run":          "run-001",
  "rtl_path":     "runs/run-001/src"
}
```

---

## Part of the SemiCoLab Ecosystem

```
TileWizard          → wraps generic IP RTL into SemiCoLab tile
VeriFlow (local)    → full functional verification with waveforms
veriflow-precheck   → CI gate: connectivity + synthesis
Docker Suite        → TileWizard + VeriFlow in a container
```

---

## Related Repos

- [veriflow](https://github.com/tu-usuario/veriflow) — local verification tool
- [semicolab-ip-tile-precheck](https://github.com/tu-usuario/semicolab-ip-tile-precheck) — GitHub Actions workflow
