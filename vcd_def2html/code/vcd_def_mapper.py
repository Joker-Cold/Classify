#!/usr/bin/env python3
"""VCD Signal → Physical Location Mapper

Maps VCD simulation signals to chip physical coordinates using DEF layout data.
Outputs CSV mapping table and optional Plotly HTML scatter plot.

Usage:
    python code/vcd_def_mapper.py --vcd VCD_PATH --def DEF_PATH --output CSV_PATH [--html HTML_PATH]
"""
import re
import csv
import json
import argparse
import sys
import os

sys.path.insert(0, os.path.dirname(__file__))
from parse_vcd_signal import VCDSignalParser


# ── DEF Parsers (streaming, line-by-line) ─────────────────────────────


def parse_def_units(def_path: str) -> int:
    """Extract UNITS DISTANCE MICRONS value from DEF header."""
    with open(def_path, "r", encoding="utf-8") as f:
        for line in f:
            m = re.match(r"UNITS DISTANCE MICRONS (\d+)", line.strip())
            if m:
                return int(m.group(1))
            if line.strip().startswith("COMPONENTS") or line.strip().startswith("PINS"):
                break
    return 4000  # default


def parse_def_components(def_path: str) -> dict:
    """Parse COMPONENTS section → {inst_name: (x, y, cell_type)}.

    Format: - NAME TYPE [+ ...] + PLACED ( X Y ) ORIENT
    May span multiple lines, terminated by ';'.
    """
    components = {}
    in_section = False
    buf = ""
    with open(def_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not in_section:
                if s.startswith("COMPONENTS "):
                    in_section = True
                continue
            if s == "END COMPONENTS":
                break
            buf += " " + s
            if ";" not in s:
                continue
            # Process complete entry
            entry = buf.strip()
            buf = ""
            # Pattern: - INST_NAME CELL_TYPE ... PLACED ( X Y ) ORIENT
            m = re.match(r"^-\s+(\S+)\s+(\S+)", entry)
            if not m:
                continue
            inst_name = m.group(1).replace("\\[", "[").replace("\\]", "]")
            cell_type = m.group(2)
            pm = re.search(r"PLACED\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", entry)
            if not pm:
                pm = re.search(r"FIXED\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", entry)
            if pm:
                x, y = int(pm.group(1)), int(pm.group(2))
                components[inst_name] = (x, y, cell_type)
    return components


def parse_def_pins(def_path: str) -> dict:
    """Parse PINS section → {pin_name: (x, y, direction)}.

    Format: - PIN_NAME + NET ... + DIRECTION dir ... + PLACED ( X Y ) ORIENT ;
    May span multiple lines.
    """
    pins = {}
    in_section = False
    buf = ""
    with open(def_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not in_section:
                if s.startswith("PINS "):
                    in_section = True
                continue
            if s == "END PINS":
                break
            buf += " " + s
            if ";" not in s:
                continue
            entry = buf.strip()
            buf = ""
            m = re.match(r"^-\s+(\S+)", entry)
            if not m:
                continue
            pin_name = m.group(1)
            # Unescape DEF bus notation: \[  \] → [ ]
            pin_name = pin_name.replace("\\[", "[").replace("\\]", "]")
            # Direction
            dm = re.search(r"DIRECTION\s+(\S+)", entry)
            direction = dm.group(1) if dm else "UNKNOWN"
            # Position
            pm = re.search(r"PLACED\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", entry)
            if not pm:
                pm = re.search(r"FIXED\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", entry)
            if pm:
                x, y = int(pm.group(1)), int(pm.group(2))
                pins[pin_name] = (x, y, direction)
    return pins


def parse_def_nets(def_path: str) -> dict:
    """Parse NETS section → {net_name: {"conns": [(inst,pin),...], "first_route": (x,y)|None}}.

    Only extracts connection list and first routing coordinate per net.
    """
    nets = {}
    in_section = False
    current_net = None
    conns = []
    first_route = None
    with open(def_path, "r", encoding="utf-8") as f:
        for line in f:
            s = line.strip()
            if not in_section:
                if s.startswith("NETS "):
                    in_section = True
                continue
            if s == "END NETS":
                # Save last net
                if current_net is not None:
                    nets[current_net] = {"conns": conns, "first_route": first_route}
                break
            # New net definition
            if s.startswith("- "):
                # Save previous net
                if current_net is not None:
                    nets[current_net] = {"conns": conns, "first_route": first_route}
                # Parse net name
                parts = s.split()
                net_name = parts[1] if len(parts) > 1 else ""
                net_name = net_name.replace("\\[", "[").replace("\\]", "]")
                current_net = net_name
                conns = []
                first_route = None
                continue
            if current_net is None:
                continue
            # Connection lines come before routing; skip routing lines for connections
            is_route_line = ("ROUTED" in s or s.startswith("NEW ") or
                             s.startswith("+ ROUTED") or s.startswith("+ SOURCE"))
            if not is_route_line:
                # Connection line: ( inst pin ) or ( PIN pin_name )
                for cm in re.finditer(r"\(\s*(\S+)\s+(\S+)\s*\)", s):
                    inst = cm.group(1).replace("\\[", "[").replace("\\]", "]")
                    pin = cm.group(2).replace("\\[", "[").replace("\\]", "]")
                    conns.append((inst, pin))
            # First routing coordinate
            if first_route is None and "ROUTED" in s:
                rm = re.search(r"ROUTED\s+\S+\s*\(\s*(-?\d+)\s+(-?\d+)\s*\)", s)
                if rm:
                    first_route = (int(rm.group(1)), int(rm.group(2)))
    return nets


# ── VCD Signal Extraction ─────────────────────────────────────────────


def parse_vcd_signals(vcd_path: str) -> list:
    """Extract VCD signal metadata using VCDSignalParser.

    Returns list of {name, full_name, scope, width, type, symbol}.
    Scope is extracted from full_name by removing the signal name suffix.
    """
    parser = VCDSignalParser(vcd_path)
    parser.parse_header()
    signals = parser.list_unique_signals(exclude_params=True, exclude_tasks=True)
    # Add scope field
    for sig in signals:
        fn = sig["full_name"]
        base = sig["name"]
        # scope = full_name minus trailing .base_name
        if "." in fn:
            # full_name uses '.' as separator
            parts = fn.rsplit(".", 1)
            sig["scope"] = parts[0]
        else:
            sig["scope"] = ""
    return signals


# ── Core Mapping Logic ────────────────────────────────────────────────


def _full_name_to_def_path(full_name: str, top_scope: str) -> str:
    """Convert VCD full_name to DEF-compatible hierarchical path.

    VCD full_name uses '.' as separator: test.u0.u0.K3 [1:48]
    DEF uses '/' as separator: u0/K3[1]

    Steps:
    1. Strip testbench scope (top_scope, e.g. 'test')
    2. Strip DES3 top instance (next level, e.g. 'u0')
    3. Convert '.' to '/'
    4. Extract base signal name (last component)
    """
    parts = full_name.split(".")
    # Strip testbench
    if parts and parts[0] == top_scope:
        parts = parts[1:]
    # Strip DES3 top instance
    if parts:
        parts = parts[1:]
    return "/".join(parts)


def _vcd_name_to_base(name: str) -> str:
    """Extract base signal name from VCD signal name.

    'K3 [1:48]' → 'K3'  (bus signal, remove bit range)
    'FE_PHN8655_xxx' → 'FE_PHN8655_xxx'
    """
    # Remove bit range notation like ' [1:48]' or ' [63:0]'
    m = re.match(r"^(.+?)\s*\[\d+:\d+\]$", name)
    if m:
        return m.group(1)
    return name


def build_mapping(vcd_signals: list, components: dict, pins: dict, nets: dict,
                  top_scope: str, units: int) -> list:
    """Map each VCD signal to physical coordinates.

    Returns list of dicts with: signal_name, scope, width, x_um, y_um, source_type, cell_type
    """
    # Net driver cell lookup: net_name -> driver component
    net_driver_comp = {}
    for net_name, info in nets.items():
        for inst, pin in info["conns"]:
            if inst == "PIN":
                continue
            if pin in ("Y", "Q", "QN", "Z", "ZN", "CO", "S"):
                net_driver_comp[net_name] = inst
                break

    results = []
    matched = 0
    for sig in vcd_signals:
        name = sig["name"]
        full_name = sig["full_name"]
        scope = sig["scope"]
        width = sig["width"]

        # Derive DEF path from full_name (not disambiguated name)
        def_path = _full_name_to_def_path(full_name, top_scope)
        # def_path might be "u0/K3 [1:48]" - get base without bit range
        base_name = _vcd_name_to_base(def_path.rsplit("/", 1)[-1] if "/" in def_path else def_path)
        # def_prefix is the hierarchy part
        if "/" in def_path:
            def_prefix = def_path.rsplit("/", 1)[0]
        else:
            def_prefix = ""

        x, y, source_type, cell_type = None, None, "", ""

        # Strategy 1: Direct component match (exact path)
        if def_path in components:
            x, y, cell_type = components[def_path]
            source_type = "component"

        # Strategy 2: Pin match (top-level ports like desOut[63])
        if x is None and base_name in pins:
            x, y, direction = pins[base_name]
            source_type = "pin"
            cell_type = direction

        # Strategy 3: Net match - look in NETS, use driver cell coords
        if x is None:
            net_key = def_path
            if net_key in nets:
                driver = net_driver_comp.get(net_key)
                if driver and driver in components:
                    x, y, cell_type = components[driver]
                    source_type = "net_driver"
                elif nets[net_key]["first_route"]:
                    x, y = nets[net_key]["first_route"]
                    source_type = "net_route"

        # Strategy 3b: Parent component match (ISPD2012 flat designs)
        # VCD: tb.u0.inst.pin → def_path = "inst/pin" → match "inst" as component
        if x is None and def_prefix and def_prefix in components:
            x, y, cell_type = components[def_prefix]
            source_type = "parent_component"

        # Strategy 4: FE_PHN net → FE_PHC component (PHN→PHC)
        if x is None and "FE_PHN" in base_name:
            phc_name = base_name.replace("FE_PHN", "FE_PHC")
            phc_path = (def_prefix + "/" + phc_name) if def_prefix else phc_name
            if phc_path in components:
                x, y, cell_type = components[phc_path]
                source_type = "phc_component"

        # Strategy 5: For bus signals, try individual bit nets
        # VCD 'K3 [1:48]' width=48 → DEF nets 'u0/K3[1]'..'u0/K3[48]'
        # Use first matching net's coordinate as representative
        if x is None and width > 1:
            for bit in range(width):
                bit_net = (def_prefix + "/" + base_name + f"[{bit}]") if def_prefix else (base_name + f"[{bit}]")
                if bit_net in nets:
                    driver = net_driver_comp.get(bit_net)
                    if driver and driver in components:
                        x, y, cell_type = components[driver]
                        source_type = "bus_net_driver"
                    elif nets[bit_net]["first_route"]:
                        x, y = nets[bit_net]["first_route"]
                        source_type = "bus_net_route"
                    break
                if bit_net in components:
                    x, y, cell_type = components[bit_net]
                    source_type = "bus_component"
                    break

        # Convert to um
        x_um = round(x / units, 4) if x is not None else None
        y_um = round(y / units, 4) if x is not None else None

        if x is not None:
            matched += 1

        results.append({
            "signal_name": name,
            "scope": scope,
            "width": width,
            "x_um": x_um,
            "y_um": y_um,
            "source_type": source_type,
            "cell_type": cell_type,
        })

    print(f"Mapped {matched}/{len(vcd_signals)} signals to physical locations")
    return results


# ── Output ────────────────────────────────────────────────────────────


def write_csv(results: list, output_path: str):
    """Write mapping results to CSV."""
    fieldnames = ["signal_name", "scope", "width", "x_um", "y_um", "source_type", "cell_type"]
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=fieldnames)
        writer.writeheader()
        for row in results:
            writer.writerow(row)
    print(f"CSV written: {output_path} ({len(results)} rows)")


def write_html(results: list, html_path: str):
    """Generate Plotly scatter plot of signal locations."""
    # Filter to signals with coordinates
    mapped = [r for r in results if r["x_um"] is not None]
    if not mapped:
        print("No mapped signals to plot")
        return

    xs = [r["x_um"] for r in mapped]
    ys = [r["y_um"] for r in mapped]
    names = [r["signal_name"] for r in mapped]
    sources = [r["source_type"] for r in mapped]

    # Color by source type
    source_types = sorted(set(sources))
    color_map = {s: i for i, s in enumerate(source_types)}
    colors = [color_map[s] for s in sources]

    trace = {
        "x": xs, "y": ys,
        "text": [f"{n}<br>{s}" for n, s in zip(names, sources)],
        "mode": "markers",
        "type": "scattergl",
        "marker": {
            "size": 3,
            "color": colors,
            "colorscale": "Viridis",
            "opacity": 0.6,
        },
        "hovertemplate": "%{text}<br>(%{x:.2f}, %{y:.2f}) um<extra></extra>",
    }
    data_json = json.dumps([trace])
    source_summary = ", ".join(f"{s}({sum(1 for x in sources if x==s)})" for s in source_types)

    html = f"""<!DOCTYPE html>
<html>
<head>
    <title>VCD Signal Physical Location Map</title>
    <script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
    <style>
        body {{ margin: 0; font-family: sans-serif; }}
        #plot {{ width: 100vw; height: 100vh; }}
        #stats {{ position: fixed; top: 10px; right: 10px; background: rgba(255,255,255,0.9);
                  padding: 10px; border-radius: 5px; font-size: 13px; z-index: 1000; }}
    </style>
</head>
<body>
<div id="stats">
    Total signals: {len(results)}<br>
    Mapped: {len(mapped)} ({100*len(mapped)//len(results)}%)<br>
    Source types: {source_summary}
</div>
<div id="plot"></div>
<script>
var data = {data_json};
var layout = {{
    title: "VCD Signal Physical Location ({len(mapped)} signals)",
    xaxis: {{ title: "X (um)", scaleanchor: "y" }},
    yaxis: {{ title: "Y (um)" }},
    hovermode: "closest",
    margin: {{ t: 50, l: 60, r: 20, b: 50 }}
}};
Plotly.newPlot("plot", data, layout, {{ responsive: true }});
</script>
</body>
</html>"""
    with open(html_path, "w", encoding="utf-8") as f:
        f.write(html)
    print(f"HTML written: {html_path}")


# ── CLI ───────────────────────────────────────────────────────────────


def main():
    p = argparse.ArgumentParser(description="Map VCD signals to physical chip locations using DEF data")
    p.add_argument("--vcd", required=True, help="VCD file path")
    p.add_argument("--def", dest="def_path", required=True, help="DEF file path")
    p.add_argument("--output", required=True, help="Output CSV path")
    p.add_argument("--html", help="Optional HTML scatter plot output")
    args = p.parse_args()

    print(f"Parsing DEF units from {args.def_path}...")
    units = parse_def_units(args.def_path)
    print(f"  UNITS DISTANCE MICRONS = {units}")

    print(f"Parsing DEF COMPONENTS...")
    components = parse_def_components(args.def_path)
    print(f"  {len(components)} components")

    print(f"Parsing DEF PINS...")
    pins = parse_def_pins(args.def_path)
    print(f"  {len(pins)} pins")

    print(f"Parsing DEF NETS...")
    nets = parse_def_nets(args.def_path)
    print(f"  {len(nets)} nets")

    print(f"Parsing VCD signals from {args.vcd}...")
    vcd_parser = VCDSignalParser(args.vcd)
    vcd_parser.parse_header()
    vcd_signals = parse_vcd_signals(args.vcd)
    print(f"  {len(vcd_signals)} unique signals")

    print("Building signal → location mapping...")
    results = build_mapping(vcd_signals, components, pins, nets,
                            vcd_parser.top_scope, units)

    os.makedirs(os.path.dirname(os.path.abspath(args.output)), exist_ok=True)
    write_csv(results, args.output)

    if args.html:
        os.makedirs(os.path.dirname(os.path.abspath(args.html)), exist_ok=True)
        write_html(results, args.html)

    # Summary
    mapped = sum(1 for r in results if r["x_um"] is not None)
    by_source = {}
    for r in results:
        st = r["source_type"] or "unmapped"
        by_source[st] = by_source.get(st, 0) + 1
    print("\nSummary:")
    for st, cnt in sorted(by_source.items(), key=lambda x: -x[1]):
        print(f"  {st}: {cnt}")


if __name__ == "__main__":
    main()
