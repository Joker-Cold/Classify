"""Parse Voltus instance voltage (.iv) file.

Format (relevant lines):
    NOMINAL_VOLTAGE  0.7
    BEGIN
    - inst_name  WIN_EIV  PWR_WIN_IV  GND_WIN_IV  ...  CELL_NAME
    END
"""


def parse_iv(path: str) -> tuple[dict, float]:
    """Parse a Voltus .iv file.

    Returns:
        data      : {inst_name: ir_drop_mV}  (skips 'NA' entries)
        nominal_v : nominal power supply voltage (V)
    """
    nominal_v = 0.7
    data: dict[str, float] = {}
    in_body = False

    with open(path) as f:
        for line in f:
            s = line.strip()
            if s.startswith("NOMINAL_VOLTAGE"):
                nominal_v = float(s.split()[1])
            elif s == "BEGIN":
                in_body = True
            elif s == "END":
                break
            elif in_body and s.startswith("-"):
                parts = s.split()
                # format: - inst_name WIN_EIV PWR_WIN_IV GND_WIN_IV ...
                if len(parts) < 3:
                    continue
                inst = parts[1]
                win_eiv_str = parts[2]
                if win_eiv_str == "NA":
                    continue
                try:
                    win_eiv = float(win_eiv_str)
                except ValueError:
                    continue
                data[inst] = (nominal_v - win_eiv) * 1000  # → mV

    return data, nominal_v
