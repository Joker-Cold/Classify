#!/usr/bin/env python3
"""
Improved waveform viewer with better scalar/vector support
"""

import csv
import argparse
import os
from typing import List, Tuple


def read_waveform_csv(csv_path: str) -> List[Tuple[int, str]]:
    """Read waveform data from CSV file."""
    waveform = []
    with open(csv_path, 'r', encoding='utf-8') as f:
        reader = csv.DictReader(f)
        for row in reader:
            time = int(row['time'])
            value = row['value']
            waveform.append((time, value))
    return waveform


def is_scalar(waveform: List[Tuple[int, str]]) -> bool:
    """Check if waveform is scalar (single bit)."""
    values = [v for t, v in waveform]
    return all(len(v) == 1 and v in '01xzXZ' for v in values if v not in 'xzXZ')


def value_to_int(value: str) -> int:
    """Convert binary string to integer."""
    if value in 'xzXZ':
        return -1
    try:
        return int(value, 2)
    except ValueError:
        return -1


def generate_scalar_waveform_html(waveform: List[Tuple[int, str]]) -> str:
    """Generate HTML for scalar waveform."""
    times = [t for t, v in waveform]
    values = [v for t, v in waveform]
    min_time = times[0]
    max_time = times[-1]
    time_range = max_time - min_time if max_time > min_time else 1

    # Generate wave path
    wave_points = []
    last_y = 0

    for i, (t, v) in enumerate(waveform):
        x = ((t - min_time) / time_range) * 100

        if v == '1':
            y = 20
        elif v == '0':
            y = 80
        else:  # x/z
            y = 50

        if i == 0:
            wave_points.append(f"M {x},{y}")
        else:
            # Vertical line at current x from last_y to y
            wave_points.append(f"L {x},{last_y}")
            wave_points.append(f"L {x},{y}")

        last_y = y

        # Add horizontal line if not last point
        if i < len(waveform) - 1:
            next_t = waveform[i+1][0]
            next_x = ((next_t - min_time) / time_range) * 100
            wave_points.append(f"L {next_x},{y}")

    wave_path = " ".join(wave_points)

    # Generate value markers
    markers_html = ""
    for t, v in waveform:
        x = ((t - min_time) / time_range) * 100
        if v == '1':
            y = 10
        elif v == '0':
            y = 90
        else:
            y = 50

        color = '#10b981' if v == '1' else '#ef4444' if v == '0' else '#6b7280'
        bg_color = '#d1fae5' if v == '1' else '#fee2e2' if v == '0' else '#f3f4f6'

        markers_html += f'''
        <div class="value-marker" style="left: {x}%; top: {y}px; transform: translate(-50%, -50%);">
            <div class="marker-dot" style="background: {color};"></div>
            <div class="marker-label" style="background: {bg_color}; color: {color};">{v}</div>
        </div>
        '''

    # Generate time axis
    time_axis_html = ""
    num_ticks = min(15, len(waveform))
    step = max(1, len(waveform) // num_ticks)
    for i in range(0, len(waveform), step):
        t, v = waveform[i]
        x = ((t - min_time) / time_range) * 100
        time_axis_html += f'''
        <div class="time-tick" style="left: {x}%;">
            <div class="tick-line"></div>
            <div class="tick-label">{t}</div>
        </div>
        '''

    html = f'''
    <div class="waveform-svg-container">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="wave-svg">
            <line x1="0" y1="20" x2="100" y2="20" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>
            <line x1="0" y1="50" x2="100" y2="50" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>
            <line x1="0" y1="80" x2="100" y2="80" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>
            <path d="{wave_path}" fill="none" stroke="#1f4e79" stroke-width="2" stroke-linecap="square"/>
        </svg>
        {markers_html}
    </div>
    <div class="time-axis">
        {time_axis_html}
    </div>
    <div class="y-axis-labels">
        <span class="y-label high">1</span>
        <span class="y-label low">0</span>
    </div>
    '''
    return html


def generate_vector_waveform_html(waveform: List[Tuple[int, str]]) -> str:
    """Generate HTML for vector waveform - each bit as separate scalar wave."""
    times = [t for t, v in waveform]
    values = [v for t, v in waveform]
    min_time = times[0]
    max_time = times[-1]
    time_range = max_time - min_time if max_time > min_time else 1

    # Determine vector width (maximum bit count); guard against all-x/z waveforms
    valid_widths = [len(v) for v in values if len(v) > 1 and v not in ('x', 'z', 'X', 'Z')]
    bit_width = max(valid_widths) if valid_widths else 1

    # Create individual bit waveforms
    bit_waveforms = []
    for bit_idx in range(bit_width):
        bit_values = []
        for t, v in waveform:
            if v in 'xzXZ':
                bit_values.append((t, 'x'))
            else:
                # Ensure value has enough bits (pad with 0s)
                padded_v = v.zfill(bit_width)
                bit_values.append((t, padded_v[bit_width - 1 - bit_idx]))
        bit_waveforms.append((bit_idx, bit_values))

    # Generate time axis
    time_axis_html = ""
    num_ticks = min(12, len(waveform))
    step = max(1, len(waveform) // num_ticks)
    for i in range(0, len(waveform), step):
        t, v = waveform[i]
        x = ((t - min_time) / time_range) * 100
        time_axis_html += f'''
        <div class="time-tick" style="left: {x}%;">
            <div class="tick-line"></div>
            <div class="tick-label">{t}</div>
        </div>
        '''

    # Generate each bit's waveform
    bits_html = ""
    for bit_idx, bit_wave in bit_waveforms:
        bits_html += f'''
        <div class="bit-section">
            <div class="bit-label">Bit {bit_idx}</div>
            <div class="bit-wave-container">
                {generate_scalar_waveform_for_bit(bit_wave, min_time, time_range)}
            </div>
        </div>
        '''

    html = f'''
    <div class="bit-waveforms">
        {bits_html}
    </div>
    <div class="time-axis">
        {time_axis_html}
    </div>
    '''
    return html


def generate_scalar_waveform_for_bit(waveform: List[Tuple[int, str]], min_time: int, time_range: int) -> str:
    """Generate scalar waveform for a single bit (used by vector waveform)."""
    times = [t for t, v in waveform]
    values = [v for t, v in waveform]

    # Generate wave path
    wave_points = []
    last_y = 0

    for i, (t, v) in enumerate(waveform):
        x = ((t - min_time) / time_range) * 100

        if v == '1':
            y = 20
        elif v == '0':
            y = 80
        else:  # x/z
            y = 50

        if i == 0:
            wave_points.append(f"M {x},{y}")
        else:
            wave_points.append(f"L {x},{last_y}")
            wave_points.append(f"L {x},{y}")

        last_y = y

        if i < len(waveform) - 1:
            next_t = waveform[i+1][0]
            next_x = ((next_t - min_time) / time_range) * 100
            wave_points.append(f"L {next_x},{y}")

    wave_path = " ".join(wave_points)

    # Generate value markers
    markers_html = ""
    for t, v in waveform:
        x = ((t - min_time) / time_range) * 100
        if v == '1':
            y = 10
        elif v == '0':
            y = 90
        else:
            y = 50

        color = '#10b981' if v == '1' else '#ef4444' if v == '0' else '#6b7280'
        bg_color = '#d1fae5' if v == '1' else '#fee2e2' if v == '0' else '#f3f4f6'

        markers_html += f'''
        <div class="value-marker" style="left: {x}%; top: {y}px; transform: translate(-50%, -50%);">
            <div class="marker-dot" style="background: {color};"></div>
            <div class="marker-label" style="background: {bg_color}; color: {color};">{v}</div>
        </div>
        '''

    html = f'''
    <div class="waveform-svg-container">
        <svg viewBox="0 0 100 100" preserveAspectRatio="none" class="wave-svg">
            <line x1="0" y1="20" x2="100" y2="20" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>
            <line x1="0" y1="50" x2="100" y2="50" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>
            <line x1="0" y1="80" x2="100" y2="80" stroke="#e5e7eb" stroke-width="0.5" stroke-dasharray="2,2"/>
            <path d="{wave_path}" fill="none" stroke="#1f4e79" stroke-width="2" stroke-linecap="square"/>
        </svg>
        {markers_html}
    </div>
    <div class="bit-y-axis">
        <span class="y-label high">1</span>
        <span class="y-label low">0</span>
    </div>
    '''
    return html


def generate_html(waveform: List[Tuple[int, str]], title: str = "Waveform", output_path: str = "waveform.html"):
    """Generate HTML waveform viewer."""
    times = [t for t, v in waveform]
    values = [v for t, v in waveform]
    scalar = is_scalar(waveform)

    min_time = times[0]
    max_time = times[-1]

    # Generate waveform specific HTML
    if scalar:
        waveform_html = generate_scalar_waveform_html(waveform)
    else:
        waveform_html = generate_vector_waveform_html(waveform)

    # Generate transitions table
    table_rows = ""
    for i, (t, v) in enumerate(waveform):
        dec = str(value_to_int(v)) if all(c in '01' for c in v) else 'N/A'
        hex_val = hex(value_to_int(v)) if all(c in '01' for c in v) else 'N/A'
        duration = times[i+1] - t if i < len(waveform)-1 else '-'

        row_class = ""
        if scalar:
            if v == '1':
                row_class = "row-high"
            elif v == '0':
                row_class = "row-low"

        table_rows += f'''
        <tr class="{row_class}">
            <td>{i+1}</td>
            <td class="time-col">{t}</td>
            <td class="bin-col">{v}</td>
            <td>{dec}</td>
            <td>{hex_val}</td>
            <td>{duration}</td>
        </tr>
        '''

    html_content = f'''
<!DOCTYPE html>
<html lang="zh-CN">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>{title}</title>
    <style>
        * {{ box-sizing: border-box; margin: 0; padding: 0; }}
        body {{
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, Oxygen, Ubuntu, sans-serif;
            background: linear-gradient(135deg, #1a1a2e 0%, #16213e 100%);
            min-height: 100vh;
            padding: 30px 20px;
        }}
        .container {{
            max-width: 1100px;
            margin: 0 auto;
            background: white;
            border-radius: 16px;
            box-shadow: 0 25px 80px rgba(0,0,0,0.4);
            overflow: hidden;
        }}
        .header {{
            background: linear-gradient(135deg, #0f172a 0%, #1e293b 100%);
            color: white;
            padding: 30px 35px;
        }}
        .header h1 {{
            font-size: 26px;
            margin-bottom: 8px;
            display: flex;
            align-items: center;
            gap: 12px;
        }}
        .header .badge {{
            font-size: 12px;
            padding: 4px 12px;
            background: {'#059669' if scalar else '#d97706'};
            border-radius: 20px;
            font-weight: 600;
        }}
        .header p {{
            opacity: 0.8;
            font-size: 14px;
        }}
        .content {{ padding: 35px; }}
        .stats {{
            display: grid;
            grid-template-columns: repeat(4, 1fr);
            gap: 15px;
            margin-bottom: 30px;
        }}
        .stat-card {{
            background: linear-gradient(135deg, #f8fafc 0%, #f1f5f9 100%);
            border: 1px solid #e2e8f0;
            border-radius: 10px;
            padding: 18px;
            text-align: center;
        }}
        .stat-card .label {{
            font-size: 11px;
            color: #64748b;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 6px;
        }}
        .stat-card .value {{
            font-size: 26px;
            font-weight: 800;
            color: #0f172a;
        }}
        .waveform-section {{
            background: #f8fafc;
            border: 1px solid #e2e8f0;
            border-radius: 12px;
            padding: 25px;
            margin-bottom: 30px;
        }}
        .section-title {{
            font-size: 14px;
            font-weight: 700;
            color: #475569;
            text-transform: uppercase;
            letter-spacing: 0.8px;
            margin-bottom: 20px;
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .section-title::before {{
            content: '';
            width: 4px;
            height: 16px;
            background: linear-gradient(180deg, #3b82f6 0%, #8b5cf6 100%);
            border-radius: 2px;
        }}
        .waveform-display {{
            position: relative;
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 15px;
            min-height: 150px;
        }}
        .waveform-svg-container {{
            position: relative;
            height: 120px;
            padding: 0 30px 0 20px;
        }}
        .wave-svg {{
            width: 100%;
            height: 100%;
        }}
        .value-marker {{
            position: absolute;
            display: flex;
            flex-direction: column;
            align-items: center;
            z-index: 10;
        }}
        .marker-dot {{
            width: 8px;
            height: 8px;
            border-radius: 50%;
            border: 2px solid white;
            box-shadow: 0 2px 4px rgba(0,0,0,0.2);
        }}
        .marker-label {{
            font-size: 11px;
            font-weight: 700;
            padding: 2px 8px;
            border-radius: 4px;
            margin-top: 4px;
        }}
        .bit-waveforms {{
            display: flex;
            flex-direction: column;
            gap: 10px;
            margin-right: 30px;
        }}
        .bit-section {{
            display: flex;
            align-items: center;
            gap: 10px;
        }}
        .bit-label {{
            min-width: 50px;
            font-weight: 700;
            font-size: 13px;
            color: #475569;
            text-align: right;
        }}
        .bit-wave-container {{
            flex: 1;
            position: relative;
            background: white;
            border: 1px solid #d1d5db;
            border-radius: 8px;
            padding: 8px 10px;
        }}
        .bit-wave-container .waveform-svg-container {{
            height: 80px;
            padding: 0 25px 0 20px;
        }}
        .bit-y-axis {{
            position: absolute;
            left: 2px;
            top: 10px;
            bottom: 8px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            pointer-events: none;
        }}
        .time-axis {{
            position: relative;
            height: 35px;
            margin: 0 30px 0 20px;
            border-top: 1px solid #cbd5e1;
        }}
        .time-tick {{
            position: absolute;
            top: 0;
            display: flex;
            flex-direction: column;
            align-items: center;
        }}
        .tick-line {{
            width: 1px;
            height: 8px;
            background: #94a3b8;
        }}
        .tick-label {{
            font-size: 11px;
            color: #64748b;
            margin-top: 4px;
            white-space: nowrap;
        }}
        .y-axis-labels {{
            position: absolute;
            left: 5px;
            top: 15px;
            bottom: 45px;
            display: flex;
            flex-direction: column;
            justify-content: space-between;
            pointer-events: none;
        }}
        .y-label {{
            font-size: 12px;
            font-weight: 700;
            width: 20px;
            text-align: center;
        }}
        .y-label.high {{ color: #059669; }}
        .y-label.low {{ color: #dc2626; }}
        .table-wrapper {{
            overflow-x: auto;
            border-radius: 8px;
            border: 1px solid #e2e8f0;
        }}
        table {{
            width: 100%;
            border-collapse: collapse;
            font-size: 13px;
        }}
        th, td {{ padding: 12px 16px; text-align: left; }}
        th {{
            background: #f1f5f9;
            font-weight: 700;
            color: #475569;
            text-transform: uppercase;
            font-size: 11px;
            letter-spacing: 0.6px;
        }}
        tr {{ border-bottom: 1px solid #e2e8f0; }}
        tr:last-child {{ border-bottom: none; }}
        tr:hover {{ background: #f8fafc; }}
        tr.row-high {{ background: #f0fdf4; }}
        tr.row-low {{ background: #fef2f2; }}
        .bin-col {{
            font-family: 'Courier New', monospace;
            font-weight: 700;
            background: #f1f5f9;
            padding: 3px 8px;
            border-radius: 4px;
            display: inline-block;
        }}
        .time-col {{
            font-weight: 700;
            color: #1d4ed8;
        }}
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>
                📈 {title}
                <span class="badge">{'SCALAR' if scalar else 'VECTOR'}</span>
            </h1>
            <p>Interactive Waveform Visualization</p>
        </div>
        <div class="content">
            <div class="stats">
                <div class="stat-card">
                    <div class="label">Transitions</div>
                    <div class="value">{len(waveform)}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Start</div>
                    <div class="value">{min_time}</div>
                </div>
                <div class="stat-card">
                    <div class="label">End</div>
                    <div class="value">{max_time}</div>
                </div>
                <div class="stat-card">
                    <div class="label">Duration</div>
                    <div class="value">{max_time - min_time}</div>
                </div>
            </div>

            <div class="waveform-section">
                <div class="section-title">Waveform</div>
                <div class="waveform-display">
                    {waveform_html}
                </div>
            </div>

            <div class="section-title">Transition Details</div>
            <div class="table-wrapper">
                <table>
                    <thead>
                        <tr>
                            <th>#</th>
                            <th>Time</th>
                            <th>Binary</th>
                            <th>Decimal</th>
                            <th>Hex</th>
                            <th>Duration</th>
                        </tr>
                    </thead>
                    <tbody>
                        {table_rows}
                    </tbody>
                </table>
            </div>
        </div>
    </div>
</body>
</html>
'''

    with open(output_path, 'w', encoding='utf-8') as f:
        f.write(html_content)

    return output_path


def main():
    parser = argparse.ArgumentParser(description='Generate HTML waveform viewer')
    parser.add_argument('csv_file', help='Path to CSV file')
    parser.add_argument('--title', help='Plot title', default='VCD Waveform')
    parser.add_argument('--output', help='Output HTML file path', default='waveform.html')

    args = parser.parse_args()

    waveform = read_waveform_csv(args.csv_file)
    print(f"Read {len(waveform)} transitions from {args.csv_file}")

    output_path = generate_html(waveform, args.title, args.output)
    abs_path = os.path.abspath(output_path)
    print(f"Waveform viewer generated: {abs_path}")
    print("\nPlease open this file in your web browser to view the waveform!")


if __name__ == '__main__':
    main()
