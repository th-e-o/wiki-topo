"""Collecte des métadonnées arXiv (OAI-PMH) pour les articles de topologie.

Usage : python -m wiki.harvest --month 2026-09
        python -m wiki.harvest --from 2026-09-01 --until 2026-09-30
        python -m wiki.harvest --source web --month 2026-09 [--limit 300]

--source oai (défaut) passe par oaipmh.arxiv.org (OAI-PMH, voie recommandée) ;
--source web lit les listings mensuels et les pages /abs/ de arxiv.org, quand
seul ce domaine est accessible.
Sortie : data/papers.jsonl (une ligne JSON par article, dédoublonnée par id)
"""
import argparse
import json
import re
import time
import xml.etree.ElementTree as ET

import requests

from . import config

NS = {
    "oai": "http://www.openarchives.org/OAI/2.0/",
    "ax": "http://arxiv.org/OAI/arXiv/",
}


def _text(el, path):
    found = el.find(path, NS)
    return " ".join(found.text.split()) if found is not None and found.text else ""


def parse_record(rec):
    meta = rec.find("oai:metadata/ax:arXiv", NS)
    if meta is None:  # enregistrement supprimé
        return None
    cats = _text(meta, "ax:categories").split()
    authors = []
    for a in meta.findall("ax:authors/ax:author", NS):
        name = " ".join(filter(None, [_text(a, "ax:forenames"), _text(a, "ax:keyname")]))
        authors.append(name)
    return {
        "id": _text(meta, "ax:id"),
        "title": _text(meta, "ax:title"),
        "abstract": _text(meta, "ax:abstract"),
        "authors": authors,
        "categories": cats,
        "primary": cats[0] if cats else "",
        "created": _text(meta, "ax:created"),
        "updated": _text(meta, "ax:updated"),
        "license": _text(meta, "ax:license"),
        "msc": _text(meta, "ax:msc-class"),
        "doi": _text(meta, "ax:doi"),
    }


def is_topology(paper):
    return any(c in config.CATEGORIES for c in paper["categories"])


def fetch(session, params):
    while True:
        r = session.get(config.OAI_URL, params=params, timeout=120)
        if r.status_code == 503:  # arXiv demande d'attendre
            wait = int(r.headers.get("Retry-After", "30"))
            print(f"  503, nouvelle tentative dans {wait} s")
            time.sleep(wait)
            continue
        r.raise_for_status()
        return ET.fromstring(r.content)


def months_between(date_from, date_until):
    """{'2609', '2610'} : préfixes d'identifiants arXiv des mois couverts."""
    y, m = int(date_from[:4]), int(date_from[5:7])
    end = (int(date_until[:4]), int(date_until[5:7]))
    out = set()
    while (y, m) <= end:
        out.add(f"{y % 100:02d}{m:02d}")
        y, m = (y + 1, 1) if m == 12 else (y, m + 1)
    return out


def harvest(date_from, date_until, limit=None, new_only=True, prefixes=None):
    """OAI-PMH filtre sur la date de modification : sans --include-updates, on ne
    garde que les articles déposés pendant la période (préfixe AAMM de l'identifiant)."""
    prefixes = prefixes or months_between(date_from, date_until)
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    params = {"verb": "ListRecords", "metadataPrefix": "arXiv", "set": config.OAI_SET,
              "from": date_from, "until": date_until}
    papers = {}
    page = 0
    while True:
        root = fetch(session, params)
        err = root.find("oai:error", NS)
        if err is not None:
            if err.get("code") == "noRecordsMatch":
                break
            raise RuntimeError(f"OAI-PMH : {err.get('code')} {err.text}")
        page += 1
        for rec in root.iterfind("oai:ListRecords/oai:record", NS):
            p = parse_record(rec)
            if p and is_topology(p) and (not new_only or p["id"][:4] in prefixes):
                papers[p["id"]] = p
        print(f"  page {page} : {len(papers)} articles de topologie")
        token = root.find("oai:ListRecords/oai:resumptionToken", NS)
        if (limit and len(papers) >= limit) or token is None or not (token.text or "").strip():
            break
        params = {"verb": "ListRecords", "resumptionToken": token.text.strip()}
        time.sleep(config.DELAY_SECONDS)
    return list(papers.values())[:limit] if limit else list(papers.values())


def parse_abs_page(paper_id, html_bytes):
    from lxml import html as lh
    doc = lh.fromstring(html_bytes)
    meta = lambda name: [m.get("content", "") for m in doc.xpath(f'//meta[@name="{name}"]')]
    subjects = " ".join(doc.xpath('//td[contains(@class,"subjects")]//text()'))
    cats = re.findall(r"\(([a-z\-]+(?:\.[A-Za-z\-]+)?)\)", subjects)
    lic = doc.xpath('//div[@class="abs-license"]/a/@href')
    msc = " ".join(" ".join(doc.xpath('//td[contains(@class,"msc-classes")]//text()')).split())
    date = (meta("citation_date") or [""])[0].replace("/", "-")
    return {
        "id": paper_id,
        "title": " ".join((meta("citation_title") or [""])[0].split()),
        "abstract": " ".join((meta("citation_abstract") or [""])[0].split()),
        "authors": [" ".join(reversed([x.strip() for x in a.split(",", 1)])) for a in meta("citation_author")],
        "categories": cats,
        "primary": cats[0] if cats else "",
        "created": date,
        "updated": (meta("citation_online_date") or [""])[0].replace("/", "-"),
        "license": lic[0] if lic else "http://arxiv.org/licenses/nonexclusive-distrib/1.0/",
        "msc": msc,
        "doi": "",
    }


def harvest_web(month, limit=None, known=()):
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    ids = []
    for cat in config.CATEGORIES:
        r = session.get(f"https://arxiv.org/list/{cat}/{month}", params={"skip": 0, "show": 2000}, timeout=120)
        r.raise_for_status()
        found = re.findall(r'href ?="/abs/([^"v]+)(?:v\d+)?"', r.text)
        print(f"  {cat} {month} : {len(found)} entrées")
        ids += [i for i in found if i not in ids]
        time.sleep(config.DELAY_SECONDS)
    ids = [i for i in ids if i not in known]
    if limit:
        ids = ids[:limit]
    papers = []
    for n, pid in enumerate(ids, 1):
        r = session.get(f"https://arxiv.org/abs/{pid}", timeout=120)
        time.sleep(config.DELAY_SECONDS)
        if r.status_code != 200:
            print(f"  {pid} : HTTP {r.status_code}")
            continue
        p = parse_abs_page(pid, r.content)
        if is_topology(p):
            papers.append(p)
        if n % 25 == 0:
            print(f"  {n}/{len(ids)} pages lues")
    return papers


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--source", choices=["oai", "web"], default="oai")
    ap.add_argument("--from", dest="date_from", help="AAAA-MM-JJ (oai)")
    ap.add_argument("--until", dest="date_until", help="AAAA-MM-JJ (oai)")
    ap.add_argument("--month", help="AAAA-MM : articles déposés ce mois-là")
    ap.add_argument("--limit", type=int, help="nombre maximal d'articles")
    ap.add_argument("--include-updates", action="store_true",
                    help="(oai) garder aussi les anciens articles mis à jour pendant la période")
    args = ap.parse_args()

    config.DATA.mkdir(parents=True, exist_ok=True)
    out = config.DATA / "papers.jsonl"
    existing = {}
    if out.exists():
        for line in out.read_text().splitlines():
            p = json.loads(line)
            existing[p["id"]] = p
    if args.source == "web":
        if not args.month:
            ap.error("--month est requis avec --source web")
        new = harvest_web(args.month, args.limit, known=existing)
    elif args.month:
        # un article est daté du jour de son annonce : on prend 5 jours de marge
        y, m = map(int, args.month.split("-"))
        nxt = f"{y + (m == 12)}-{m % 12 + 1:02d}-05"
        new = harvest(f"{args.month}-01", nxt, args.limit, not args.include_updates,
                      prefixes={f"{y % 100:02d}{m:02d}"})
    else:
        if not (args.date_from and args.date_until):
            ap.error("--month, ou --from et --until, sont requis avec --source oai")
        new = harvest(args.date_from, args.date_until, args.limit, not args.include_updates)
    for p in new:
        existing[p["id"]] = p
    out.write_text("".join(json.dumps(p, ensure_ascii=False) + "\n" for p in existing.values()))
    print(f"{len(existing)} articles dans {out}")


if __name__ == "__main__":
    main()
