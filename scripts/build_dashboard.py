"""Génère docs/index.html — dashboard autonome à partir de data/dic_data.json.

GitHub Pages sert le dossier /docs : le dashboard est donc accessible par URL et
régénéré à chaque run du pipeline (mise à jour automatique).

    ./.venv/bin/python scripts/build_dashboard.py
"""
import json
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dic_data.json"
OUT = ROOT / "docs" / "index.html"

TEMPLATE = """<!doctype html>
<html lang="fr"><head>
<meta charset="utf-8"><meta name="viewport" content="width=device-width, initial-scale=1">
<title>DIC — Top 100 fonds</title>
<style>
:root{--bg:#fff;--fg:#111;--muted:#666;--line:#e5e5e5;--card:#f7f7f8;--accent:#2b6cb0;--good:#1a7f37;--warn:#b7791f;--bad:#c53030}
@media(prefers-color-scheme:dark){:root{--bg:#0d1117;--fg:#e6edf3;--muted:#8b949e;--line:#30363d;--card:#161b22;--accent:#58a6ff;--good:#3fb950;--warn:#d29922;--bad:#f85149}}
*{box-sizing:border-box}body{margin:0;font:15px/1.5 -apple-system,Segoe UI,Roboto,sans-serif;background:var(--bg);color:var(--fg)}
.wrap{max-width:1200px;margin:0 auto;padding:24px 16px}
h1{font-size:22px;margin:0 0 4px}.sub{color:var(--muted);font-size:13px;margin-bottom:20px}
.stats{display:flex;flex-wrap:wrap;gap:12px;margin-bottom:20px}
.stat{background:var(--card);border:1px solid var(--line);border-radius:10px;padding:12px 16px;min-width:130px}
.stat b{display:block;font-size:24px}.stat span{color:var(--muted);font-size:12px}
input{width:100%;padding:10px 12px;border:1px solid var(--line);border-radius:8px;background:var(--card);color:var(--fg);margin-bottom:14px;font-size:14px}
.tablewrap{overflow-x:auto;border:1px solid var(--line);border-radius:10px}
table{border-collapse:collapse;width:100%;font-size:13px;min-width:820px}
th,td{padding:8px 10px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
th{position:sticky;top:0;background:var(--card);cursor:pointer;user-select:none;font-size:12px}
tr:hover td{background:var(--card)}
.badge{display:inline-block;padding:1px 7px;border-radius:20px;font-size:11px;border:1px solid var(--line)}
.miss{color:var(--muted)}
.bar{display:inline-block;width:52px;height:7px;border-radius:4px;background:var(--line);vertical-align:middle;overflow:hidden;margin-right:6px}
.bar>i{display:block;height:100%;background:var(--good)}
.no{color:var(--bad)}.foot{color:var(--muted);font-size:12px;margin-top:16px}
a{color:var(--accent)}
</style></head><body><div class="wrap">
<h1>DIC — Top __CAT__ fonds du marché</h1>
<div class="sub">Généré le __GEN__ · données PRIIPs extraites automatiquement (SRI, coûts, période de détention)</div>
<div class="stats">
<div class="stat"><b>__RETR__/__CAT__</b><span>DIC récupérés</span></div>
<div class="stat"><b>__COMP__%</b><span>complétude moyenne</span></div>
<div class="stat"><b>__COS__</b><span>maisons couvertes</span></div>
<div class="stat"><b>__SRC__</b><span>sources actives</span></div>
</div>
<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap">
<input id="q" placeholder="Filtrer : nom, ISIN, société, source…" style="flex:1;min-width:220px">
<label style="display:inline-flex;align-items:center;gap:6px;white-space:nowrap;cursor:pointer;font-size:14px;color:var(--muted)">
<input type="checkbox" id="onlydic" style="width:auto;margin:0"> Uniquement avec DIC</label>
</div>
<div class="tablewrap"><table id="t"><thead><tr>
<th data-k="rank">#</th><th data-k="company_group">Société</th><th data-k="name">Fonds</th>
<th data-k="isin">ISIN</th><th data-k="type">Type</th><th data-k="sri">SRI</th>
<th data-k="ongoing_costs">Frais</th><th data-k="transaction_costs">Transac.</th>
<th data-k="completeness">Complétude</th><th data-k="source">Source</th><th>DIC</th>
</tr></thead><tbody></tbody></table></div>
<div class="foot">Source données : catalogue par encours + parsing DIC/EPT. Les fonds sans DIC récupérable
(iShares, JPMorgan, PIMCO…) nécessitent un accès fundinfo ou un dépôt d'EPT. ·
<a href="https://github.com/icarusmagnus/dic-parser">Code source</a></div>
</div>
<script>
const DATA=__DATA__;
const tb=document.querySelector('#t tbody');
const pct=v=>v==null?'':v+'%';
const cell=v=>v==null||v===''?'<span class="miss">–</span>':v;
function bar(v){if(v==null)return '<span class="miss">–</span>';return `<span class="bar"><i style="width:${v}%"></i></span>${v}%`;}
function row(f){
  const src=f.retrieved?`<span class="badge">${f.source}</span>`:'<span class="no">non récup.</span>';
  return `<tr>
    <td>${f.rank}</td><td>${f.company_group}</td><td>${f.name}</td>
    <td>${f.isin}</td><td>${f.type}</td><td>${cell(f.sri)}</td>
    <td>${f.ongoing_costs!=null?f.ongoing_costs+'%':cell(null)}</td>
    <td>${f.transaction_costs!=null?f.transaction_costs+'%':cell(null)}</td>
    <td>${bar(f.retrieved?f.completeness:null)}</td><td>${src}</td>
    <td>${f.dic_url?`<a class="badge" href="${f.dic_url}" target="_blank" rel="noopener">PDF ↗</a>`:'<span class="miss">–</span>'}</td></tr>`;
}
let rows=DATA.funds.slice();
function render(){tb.innerHTML=rows.map(row).join('')}
function applyFilters(){
  const q=document.querySelector('#q').value.toLowerCase();
  const onlydic=document.querySelector('#onlydic').checked;
  rows=DATA.funds.filter(f=>(!onlydic||f.retrieved)&&[f.name,f.isin,f.company_group,f.source,f.type].join(' ').toLowerCase().includes(q));
  render();
}
document.querySelector('#q').addEventListener('input',applyFilters);
document.querySelector('#onlydic').addEventListener('change',applyFilters);
let asc={};
document.querySelectorAll('th').forEach(th=>th.addEventListener('click',()=>{
  const k=th.dataset.k;asc[k]=!asc[k];
  rows.sort((a,b)=>{let x=a[k],y=b[k];if(x==null)x=asc[k]?1e9:-1e9;if(y==null)y=asc[k]?1e9:-1e9;
    return (typeof x==='number'&&typeof y==='number')?(asc[k]?x-y:y-x):(asc[k]?String(x).localeCompare(y):String(y).localeCompare(x));});
  render();
}));
render();
</script></body></html>"""


def main():
    data = json.loads(DATA.read_text())
    html = (TEMPLATE
            .replace("__DATA__", json.dumps(data, ensure_ascii=False))
            .replace("__GEN__", data.get("generated_at", "—"))
            .replace("__RETR__", str(data.get("retrieved", 0)))
            .replace("__CAT__", str(data.get("catalog_size", 0)))
            .replace("__COMP__", str(data.get("avg_completeness", "—")))
            .replace("__COS__", str(data.get("companies_covered", 0)))
            .replace("__SRC__", str(len(data.get("sources", {})))))
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text(html)
    print(f"dashboard -> {OUT}")


if __name__ == "__main__":
    main()
