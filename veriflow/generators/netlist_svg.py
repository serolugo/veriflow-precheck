import json
import subprocess
import tempfile
from pathlib import Path


def generate_netlist_svg(
    rtl_files: list[Path],
    top_module: str,
    output_path: Path,
) -> bool:
    """
    Generate a netlist SVG using Yosys + netlistsvg.
    Returns True if successful.
    """
    output_path.parent.mkdir(parents=True, exist_ok=True)

    # Step 1: Yosys generates JSON netlist
    json_path = Path(tempfile.mktemp(suffix=".json"))
    read_cmds = "\n".join(f"read_verilog {f.as_posix()}" for f in rtl_files)
    script = f"""
{read_cmds}
hierarchy -check -top {top_module}
proc
opt
write_json {json_path.as_posix()}
"""
    try:
        result = subprocess.run(
            ["yosys", "-p", script],
            capture_output=True,
            text=True,
        )
        if result.returncode != 0 or not json_path.exists():
            return False

        # Step 2: netlistsvg converts JSON to SVG
        result2 = subprocess.run(
            ["netlistsvg", str(json_path), "-o", str(output_path)],
            capture_output=True,
            text=True,
        )
        if result2.returncode == 0 and output_path.exists():
            # Inject white background for readability on dark themes
            svg = output_path.read_text(encoding="utf-8")
            svg = svg.replace(
                "<svg ",
                "<svg style=\"background-color:white;\" ",
                1
            )
            # Center the SVG
            svg = svg.replace(
                "<svg ",
                "<svg display=\"block\" margin=\"auto\" ",
                1
            )
            output_path.write_text(svg, encoding="utf-8")
            return True
        return False
    except FileNotFoundError:
        return False
    finally:
        json_path.unlink(missing_ok=True)
