"""Téléchargement et décompression des sources LaTeX (e-print) des articles.

Usage : python -m wiki.fetch_sources [--max 200] [--open-only]
Les archives sont traitées comme des données non fiables : extraction filtrée
(pas de liens, pas de chemins hors du dossier), seuls les .tex/.sty/.bbl sont gardés.
"""
import argparse
import gzip
import io
import json
import tarfile
import time

import requests

from . import config

KEEP_SUFFIXES = (".tex", ".sty", ".bbl", ".ltx")
MAX_FILE_BYTES = 5_000_000


def is_open(paper):
    return any(l in paper.get("license", "") for l in config.OPEN_LICENSES)


def safe_dir(paper_id):
    return paper_id.replace("/", "_")


def unpack(blob, dest):
    """Décompresse un e-print : tar.gz, ou simple .tex gzippé."""
    dest.mkdir(parents=True, exist_ok=True)
    try:
        data = gzip.decompress(blob)
    except OSError:
        data = blob  # déjà non compressé (ou PDF seul)
    if data[:4] == b"%PDF":
        return 0
    try:
        with tarfile.open(fileobj=io.BytesIO(data)) as tar:
            n = 0
            for m in tar.getmembers():
                if not m.isfile() or m.size > MAX_FILE_BYTES:
                    continue
                if not m.name.lower().endswith(KEEP_SUFFIXES):
                    continue
                tar.extract(m, dest, filter="data")
                n += 1
            return n
    except tarfile.ReadError:
        (dest / "main.tex").write_bytes(data[:MAX_FILE_BYTES])
        return 1


def main():
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--max", type=int, default=200, help="nombre maximal de téléchargements")
    ap.add_argument("--open-only", action="store_true",
                    help="ne télécharger que les articles sous licence ouverte")
    args = ap.parse_args()

    papers = [json.loads(l) for l in (config.DATA / "papers.jsonl").read_text().splitlines()]
    papers.sort(key=lambda p: not is_open(p))  # licences ouvertes d'abord
    if args.open_only:
        papers = [p for p in papers if is_open(p)]
    session = requests.Session()
    session.headers["User-Agent"] = config.USER_AGENT
    done = 0
    for p in papers:
        dest = config.SRC / safe_dir(p["id"])
        if dest.exists():
            continue
        if done >= args.max:
            break
        r = session.get(config.EPRINT_URL.format(id=p["id"]), timeout=120)
        time.sleep(config.DELAY_SECONDS)
        done += 1
        if r.status_code != 200:
            print(f"  {p['id']} : HTTP {r.status_code}")
            continue
        config.RAW.mkdir(parents=True, exist_ok=True)
        (config.RAW / safe_dir(p["id"])).write_bytes(r.content)
        n = unpack(r.content, dest)
        print(f"  {p['id']} : {n} fichier(s) source")
    print(f"{done} téléchargement(s)")


if __name__ == "__main__":
    main()
