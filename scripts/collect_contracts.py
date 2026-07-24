"""Collecte les DIC des CONTRATS (assurance-vie/capi/PER) chez Cardif.

Distinct des DIC de fonds : ici on récupère le DIC de l'enveloppe elle-même.
Portail Liferay document-information-cle.cardif.fr, endpoint manageProductsData.
Colonnes datatable : name, status, closingDateLabel, closingDateSort, link(=DIC), copy, support.

Sortie : data/contracts.json (nom, réseau, type, dic_url). À lancer en CI (réseau stable).
"""
import http.cookiejar
import json
import sys
import urllib.parse
import urllib.request
from datetime import datetime, timezone
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from dic_parser.kid_pdf import parse_kid_pdf  # noqa: E402

HOST = "https://document-information-cle.cardif.fr"
P = "com_bpc_pcf_priips_views_PriipsContractsPortlet"
COLS = ["name", "status", "closingDateLabel", "closingDateSort", "link", "copy", "support"]
NETWORKS = ["partenaires", "cgpi", "retail", "aep", "sg"]

# Suravenir : DIC de contrats à URL numérique énumérable (IDs découverts par balayage).
SURAVENIR_URL = "https://espaceclient.suravenir.fr/o/documents/WsPUS/DIC_CONTRAT/DIC-{}.pdf"
SURAVENIR_IDS = [58, 59, 60, 63, 64, 68, 71, 82, 93]

DATA = Path(__file__).resolve().parent.parent / "data"
CORPUS = DATA / "contract_corpus"
OUT = DATA / "contracts_data.json"


def _opener():
    cj = http.cookiejar.CookieJar()
    op = urllib.request.build_opener(urllib.request.HTTPCookieProcessor(cj))
    op.addheaders = [("User-Agent", "Mozilla/5.0")]
    return op


def _filter(op, net):
    # session
    try:
        op.open(urllib.request.Request(f"{HOST}/{net}/contrats",
                headers={"User-Agent": "Mozilla/5.0"}), timeout=30).read(300)
    except Exception as e:  # noqa: BLE001
        return [], f"session KO: {e}"
    body = {f"_{P}_action": "filter", "draw": "1", "start": "0", "length": "500",
            "order[0][column]": "0", "order[0][dir]": "asc",
            "search[value]": "", "search[regex]": "false",
            "contract": "", "contractType": "", "page": ""}
    for i, c in enumerate(COLS):
        body[f"columns[{i}][data]"] = c
        body[f"columns[{i}][name]"] = ""
        body[f"columns[{i}][searchable]"] = "true"
        body[f"columns[{i}][orderable]"] = "true"
        body[f"columns[{i}][search][value]"] = ""
        body[f"columns[{i}][search][regex]"] = "false"
    url = (f"{HOST}/{net}/contrats?p_p_id={P}&p_p_lifecycle=2&p_p_state=normal"
           f"&p_p_mode=view&p_p_resource_id=%2FmanageProductsData"
           f"&p_p_cacheability=cacheLevelPage&_{P}_action=filter")
    req = urllib.request.Request(url, data=urllib.parse.urlencode(body).encode(),
                                 headers={"X-Requested-With": "XMLHttpRequest",
                                          "Content-Type": "application/x-www-form-urlencoded"})
    try:
        resp = op.open(req, timeout=40).read().decode("utf-8", "replace")
        return json.loads(resp).get("data", []), f"{len(resp)}o"
    except Exception as e:  # noqa: BLE001
        return [], f"filter KO: {e}"


def _download(url):
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=30) as r:
            data = r.read(4_000_000)
        return data if data[:5] == b"%PDF" else None
    except Exception:  # noqa: BLE001
        return None


def main():
    # 1a) Cardif : liste des contrats + URL de leur DIC (portail Liferay)
    contracts, seen = [], set()
    for net in NETWORKS:
        rows, info = _filter(_opener(), net)
        n = 0
        for r in rows:
            link = r.get("link")
            if link and link not in ("null", "") and link not in seen:
                seen.add(link)
                contracts.append({"insurer": "Cardif", "name": r.get("name"), "network": net,
                                  "type": r.get("legalNatureLabel"), "dic_url": link})
                n += 1
        print(f"[Cardif/{net}] {info} -> {len(rows)} lignes, {n} contrats")

    # 1b) Suravenir : DIC de contrats énumérés (nom récupéré du PDF)
    for i in SURAVENIR_IDS:
        url = SURAVENIR_URL.format(i)
        if url not in seen:
            seen.add(url)
            contracts.append({"insurer": "Suravenir", "name": None, "network": f"DIC-{i}",
                              "type": "Contrat", "dic_url": url})
    print(f"[Suravenir] {len(SURAVENIR_IDS)} contrats énumérés")

    # 2) télécharge + parse chaque DIC de contrat
    CORPUS.mkdir(parents=True, exist_ok=True)
    for idx, c in enumerate(contracts):
        data = _download(c["dic_url"])
        if not data:
            c["retrieved"] = False
            continue
        c["retrieved"] = True
        pdf = CORPUS / f"{c['insurer']}_{idx}.pdf"
        pdf.write_bytes(data)
        try:
            k = parse_kid_pdf(pdf)
            if not c.get("name"):
                c["name"] = k.product_name or f"{c['insurer']} contrat {c['network']}"
            c.update(sri=k.sri, rhp_years=k.rhp_years, ongoing_costs=k.costs.ongoing_costs,
                     completeness=k.completeness(), product_name=k.product_name)
        except Exception as e:  # noqa: BLE001
            c["warnings"] = str(e)[:60]

    got = [c for c in contracts if c.get("retrieved")]
    payload = {"generated_at": datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M UTC"),
               "count": len(got), "total": len(contracts), "contracts": contracts}
    OUT.write_text(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nTOTAL: {len(got)}/{len(contracts)} DIC de contrats récupérés & parsés -> {OUT.name}")


if __name__ == "__main__":
    main()
