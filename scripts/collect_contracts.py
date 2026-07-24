"""Collecte les DIC des CONTRATS (assurance-vie/capi/PER) chez Cardif.

Distinct des DIC de fonds : ici on récupère le DIC de l'enveloppe elle-même.
Portail Liferay document-information-cle.cardif.fr, endpoint manageProductsData.
Colonnes datatable : name, status, closingDateLabel, closingDateSort, link(=DIC), copy, support.

Sortie : data/contracts.json (nom, réseau, type, dic_url). À lancer en CI (réseau stable).
"""
import http.cookiejar
import json
import urllib.parse
import urllib.request
from pathlib import Path

HOST = "https://document-information-cle.cardif.fr"
P = "com_bpc_pcf_priips_views_PriipsContractsPortlet"
COLS = ["name", "status", "closingDateLabel", "closingDateSort", "link", "copy", "support"]
NETWORKS = ["partenaires", "cgpi", "retail", "aep", "sg"]
OUT = Path(__file__).resolve().parent.parent / "data" / "contracts.json"


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


def main():
    contracts, seen = [], set()
    for net in NETWORKS:
        rows, info = _filter(_opener(), net)
        n = 0
        for r in rows:
            link = r.get("link")
            if link and link not in ("null", "") and link not in seen:
                seen.add(link)
                contracts.append({"name": r.get("name"), "network": net,
                                  "type": r.get("legalNatureLabel"), "dic_url": link})
                n += 1
        print(f"[{net}] {info} -> {len(rows)} lignes, {n} DIC contrats nouveaux")
    OUT.write_text(json.dumps(contracts, ensure_ascii=False, indent=2))
    print(f"\nTOTAL: {len(contracts)} DIC de contrats -> {OUT.name}")
    for c in contracts[:8]:
        print(f"  {c['name'][:45]:45} {c['dic_url'][:70]}")


if __name__ == "__main__":
    main()
