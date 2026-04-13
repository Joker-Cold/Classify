#!/usr/bin/env python3
"""生成热点覆盖率可视化 HTML（Plotly，无需安装）"""

import csv, json, os, sys

def read_csv(path):
    rows = []
    with open(path, newline='', encoding='utf-8') as f:
        for r in csv.DictReader(f):
            rows.append(r)
    return rows

def fv(s, default=None):
    try: return float(s)
    except: return default

def iv(s, default=None):
    try: return int(s)
    except: return default

# ── load ──────────────────────────────────────────────────────────────────────
csv_path = os.path.join(os.path.dirname(__file__), '..', 'result', 'hotspot_top20.csv')
sum_path = os.path.join(os.path.dirname(__file__), '..', 'result', 'summary.json')
out_path = os.path.join(os.path.dirname(__file__), '..', 'result', 'hotspot_visualization.html')

rows = read_csv(csv_path)
with open(sum_path) as f:
    summary = json.load(f)

# separate groups
orig_rows = [r for r in rows if r['in_orig_topk'] == 'Y']
comp_rows = [r for r in rows if r['in_comp_topk'] == 'Y']
both_rows = [r for r in rows if r['in_orig_topk'] == 'Y' and r['in_comp_topk'] == 'Y']

# short inst name for display
def short(name):
    parts = name.split('/')
    return '/'.join(parts[-2:]) if len(parts) > 2 else name

# ── build chart data ──────────────────────────────────────────────────────────

# Chart 1: grouped bar - orig top-20 IR drop comparison
bar_labels = [short(r['inst']) for r in orig_rows]
bar_orig   = [fv(r['ir_orig_mV'], 0) for r in orig_rows]
bar_comp   = [fv(r['ir_comp_mV'])    for r in orig_rows]   # None if missing
bar_comp_vals = [v if v is not None else 0 for v in bar_comp]
bar_comp_none = [v is None for v in bar_comp]
bar_delta = [fv(r['delta_mV']) for r in orig_rows]

# Chart 2: rank scatter (orig rank vs comp rank for instances with both ranks)
rs_inst   = [short(r['inst']) for r in rows if iv(r['rank_orig']) and iv(r['rank_comp'])]
rs_orig_r = [iv(r['rank_orig']) for r in rows if iv(r['rank_orig']) and iv(r['rank_comp'])]
rs_comp_r = [iv(r['rank_comp']) for r in rows if iv(r['rank_orig']) and iv(r['rank_comp'])]
rs_delta  = [fv(r['delta_mV'], 0) for r in rows if iv(r['rank_orig']) and iv(r['rank_comp'])]

# Chart 3: spatial scatter - orig top rows with position
sp_x    = [fv(r['x_um'])       for r in rows if fv(r['x_um']) is not None]
sp_y    = [fv(r['y_um'])       for r in rows if fv(r['y_um']) is not None]
sp_orig = [fv(r['ir_orig_mV']) for r in rows if fv(r['x_um']) is not None]
sp_comp = [fv(r['ir_comp_mV']) for r in rows if fv(r['x_um']) is not None]
sp_inst = [short(r['inst'])    for r in rows if fv(r['x_um']) is not None]
sp_in_orig = [r['in_orig_topk'] == 'Y' for r in rows if fv(r['x_um']) is not None]
sp_in_comp = [r['in_comp_topk'] == 'Y' for r in rows if fv(r['x_um']) is not None]

# table rows
table_rows_html = ''
for r in rows:
    ro = iv(r['rank_orig'])
    rc = iv(r['rank_comp'])
    orig_flag = '🔴' if r['in_orig_topk'] == 'Y' else ''
    comp_flag = '🔵' if r['in_comp_topk'] == 'Y' else ''
    delta = fv(r['delta_mV'])
    if delta is not None:
        delta_class = 'delta-pos' if delta > 0 else 'delta-neg'
        delta_str = f'{delta:+.2f}'
    else:
        delta_class = ''
        delta_str = 'N/A'
    comp_str = f"{fv(r['ir_comp_mV']):.2f}" if fv(r['ir_comp_mV']) is not None else '—'
    rc_str   = str(rc) if rc else '—'
    table_rows_html += f'''
        <tr>
          <td>{r["inst"]}</td>
          <td>{r["cell"]}</td>
          <td>{r["x_um"] or "—"}</td>
          <td>{r["y_um"] or "—"}</td>
          <td>{fv(r["ir_orig_mV"]):.2f}</td>
          <td>{comp_str}</td>
          <td class="{delta_class}">{delta_str}</td>
          <td>{ro or "—"}</td>
          <td>{rc_str}</td>
          <td>{orig_flag}</td>
          <td>{comp_flag}</td>
        </tr>'''

c_int   = summary['C_int_%']
verdict = summary['verdict']
verdict_color = '#27ae60' if verdict == 'PASS' else ('#e67e22' if verdict == 'MARGINAL' else '#c0392b')

html = f"""<!DOCTYPE html>
<html lang="zh">
<head>
<meta charset="UTF-8">
<title>热点覆盖率分析 — Traditional VCD vs Full VCD</title>
<script src="https://cdn.plot.ly/plotly-2.27.0.min.js"></script>
<style>
  body {{ font-family: 'Segoe UI', Arial, sans-serif; margin: 0; background: #f5f6fa; color: #2c3e50; }}
  h1   {{ background: #2c3e50; color: #fff; margin: 0; padding: 18px 30px; font-size: 1.3em; }}
  .subtitle {{ background: #34495e; color: #bdc3c7; padding: 6px 30px; font-size: 0.88em; }}
  .cards  {{ display: flex; gap: 16px; padding: 20px 30px 4px; flex-wrap: wrap; }}
  .card   {{ background: #fff; border-radius: 8px; padding: 14px 22px;
              box-shadow: 0 2px 6px rgba(0,0,0,.08); min-width: 150px; }}
  .card .label {{ font-size: 0.78em; color: #7f8c8d; margin-bottom: 4px; }}
  .card .value {{ font-size: 1.6em; font-weight: 700; }}
  .verdict {{ font-size: 1.1em !important; color: {verdict_color} !important; }}
  .section {{ background: #fff; border-radius: 8px; margin: 16px 30px;
               box-shadow: 0 2px 6px rgba(0,0,0,.08); overflow: hidden; }}
  .section h2 {{ background: #ecf0f1; margin: 0; padding: 10px 20px; font-size: 1em;
                  color: #2c3e50; border-bottom: 1px solid #dde; }}
  .chart-wrap {{ padding: 10px; }}
  table  {{ width: 100%; border-collapse: collapse; font-size: 0.82em; }}
  th     {{ background: #2c3e50; color: #fff; padding: 8px 10px; text-align: left; position: sticky; top: 0; }}
  td     {{ padding: 6px 10px; border-bottom: 1px solid #eee; }}
  tr:hover td {{ background: #f0f4f8; }}
  .delta-pos {{ color: #e74c3c; font-weight: 600; }}
  .delta-neg {{ color: #27ae60; font-weight: 600; }}
  .table-wrap {{ max-height: 420px; overflow-y: auto; }}
  footer {{ text-align: center; padding: 14px; color: #95a5a6; font-size: 0.8em; }}
</style>
</head>
<body>
<h1>热点覆盖率分析报告 — Traditional Vector Profiling</h1>
<div class="subtitle">
  原始仿真：test.vcd（全量 11850 ns）&nbsp;|&nbsp;压缩仿真：traditional.vcd（4 窗口 1237 ns，10.4%）
  &nbsp;|&nbsp;工具：Innovus v20.10 Voltus Rail
</div>

<div class="cards">
  <div class="card">
    <div class="label">C_int 强度覆盖率</div>
    <div class="value" style="color:#e67e22">{c_int:.2f}%</div>
  </div>
  <div class="card">
    <div class="label">C_k 位置覆盖率 (k=1~10)</div>
    <div class="value" style="color:#c0392b">全部 MISS</div>
  </div>
  <div class="card">
    <div class="label">Verdict</div>
    <div class="value verdict">{verdict}</div>
  </div>
  <div class="card">
    <div class="label">orig 最坏 IR Drop</div>
    <div class="value">{summary['ir_orig_max_mV']} mV</div>
  </div>
  <div class="card">
    <div class="label">comp 最坏 IR Drop</div>
    <div class="value">{summary['ir_comp_max_mV']} mV</div>
  </div>
  <div class="card">
    <div class="label">orig 最坏实例</div>
    <div class="value" style="font-size:0.75em;margin-top:4px">{summary['worst_inst_orig']}</div>
  </div>
  <div class="card">
    <div class="label">comp 最坏实例</div>
    <div class="value" style="font-size:0.75em;margin-top:4px">{summary['worst_inst_comp']}</div>
  </div>
</div>

<!-- Chart 1: grouped bar -->
<div class="section">
  <h2>① Orig Top-20 热点 IR Drop 对比（原始 vs 压缩）</h2>
  <div class="chart-wrap"><div id="chart1"></div></div>
</div>

<!-- Chart 2: rank scatter -->
<div class="section">
  <h2>② 热点排名漂移（Orig rank → Comp rank）</h2>
  <div class="chart-wrap"><div id="chart2"></div></div>
</div>

<!-- Chart 3: spatial -->
<div class="section">
  <h2>③ 物理位置分布（有坐标的实例，orig IR Drop 着色）</h2>
  <div class="chart-wrap"><div id="chart3"></div></div>
</div>

<!-- Table -->
<div class="section">
  <h2>④ 数据明细表（🔴 = orig top-20，🔵 = comp top-20）</h2>
  <div class="table-wrap">
    <table>
      <thead><tr>
        <th>Instance</th><th>Cell</th><th>X (μm)</th><th>Y (μm)</th>
        <th>IR Orig (mV)</th><th>IR Comp (mV)</th><th>Δ (mV)</th>
        <th>Rank Orig</th><th>Rank Comp</th><th>Orig Top</th><th>Comp Top</th>
      </tr></thead>
      <tbody>{table_rows_html}</tbody>
    </table>
  </div>
</div>

<footer>Generated by coverage_analysis/code/visualize_hotspot.py</footer>

<script>
// ── Chart 1: grouped bar ──────────────────────────────────────────────────────
var labels = {json.dumps(bar_labels)};
var origV  = {json.dumps(bar_orig)};
var compV  = {json.dumps(bar_comp_vals)};
var compNone = {json.dumps(bar_comp_none)};

// mark missing comp as lighter
var compColors = compNone.map(n => n ? 'rgba(180,180,180,0.4)' : 'rgba(52,152,219,0.8)');

Plotly.newPlot('chart1', [
  {{
    name: 'Orig (Full VCD)', type: 'bar',
    x: labels, y: origV,
    marker: {{color: 'rgba(231,76,60,0.85)'}},
    hovertemplate: '%{{x}}<br>Orig: %{{y:.2f}} mV<extra></extra>'
  }},
  {{
    name: 'Comp (Traditional VCD)', type: 'bar',
    x: labels, y: compV,
    marker: {{color: compColors}},
    hovertemplate: '%{{x}}<br>Comp: %{{y:.2f}} mV<extra></extra>'
  }}
], {{
  barmode: 'group',
  height: 380,
  margin: {{t:20, b:120, l:60, r:20}},
  xaxis: {{tickangle: -35, tickfont: {{size:10}}}},
  yaxis: {{title: 'IR Drop (mV)'}},
  legend: {{orientation:'h', y:1.08}},
  plot_bgcolor: '#fafafa',
  paper_bgcolor: '#fff'
}}, {{responsive: true}});

// ── Chart 2: rank scatter ─────────────────────────────────────────────────────
var rsInst  = {json.dumps(rs_inst)};
var rsOrigR = {json.dumps(rs_orig_r)};
var rsCompR = {json.dumps(rs_comp_r)};
var rsDelta = {json.dumps(rs_delta)};

Plotly.newPlot('chart2', [
  {{
    type: 'scatter', mode: 'markers',
    x: rsOrigR, y: rsCompR,
    text: rsInst,
    marker: {{
      size: 10,
      color: rsDelta,
      colorscale: 'RdYlGn',
      reversescale: true,
      colorbar: {{title: 'Δ IR Drop (mV)', thickness: 14}},
      showscale: true
    }},
    hovertemplate: '%{{text}}<br>Orig rank: %{{x}}<br>Comp rank: %{{y}}<extra></extra>'
  }},
  {{
    type: 'scatter', mode: 'lines',
    x: [0, 55000], y: [0, 55000],
    line: {{color:'#aaa', dash:'dot', width:1}},
    showlegend: false,
    hoverinfo: 'skip'
  }}
], {{
  height: 400,
  margin: {{t:20, b:60, l:80, r:20}},
  xaxis: {{title: 'Rank in Orig (Full VCD)', type:'log'}},
  yaxis: {{title: 'Rank in Comp (Traditional VCD)', type:'log'}},
  annotations: [{{
    x: 0.5, y: 1.04, xref:'paper', yref:'paper',
    text: '对角线上=排名不变，右下=在压缩中排名靠前（漂移），左上=排名下降',
    showarrow: false, font:{{size:11, color:'#666'}}
  }}],
  plot_bgcolor: '#fafafa',
  paper_bgcolor: '#fff'
}}, {{responsive: true}});

// ── Chart 3: spatial ─────────────────────────────────────────────────────────
var spX    = {json.dumps(sp_x)};
var spY    = {json.dumps(sp_y)};
var spOrig = {json.dumps(sp_orig)};
var spComp = {json.dumps(sp_comp)};
var spInst = {json.dumps(sp_inst)};
var spInOrig = {json.dumps(sp_in_orig)};
var spInComp = {json.dumps(sp_in_comp)};

var origTop = {{x:[], y:[], text:[], ir:[]}};
var compTop = {{x:[], y:[], text:[], ir:[]}};
var other   = {{x:[], y:[], text:[], ir:[]}};

for (var i=0; i<spX.length; i++) {{
  if (spInOrig[i]) {{
    origTop.x.push(spX[i]); origTop.y.push(spY[i]);
    origTop.text.push(spInst[i]); origTop.ir.push(spOrig[i]);
  }} else if (spInComp[i]) {{
    compTop.x.push(spX[i]); compTop.y.push(spY[i]);
    compTop.text.push(spInst[i]); compTop.ir.push(spOrig[i]);
  }} else {{
    other.x.push(spX[i]); other.y.push(spY[i]);
    other.text.push(spInst[i]); other.ir.push(spOrig[i]);
  }}
}}

Plotly.newPlot('chart3', [
  {{
    name: 'Comp Top-20 热点', type:'scatter', mode:'markers',
    x: compTop.x, y: compTop.y, text: compTop.text,
    marker: {{size:18, color:'#3498db', symbol:'star', opacity:0.95,
              line:{{color:'#fff',width:1}}}},
    hovertemplate: '%{{text}}<br>(%{{x:.1f}}, %{{y:.1f}}) μm<extra>Comp Top</extra>'
  }},
  {{
    name: 'Orig Top-20 热点', type:'scatter', mode:'markers',
    x: origTop.x, y: origTop.y, text: origTop.text,
    marker: {{size:18, color:'#e74c3c', symbol:'star', opacity:0.95,
              line:{{color:'#fff',width:1}}}},
    hovertemplate: '%{{text}}<br>(%{{x:.1f}}, %{{y:.1f}}) μm<br>Orig IR: %{{customdata:.2f}} mV<extra>Orig Top</extra>',
    customdata: origTop.ir
  }}
], {{
  height: 420,
  margin: {{t:20, b:60, l:70, r:20}},
  xaxis: {{title: 'X (μm)', range:[0, 400]}},
  yaxis: {{title: 'Y (μm)', range:[0, 400]}},
  plot_bgcolor: '#f0f4f8',
  paper_bgcolor: '#fff',
  annotations: [{{
    x: 0.5, y: 1.04, xref:'paper', yref:'paper',
    text: '🔴 Orig 最坏热点集中于 u2 区域（右上）  🔵 Comp 最坏热点集中于 u1 区域（左中）',
    showarrow: false, font:{{size:11, color:'#444'}}
  }}]
}}, {{responsive: true}});
</script>
</body>
</html>"""

with open(out_path, 'w', encoding='utf-8') as f:
    f.write(html)
print(f'Saved → {out_path}')
