#!/usr/bin/env python3
"""VCD Signal Parser - Core Module
Parses VCD (Value Change Dump) files and extracts signal waveforms.
"""
import re
import argparse
from typing import Dict, List, Tuple, Optional


class VCDSignalParser:
    """VCD file parser: extracts signal waveforms and metadata."""

    def __init__(self, vcd_path: str):
        self.vcd_path = vcd_path
        self.signal_table: Dict[str, str] = {}   # signal_name -> symbol
        self.symbol_table: Dict[str, dict] = {}  # symbol -> {name,type,width,full_name,scope_type}
        self.scopes: List[str] = []
        self.scope_types: List[str] = []  # parallel to scopes: "module","task", etc.
        self.current_scope = ""
        self.current_scope_type = "module"
        self.top_scope = ""
        self.timescale = "1 ns"
        self._header_parsed = False

    # ── Header parsing ────────────────────────────────────────────────

    def parse_header(self) -> None:
        """Parse VCD header: build signal/symbol tables and read metadata."""
        if self._header_parsed:
            return
        collecting = None
        buf: List[str] = []
        with open(self.vcd_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s.startswith("$enddefinitions"):
                    break
                if collecting:
                    if "$end" in s:
                        frag = s.replace("$end", "").strip()
                        if frag:
                            buf.append(frag)
                        if collecting == "timescale":
                            self.timescale = " ".join(buf).strip()
                        collecting = None
                        buf = []
                    else:
                        buf.append(s)
                elif "$timescale" in s:
                    inline = s.replace("$timescale", "").strip()
                    if "$end" in inline:
                        self.timescale = inline.replace("$end", "").strip()
                    elif inline:
                        collecting = "timescale"
                        buf = [inline]
                    else:
                        collecting = "timescale"
                        buf = []
                else:
                    self._parse_header_line(s)
        self._header_parsed = True

    def _parse_header_line(self, line: str) -> None:
        if line.startswith("$scope"):
            parts = line.split()
            if len(parts) >= 3:
                scope_type = parts[1]  # module, task, function, begin
                sn = parts[2]
                self.scopes.append(sn)
                self.scope_types.append(scope_type)
                self.current_scope = ".".join(self.scopes)
                self.current_scope_type = scope_type
                if not self.top_scope:
                    self.top_scope = sn
        elif line.startswith("$upscope"):
            if self.scopes:
                self.scopes.pop()
                self.scope_types.pop()
                self.current_scope = ".".join(self.scopes) if self.scopes else ""
                self.current_scope_type = self.scope_types[-1] if self.scope_types else "module"
        elif line.startswith("$var"):
            self._parse_var_definition(line)

    def _parse_var_definition(self, line: str) -> None:
        parts = line.split()
        if len(parts) < 5:
            return
        if parts[0] == "$var":
            parts = parts[1:]
        if parts and parts[-1] == "$end":
            parts = parts[:-1]
        if len(parts) < 4:
            return
        var_type = parts[0]
        try:
            width = int(parts[1])
        except ValueError:
            return
        symbol = parts[2]
        signal_name = " ".join(parts[3:])
        full_name = (self.current_scope + "." + signal_name) if self.current_scope else signal_name
        self.signal_table[signal_name] = symbol
        self.signal_table[full_name] = symbol
        # Determine the innermost scope type containing this variable
        in_task = any(st in ("task", "function", "begin") for st in self.scope_types)
        self.symbol_table[symbol] = {
            "name": signal_name,
            "full_name": full_name,
            "type": var_type,
            "width": width,
            "scope_type": self.current_scope_type,
            "in_task": in_task,
        }

    # ── Signal access ─────────────────────────────────────────────────

    def list_signals(self) -> List[str]:
        """All signal names (base + full hierarchical)."""
        return list(self.signal_table.keys())

    def list_base_signals(self) -> List[str]:
        """Deduplicated base signal names (no scope prefix), sorted."""
        seen: set = set()
        result: List[str] = []
        for name in self.signal_table:
            base = name.split(".")[-1] if "." in name else name
            if base not in seen:
                seen.add(base)
                result.append(base)
        return sorted(result)

    def list_unique_signals(self, exclude_params: bool = True,
                            exclude_tasks: bool = True) -> List[dict]:
        """Return one entry per unique VCD symbol, with disambiguated names.

        Each entry: {name, full_name, type, width, symbol, scope_type, in_task}
        Signals with the same base name but different symbols get their
        full_name used as the 'name' key to avoid collisions.
        """
        if not self._header_parsed:
            self.parse_header()

        # Collect all symbols
        entries = []
        for sym, info in self.symbol_table.items():
            if exclude_params and info["type"] == "parameter":
                continue
            if exclude_tasks and info.get("in_task", False):
                continue
            entries.append({
                "name": info["name"],
                "full_name": info["full_name"],
                "type": info["type"],
                "width": info["width"],
                "symbol": sym,
                "scope_type": info.get("scope_type", "module"),
                "in_task": info.get("in_task", False),
            })

        # Disambiguate: if multiple entries share the same base name,
        # use full_name (strip top scope prefix for readability)
        from collections import Counter
        name_counts = Counter(e["name"] for e in entries)
        for e in entries:
            if name_counts[e["name"]] > 1:
                # Use full_name but strip the top scope for brevity
                fn = e["full_name"]
                prefix = self.top_scope + "."
                e["name"] = fn[len(prefix):] if fn.startswith(prefix) else fn

        return sorted(entries, key=lambda e: e["name"])

    def get_signal_info(self, signal_name: str) -> Optional[dict]:
        """Return {name, full_name, type, width, symbol} or None."""
        sym = self._resolve_symbol(signal_name)
        if sym is None:
            return None
        info = dict(self.symbol_table[sym])
        info["symbol"] = sym
        return info

    def _resolve_symbol(self, signal_name: str) -> Optional[str]:
        for name, sym in self.signal_table.items():
            if name == signal_name or name.endswith("." + signal_name):
                return sym
        return None

    # ── Single-signal extraction (streaming) ─────────────────────────

    def extract_waveform(self, signal_name: str,
                         start_time: Optional[int] = None,
                         end_time: Optional[int] = None) -> dict:
        """Stream VCD and extract one signal. Use parse_all_waveforms() for bulk."""
        if not self._header_parsed:
            self.parse_header()
        sym = self._resolve_symbol(signal_name)
        if sym is None:
            raise ValueError("Signal not found: " + signal_name +
                             ". Available: " + str(self.list_base_signals()))
        info = self.symbol_table[sym]
        waveform: List[Tuple[int, str]] = []
        current_time = 0
        in_val = False
        with open(self.vcd_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s.startswith("$enddefinitions"):
                    in_val = True
                    continue
                if not in_val:
                    continue
                if s.startswith("#"):
                    try:
                        t = int(s[1:])
                        if end_time is not None and t > end_time:
                            break
                        current_time = t
                    except ValueError:
                        pass
                    continue
                if s.startswith("$"):
                    continue
                if start_time is not None and current_time < start_time:
                    continue
                val = self._parse_value_change(s, sym)
                if val is not None:
                    waveform.append((current_time, val))
        return {"signal": signal_name, "full_name": info["full_name"],
                "type": info["type"], "width": info["width"], "waveform": waveform}

    # ── All-signal extraction (single pass) ──────────────────────────

    def parse_all_waveforms(self, exclude_params: bool = False,
                            exclude_tasks: bool = False) -> Dict[str, List[Tuple[int, str]]]:
        """Parse entire VCD in ONE pass. Returns {name: [(time,value),...]}.

        When exclude_params/exclude_tasks are False (default), includes all
        signals for backward compatibility. When True, filters them out.
        Disambiguates names when multiple symbols share the same base name.
        """
        if not self._header_parsed:
            self.parse_header()

        # Build symbol -> display_name map with collision detection
        from collections import Counter

        # First pass: assign base names
        sym_to_name: Dict[str, str] = {}
        for sym, info in self.symbol_table.items():
            if exclude_params and info["type"] == "parameter":
                continue
            if exclude_tasks and info.get("in_task", False):
                continue
            sym_to_name[sym] = info["name"]

        # Second pass: disambiguate collisions
        name_counts = Counter(sym_to_name.values())
        for sym in list(sym_to_name.keys()):
            name = sym_to_name[sym]
            if name_counts[name] > 1:
                fn = self.symbol_table[sym]["full_name"]
                prefix = self.top_scope + "."
                sym_to_name[sym] = fn[len(prefix):] if fn.startswith(prefix) else fn

        waveforms: Dict[str, List[Tuple[int, str]]] = {n: [] for n in sym_to_name.values()}
        current_time = 0
        in_val = False
        with open(self.vcd_path, "r", encoding="utf-8") as f:
            for line in f:
                s = line.strip()
                if not s:
                    continue
                if s.startswith("$enddefinitions"):
                    in_val = True
                    continue
                if not in_val:
                    continue
                if s.startswith("#"):
                    try:
                        current_time = int(s[1:])
                    except ValueError:
                        pass
                    continue
                if s.startswith("$"):
                    continue
                parsed = self._parse_any_value_change(s)
                if parsed:
                    sym, val = parsed
                    if sym in sym_to_name:
                        waveforms[sym_to_name[sym]].append((current_time, val))
        return waveforms

    # ── Value-change line parsers ─────────────────────────────────────

    def _parse_value_change(self, line: str, target_sym: str) -> Optional[str]:
        m = re.match(r"^([01xzXZ])(.+)$", line)
        if m and m.group(2) == target_sym:
            return m.group(1).lower()
        m = re.match(r"^b([01xzXZ]+)\s*(.+)$", line)
        if m and m.group(2).strip() == target_sym:
            return m.group(1)
        return None

    def _parse_any_value_change(self, line: str) -> Optional[Tuple[str, str]]:
        m = re.match(r"^([01xzXZ])(.+)$", line)
        if m:
            sym = m.group(2)
            if sym in self.symbol_table:
                return sym, m.group(1).lower()
        m = re.match(r"^b([01xzXZ]+)\s*(.+)$", line)
        if m:
            sym = m.group(2).strip()
            if sym in self.symbol_table:
                return sym, m.group(1)
        return None

    def waveform_to_csv(self, result: dict, output_path: str) -> None:
        with open(output_path, "w", encoding="utf-8") as f:
            f.write("time,value\n")
            for t, v in result["waveform"]:
                f.write(str(t) + "," + str(v) + "\n")


# ── CLI ───────────────────────────────────────────────────────────────

def main():
    p = argparse.ArgumentParser(description="Extract signal waveform from VCD")
    p.add_argument("vcd_file")
    p.add_argument("signal", nargs="?")
    p.add_argument("--list", action="store_true")
    p.add_argument("--start", type=int)
    p.add_argument("--end", type=int)
    p.add_argument("--csv")
    args = p.parse_args()

    vcd = VCDSignalParser(args.vcd_file)
    vcd.parse_header()

    if args.list:
        print("Timescale : " + vcd.timescale)
        print("Top scope : " + vcd.top_scope)
        print("Signals:")
        for s in vcd.list_base_signals():
            info = vcd.get_signal_info(s)
            print("  " + s.ljust(30) + "  " + info["type"].ljust(10) + "  width=" + str(info["width"]))
        return

    if not args.signal:
        print("Specify a signal or use --list")
        return

    result = vcd.extract_waveform(args.signal, args.start, args.end)
    print("Signal: " + result["signal"] + "  (" + result["type"] + "[" + str(result["width"]) + "])")
    print("Transitions: " + str(len(result["waveform"])))
    for t, v in result["waveform"]:
        print(str(t).rjust(8) + "  " + v)
    if args.csv:
        vcd.waveform_to_csv(result, args.csv)
        print("Saved to " + args.csv)


if __name__ == "__main__":
    main()
