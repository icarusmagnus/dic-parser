"""Génère data/dashboard_artifact.html (body-only) pour publication en Artifact.

Même donnée que le dashboard Pages, mais sans <html>/<head> (l'Artifact les ajoute).
"""
import json
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "data" / "dic_data.json"
OUT = ROOT / "data" / "dashboard_artifact.html"

BODY = """<style>
:root{
  --bg:#f6f7f9;--panel:#fff;--ink:#161a1f;--muted:#5c6773;--line:#e3e7ec;
  --accent:#3a5a8c;--accent-soft:#eaf0f8;
  --good:#1f7a4d;--good-bg:#e6f2ec;--warn:#9a6a12;--warn-bg:#f6eeda;--bad:#a83232;
  --track:#e3e7ec;
}
:root[data-theme="dark"],
@media (prefers-color-scheme:dark){:root:not([data-theme="light"]){
  --bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--muted:#93a1b0;--line:#262d36;
  --accent:#7aa2d6;--accent-soft:#1a2432;
  --good:#4cc38a;--good-bg:#12271d;--warn:#d9a441;--warn-bg:#2a2313;--bad:#e06c6c;
  --track:#262d36;
}}
:root[data-theme="dark"]{
  --bg:#0e1116;--panel:#161b22;--ink:#e6edf3;--muted:#93a1b0;--line:#262d36;
  --accent:#7aa2d6;--accent-soft:#1a2432;
  --good:#4cc38a;--good-bg:#12271d;--warn:#d9a441;--warn-bg:#2a2313;--bad:#e06c6c;
  --track:#262d36;
}
*{box-sizing:border-box}
.dic{background:var(--bg);color:var(--ink);font:15px/1.55 ui-sans-serif,-apple-system,"Segoe UI",Roboto,sans-serif;
  -webkit-font-smoothing:antialiased;padding:32px 20px;min-height:100vh}
.dic .inner{max-width:1180px;margin:0 auto}
.dic .eyebrow{font-size:11px;letter-spacing:.14em;text-transform:uppercase;color:var(--accent);font-weight:600;margin-bottom:6px}
.dic h1{font-size:26px;line-height:1.15;margin:0 0 6px;letter-spacing:-.01em;text-wrap:balance}
.dic .lede{color:var(--muted);font-size:14px;margin:0 0 22px}
.dic .cards{display:grid;grid-template-columns:repeat(auto-fit,minmax(150px,1fr));gap:12px;margin-bottom:14px}
.dic .card{background:var(--panel);border:1px solid var(--line);border-radius:12px;padding:14px 16px}
.dic .card .n{font-size:27px;font-weight:650;letter-spacing:-.02em;font-variant-numeric:tabular-nums}
.dic .card .l{color:var(--muted);font-size:12px;margin-top:2px}
.dic .srcbar{display:flex;height:8px;border-radius:6px;overflow:hidden;background:var(--track);margin:4px 0 22px}
.dic .srcbar>span{display:block}
.dic .legend{display:flex;flex-wrap:wrap;gap:14px;margin:-14px 0 22px;font-size:12px;color:var(--muted)}
.dic .legend b{display:inline-block;width:9px;height:9px;border-radius:3px;margin-right:5px;vertical-align:middle}
.dic input{width:100%;padding:11px 13px;border:1px solid var(--line);border-radius:10px;background:var(--panel);
  color:var(--ink);margin-bottom:14px;font-size:14px}
.dic input:focus{outline:2px solid var(--accent);outline-offset:1px;border-color:transparent}
.dic .tw{overflow-x:auto;border:1px solid var(--line);border-radius:12px;background:var(--panel)}
.dic table{border-collapse:collapse;width:100%;min-width:860px;font-size:13px}
.dic th,.dic td{padding:9px 12px;text-align:left;border-bottom:1px solid var(--line);white-space:nowrap}
.dic th{position:sticky;top:0;background:var(--panel);cursor:pointer;user-select:none;
  font-size:11px;letter-spacing:.04em;text-transform:uppercase;color:var(--muted);font-weight:600}
.dic th:hover{color:var(--ink)}
.dic tbody tr:hover td{background:var(--accent-soft)}
.dic td.num{font-variant-numeric:tabular-nums;text-align:right}
.dic .isin{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:12px;color:var(--muted)}
.dic tr.off td{opacity:.5}
.dic .sri{display:inline-block;width:22px;text-align:center;border-radius:6px;font-weight:600;font-size:12px;padding:1px 0}
.dic .chip{display:inline-block;padding:1px 9px;border-radius:20px;font-size:11px;border:1px solid var(--line);background:var(--accent-soft);color:var(--accent);font-weight:500}
.dic .none{color:var(--muted);font-size:12px}
.dic .miss{color:var(--muted)}
.dic .meter{display:inline-flex;align-items:center;gap:7px}
.dic .meter .track{width:56px;height:7px;border-radius:5px;background:var(--track);overflow:hidden}
.dic .meter .fill{height:100%;border-radius:5px}
.dic .foot{color:var(--muted);font-size:12.5px;margin-top:18px;line-height:1.6}
.dic .foot a{color:var(--accent)}
</style>
<div class="dic"><div class="inner">
<div class="eyebrow">PRIIPs · Documents d'informations clés</div>
<h1>Top __CAT__ fonds du marché — données DIC</h1>
<p class="lede">SRI, frais et période de détention extraits automatiquement · généré le __GEN__</p>
<div class="cards">
<div class="card"><div class="n">__RETR__<span style="font-size:16px;color:var(--muted)">/__CAT__</span></div><div class="l">DIC récupérés & parsés</div></div>
<div class="card"><div class="n">__COMP__%</div><div class="l">complétude moyenne</div></div>
<div class="card"><div class="n">__COS__</div><div class="l">maisons couvertes</div></div>
<div class="card"><div class="n">__NSRC__</div><div class="l">sources actives</div></div>
</div>
<div class="srcbar" id="srcbar"></div>
<div class="legend" id="legend"></div>
<div style="display:flex;gap:12px;align-items:center;flex-wrap:wrap;margin-bottom:14px">
<input id="q" placeholder="Filtrer : nom du fonds, ISIN, société, source…" aria-label="Filtrer" style="flex:1;min-width:220px;margin-bottom:0">
<label style="display:inline-flex;align-items:center;gap:6px;white-space:nowrap;cursor:pointer;font-size:13px;color:var(--muted)">
<input type="checkbox" id="onlydic" style="width:auto"> Uniquement avec DIC</label>
</div>
<div class="tw"><table><thead><tr>
<th data-k="rank">#</th><th data-k="company_group">Société</th><th data-k="name">Fonds</th>
<th data-k="isin">ISIN</th><th data-k="type">Type</th><th data-k="sri">SRI</th>
<th data-k="ongoing_costs">Frais</th><th data-k="transaction_costs">Transac.</th>
<th data-k="completeness">Complétude</th><th data-k="source">Source</th><th>DIC</th>
</tr></thead><tbody id="tb"></tbody></table></div>
<p class="foot">Catalogue classé par encours ; parsing DIC PDF (Amundi, Vanguard, portails assureurs) + ingestion EPT.
Les fonds « non récupéré » (iShares, JPMorgan, PIMCO…) n'ont pas d'URL DIC publique par ISIN — ils nécessitent un accès fundinfo ou un dépôt d'EPT.
Mise à jour automatique hebdomadaire. · <a href="https://github.com/icarusmagnus/dic-parser">Code &amp; méthode</a></p>
</div></div>
<script>
const DATA=__DATA__;
const PAGES="https://icarusmagnus.github.io/dic-parser/";  // PDF hébergés (lien absolu pour l'Artifact)
const SRI_COL=['','#1f7a4d','#3f9e5a','#8db600','#c9a227','#e08a1e','#dd6b20','#c53030'];
const srcColors={amundi:'#3a5a8c',vanguard:'#8a1f2b',predica:'#1f7a4d','ept-inbox':'#6a3d9a',suravenir:'#0f7d8c'};
const tb=document.getElementById('tb');
const cell=v=>v==null||v===''?'<span class="miss">–</span>':v;
function meter(v){if(v==null)return '<span class="miss">–</span>';
  const c=v>=75?'var(--good)':v>=50?'var(--warn)':'var(--bad)';
  return `<span class="meter"><span class="track"><span class="fill" style="width:${v}%;background:${c}"></span></span><span class="num">${v}%</span></span>`;}
function sri(v){if(v==null||v==='')return '<span class="miss">–</span>';
  return `<span class="sri" style="background:${SRI_COL[v]}22;color:${SRI_COL[v]}">${v}</span>`;}
function row(f){
  const src=f.retrieved?`<span class="chip" style="border-color:${(srcColors[f.source]||'#888')}55;color:${srcColors[f.source]||'var(--accent)'};background:${(srcColors[f.source]||'#888')}14">${f.source}</span>`:'<span class="none">non récupéré</span>';
  return `<tr class="${f.retrieved?'':'off'}">
    <td class="num">${f.rank}</td><td>${f.company_group}</td><td>${f.name}</td>
    <td class="isin">${f.isin}</td><td>${f.type}</td><td>${sri(f.sri)}</td>
    <td class="num">${f.ongoing_costs!=null?f.ongoing_costs+'%':cell(null)}</td>
    <td class="num">${f.transaction_costs!=null?f.transaction_costs+'%':cell(null)}</td>
    <td>${meter(f.retrieved?f.completeness:null)}</td><td>${src}</td>
    <td>${f.dic_url?`<a class="chip" href="${f.dic_url}" target="_blank" rel="noopener">PDF ↗</a>`:'<span class="none">–</span>'}</td></tr>`;
}
let rows=DATA.funds.slice();
const render=()=>tb.innerHTML=rows.map(row).join('');
// barre de sources
const sb=document.getElementById('srcbar'),lg=document.getElementById('legend');
const tot=DATA.retrieved||1;let sbh='',lgh='';
for(const [s,n] of Object.entries(DATA.sources||{})){
  const c=srcColors[s]||'#888';
  sbh+=`<span style="width:${100*n/tot}%;background:${c}"></span>`;
  lgh+=`<span><b style="background:${c}"></b>${s} · ${n}</span>`;
}
lgh+=`<span><b style="background:var(--track)"></b>non récupéré · ${DATA.catalog_size-DATA.retrieved}</span>`;
sb.innerHTML=sbh;lg.innerHTML=lgh;
function applyFilters(){
  const q=document.getElementById('q').value.toLowerCase();
  const onlydic=document.getElementById('onlydic').checked;
  rows=DATA.funds.filter(f=>(!onlydic||f.retrieved)&&[f.name,f.isin,f.company_group,f.source,f.type].join(' ').toLowerCase().includes(q));render();
}
document.getElementById('q').addEventListener('input',applyFilters);
document.getElementById('onlydic').addEventListener('change',applyFilters);
let asc={};
document.querySelectorAll('.dic th').forEach(th=>th.addEventListener('click',()=>{const k=th.dataset.k;asc[k]=!asc[k];
  rows.sort((a,b)=>{let x=a[k],y=b[k];if(x==null)x=asc[k]?1e9:-1e9;if(y==null)y=asc[k]?1e9:-1e9;
    return (typeof x==='number'&&typeof y==='number')?(asc[k]?x-y:y-x):(asc[k]?String(x).localeCompare(y):String(y).localeCompare(x));});render();}));
render();
</script>"""


def main():
    d = json.loads(DATA.read_text())
    html = (BODY.replace("__DATA__", json.dumps(d, ensure_ascii=False))
            .replace("__GEN__", d.get("generated_at", "—"))
            .replace("__RETR__", str(d.get("retrieved", 0)))
            .replace("__CAT__", str(d.get("catalog_size", 0)))
            .replace("__COMP__", str(d.get("avg_completeness", "—")))
            .replace("__COS__", str(d.get("companies_covered", 0)))
            .replace("__NSRC__", str(len(d.get("sources", {})))))
    OUT.write_text(html)
    print(f"artifact body -> {OUT} ({len(html)//1024} Ko)")


if __name__ == "__main__":
    main()
