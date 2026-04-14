#!/usr/bin/env python3
"""
gen_contest_lef.py — Generate contest_cells.lef for ISPD2012 circuits.

This generates ONLY the cell macros (no tech section).
It must be loaded AFTER asap7_tech_4x_201209.lef in Innovus.

Physical assumptions (matching ASAP7 conventions):
  - DATABASE MICRONS 4000 (matches ASAP7 tech LEF)
  - SITE: asap7sc7p5t  (size 0.216 x 1.08 um — defined in ASAP7 tech LEF)
  - CELL HEIGHT: 1.08 um (fixed)
  - CELL WIDTH: max(0.216, round(area) * 0.216) um
      area=1 → 0.216um, area=2 → 0.432um, area=4 → 0.864um, area=8 → 1.728um
  - VDD rail: M1 RECT 0.000 1.044 <width> 1.116  (ABUTMENT, matches ASAP7)
  - VSS rail: M1 RECT 0.000 -0.036 <width> 0.036  (ABUTMENT, matches ASAP7)
  - Signal pins: M1 thin rectangles at mid-cell height (evenly distributed)

Cell families and their pins (from contest.lib):
  in01  : inputs=[a],       output=o
  na02  : inputs=[a,b],     output=o
  na03  : inputs=[a,b,c],   output=o
  na04  : inputs=[a,b,c,d], output=o (also 'e' for na05 if present)
  no02  : inputs=[a,b],     output=o
  no03  : inputs=[a,b,c],   output=o
  no04  : inputs=[a,b,c,d], output=o
  ao12  : inputs=[a,b,c],   output=o  (A-and-B OR C)
  ao22  : inputs=[a,b,c,d], output=o  (A-and-B OR C-and-D)  — use 4 inputs
  oa12  : inputs=[a,b,c],   output=o  (A-or-B AND C)
  oa22  : inputs=[a,b,c,d], output=o
  ms00  : inputs=[d,ck],    output=o  (D flip-flop)
  vcc   : output=y  (tie-hi — dont_use, but must exist in LEF)
  vss   : output=y  (tie-lo)

Usage:
    python gen_contest_lef.py <contest.lib> <output_cells.lef>

The output LEF should be loaded AFTER the ASAP7 tech LEF in Innovus init_lef_file.
"""

import re
import sys
import math

# Physical constants matching ASAP7
SITE_NAME   = "asap7sc7p5t"
SITE_UNIT_W = 0.216   # um — minimum site width
CELL_HEIGHT = 1.08    # um
DB_UNIT     = 4000    # DATABASE MICRONS (matches ASAP7 tech LEF)
MFG_GRID    = 0.004   # um — MANUFACTURINGGRID from ASAP7 tech LEF

# M1 VDD/VSS rail extents (matching ASAP7 ABUTMENT pins exactly)
VDD_Y_LO    = 1.044
VDD_Y_HI    = 1.116
VSS_Y_LO    = -0.036
VSS_Y_HI    =  0.036

# Signal pin dimensions on M1
PIN_W = 0.072   # width (= 1 M1 track pitch at 4x scale)
PIN_H = 0.072   # height


def snap_to_grid(val, grid=MFG_GRID):
    """Snap a coordinate to the manufacturing grid."""
    return round(round(val / grid) * grid, 4)

# Cell family → pin list: (name, direction)
# Order: inputs first (left to right), then output last (right side)
FAMILY_PINS = {
    "in01": [("a", "INPUT"), ("o", "OUTPUT")],
    "na02": [("a", "INPUT"), ("b", "INPUT"), ("o", "OUTPUT")],
    "na03": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("o", "OUTPUT")],
    "na04": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("d", "INPUT"), ("o", "OUTPUT")],
    "no02": [("a", "INPUT"), ("b", "INPUT"), ("o", "OUTPUT")],
    "no03": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("o", "OUTPUT")],
    "no04": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("d", "INPUT"), ("o", "OUTPUT")],
    "ao12": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("o", "OUTPUT")],
    "ao22": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("d", "INPUT"), ("o", "OUTPUT")],
    "oa12": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("o", "OUTPUT")],
    "oa22": [("a", "INPUT"), ("b", "INPUT"), ("c", "INPUT"), ("d", "INPUT"), ("o", "OUTPUT")],
    "ms00": [("d", "INPUT"), ("ck", "INPUT"), ("o", "OUTPUT")],
    "vcc":  [("y", "OUTPUT")],
    "vss":  [("y", "OUTPUT")],
}

def get_family(cell_name):
    """Return the family prefix for a cell name."""
    for prefix in FAMILY_PINS:
        if cell_name.startswith(prefix):
            return prefix
    return None


def area_to_width(area_val):
    """
    Convert contest lib area (integer) to physical cell width.
    Width must be a multiple of SITE_UNIT_W (0.216 um).
    area=0 (vcc/vss) → 1 site; area=1 → 1 site; area=n → n sites (capped at 1 site minimum).
    """
    n_sites = max(1, int(round(area_val)))
    return round(n_sites * SITE_UNIT_W, 4)


def parse_lib(lib_path):
    """
    Parse contest.lib and return list of (cell_name, area) tuples.
    """
    cells = []
    cell_name = None
    area = None
    in_cell = False

    with open(lib_path, "r", errors="replace") as f:
        for line in f:
            m_begin = re.match(r"/\*\s*Begin cell:\s*(\S+)\s*\*/", line)
            if m_begin:
                cell_name = m_begin.group(1)
                area = None
                in_cell = True
                continue

            if in_cell and area is None:
                m_area = re.match(r"\s*area\s*:\s*([\d.]+)\s*;", line)
                if m_area:
                    area = float(m_area.group(1))

            m_end = re.match(r"/\*\s*End cell:\s*(\S+)\s*\*/", line)
            if m_end and in_cell:
                if cell_name and area is not None:
                    cells.append((cell_name, area))
                cell_name = None
                area = None
                in_cell = False

    return cells


def write_cell_lef(cells, out_path):
    """Write a cell-only LEF (no tech section — Innovus loads ASAP7 tech LEF first)."""

    with open(out_path, "w") as f:
        f.write("# Contest cell LEF for ISPD2012 benchmarks\n")
        f.write("# Load AFTER asap7_tech_4x_201209.lef\n")
        f.write("# Generated by gen_contest_lef.py\n\n")

        f.write("VERSION 5.8 ;\n")
        f.write("BUSBITCHARS \"[]\" ;\n")
        f.write("DIVIDERCHAR \"/\" ;\n\n")

        # UNITS must match ASAP7 tech LEF (DATABASE MICRONS 4000)
        f.write("UNITS\n")
        f.write("  DATABASE MICRONS 4000 ;\n")
        f.write("END UNITS\n\n")

        # SITE definition (ASAP7 tech LEF may not include it)
        f.write(f"SITE {SITE_NAME}\n")
        f.write(f"  CLASS CORE ;\n")
        f.write(f"  SIZE {SITE_UNIT_W} BY {CELL_HEIGHT} ;\n")
        f.write(f"END {SITE_NAME}\n\n")

        for cell_name, area in cells:
            family = get_family(cell_name)
            if family is None:
                print(f"  WARNING: unknown family for cell {cell_name}, skipping")
                continue

            pins = FAMILY_PINS[family]
            cw = area_to_width(area)
            ch = CELL_HEIGHT

            f.write(f"MACRO {cell_name}\n")
            f.write(f"  CLASS CORE ;\n")
            f.write(f"  ORIGIN 0 0 ;\n")
            f.write(f"  FOREIGN {cell_name} 0 0 ;\n")
            f.write(f"  SIZE {cw:.4f} BY {ch:.4f} ;\n")
            f.write(f"  SYMMETRY X Y ;\n")
            f.write(f"  SITE {SITE_NAME} ;\n")

            # ---- Signal pins on M1 ----
            # Place input pins in the lower half, output pin in upper half
            # Distribute horizontally, keeping margins from cell edges
            n_pins = len(pins)
            margin = PIN_W
            usable_w = max(cw - 2 * margin, PIN_W)
            step = usable_w / max(n_pins, 1)

            for idx, (pname, pdir) in enumerate(pins):
                # x center
                px = margin + idx * step
                px = min(px, cw - margin - PIN_W)
                px = max(px, margin)
                px = snap_to_grid(px)

                # y: inputs at ~30% height, outputs at ~70% height
                if pdir == "OUTPUT":
                    py = snap_to_grid(ch * 0.65)
                else:
                    py = snap_to_grid(ch * 0.25)

                # clamp to valid range (stay within cell, above VSS, below VDD)
                py_lo_limit = snap_to_grid(VSS_Y_HI + MFG_GRID)
                py_hi_limit = snap_to_grid(VDD_Y_LO - PIN_H - MFG_GRID)
                py = max(py, py_lo_limit)
                py = min(py, py_hi_limit)
                py = snap_to_grid(py)

                f.write(f"  PIN {pname}\n")
                f.write(f"    DIRECTION {pdir} ;\n")
                f.write(f"    USE SIGNAL ;\n")
                f.write(f"    PORT\n")
                f.write(f"      LAYER M1 ;\n")
                f.write(f"        RECT {px:.4f} {py:.4f} "
                        f"{px + PIN_W:.4f} {py + PIN_H:.4f} ;\n")
                f.write(f"    END\n")
                f.write(f"  END {pname}\n")

            # ---- VDD power rail (ABUTMENT — matches ASAP7 exactly) ----
            f.write(f"  PIN VDD\n")
            f.write(f"    DIRECTION INOUT ;\n")
            f.write(f"    USE POWER ;\n")
            f.write(f"    SHAPE ABUTMENT ;\n")
            f.write(f"    PORT\n")
            f.write(f"      LAYER M1 ;\n")
            f.write(f"        RECT 0.000 {VDD_Y_LO:.4f} {cw:.4f} {VDD_Y_HI:.4f} ;\n")
            f.write(f"    END\n")
            f.write(f"  END VDD\n")

            # ---- VSS ground rail (ABUTMENT — matches ASAP7 exactly) ----
            f.write(f"  PIN VSS\n")
            f.write(f"    DIRECTION INOUT ;\n")
            f.write(f"    USE GROUND ;\n")
            f.write(f"    SHAPE ABUTMENT ;\n")
            f.write(f"    PORT\n")
            f.write(f"      LAYER M1 ;\n")
            f.write(f"        RECT 0.000 {VSS_Y_LO:.4f} {cw:.4f} {VSS_Y_HI:.4f} ;\n")
            f.write(f"    END\n")
            f.write(f"  END VSS\n")

            # ---- OBS: block M1 between rails (avoids router using cell interior M1) ----
            obs_y_lo = round(VSS_Y_HI + 0.000, 4)
            obs_y_hi = round(VDD_Y_LO, 4)
            f.write(f"  OBS\n")
            f.write(f"    LAYER M1 ;\n")
            f.write(f"      RECT 0.000 {obs_y_lo:.4f} {cw:.4f} {obs_y_hi:.4f} ;\n")
            f.write(f"  END\n")

            f.write(f"END {cell_name}\n\n")

        f.write("END LIBRARY\n")


def main():
    if len(sys.argv) < 3:
        print(f"Usage: {sys.argv[0]} <contest.lib> <output_cells.lef>")
        sys.exit(1)

    lib_path = sys.argv[1]
    lef_path = sys.argv[2]

    print(f"Parsing {lib_path} ...")
    cells = parse_lib(lib_path)
    print(f"  Found {len(cells)} cells")

    # Summarize families
    from collections import Counter
    fam_counts = Counter()
    for cn, _ in cells:
        fam = get_family(cn)
        fam_counts[fam] += 1
    for fam, cnt in sorted(fam_counts.items()):
        print(f"  {fam}: {cnt} cells")

    print(f"Writing {lef_path} ...")
    write_cell_lef(cells, lef_path)
    print(f"Done. Cell LEF written to {lef_path}")
    print(f"")
    print(f"IMPORTANT: In Innovus init_lef_file, load in this order:")
    print(f"  1. asap7_tech_4x_201209.lef  (tech + SITE definition)")
    print(f"  2. {lef_path}  (contest cell macros)")


if __name__ == "__main__":
    main()
