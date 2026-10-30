"""Génération du site statique (une page, navigation par ancre).

Usage : python -m wiki.build_site
Sortie : site/index.html (page autonome) et site/artifact.html (même contenu,
sans squelette <html>, pour une publication en Artifact claude.ai).
"""
import datetime as dt
import html
import json
import re

from . import config
from .render import latex_to_html

LICENSES = [
    ("publicdomain/zero", "CC0"), ("licenses/by-nc-nd", "CC BY-NC-ND"),
    ("licenses/by-nc-sa", "CC BY-NC-SA"), ("licenses/by-sa", "CC BY-SA"),
    ("licenses/by/", "CC BY"), ("nonexclusive-distrib", "Licence arXiv (non exclusive)"),
]


def short_license(url):
    for frag, name in LICENSES:
        if frag in url:
            ver = re.search(r"/(\d\.\d)/?$", url)
            return f"{name} {ver.group(1)}" if ver and name.startswith("CC") else name
    return "Licence non précisée"


CHUNK_BYTES = 6_000_000

MOIS = ["janvier", "février", "mars", "avril", "mai", "juin", "juillet", "août",
        "septembre", "octobre", "novembre", "décembre"]


def month_label(yymm):
    return f"{MOIS[int(yymm[2:]) - 1]} 20{yymm[:2]}"


def anchor(pid):
    return "article-" + re.sub(r"[^A-Za-z0-9]+", "-", pid)


def inline(tex, macros=None):
    """Titre ou résumé -> HTML (sans les <div> de paragraphe)."""
    h = latex_to_html(tex, macros)
    return re.sub(r'^<div class="para">|</div>$', "", h).replace('</div><div class="para">', "<br>")


def safe_html(body, macros):
    try:
        return latex_to_html(body, macros)
    except Exception as e:  # LaTeX inhabituel : on garde la source brute
        print(f"  rendu impossible ({e!r}), source brute conservée")
        return '<div class="para">' + html.escape(body) + "</div>"


def main():
    papers = [json.loads(l) for l in (config.DATA / "papers.jsonl").read_text().splitlines()]
    st_path = config.DATA / "statements.jsonl"
    statements = [json.loads(l) for l in st_path.read_text().splitlines()] if st_path.exists() else []
    concepts = json.loads((config.DATA / "concepts.json").read_text())
    mac_path = config.DATA / "macros.json"
    macros = json.loads(mac_path.read_text()) if mac_path.exists() else {}

    sts_by_paper = {}
    out_st, bodies = [], {}
    for i, s in enumerate(statements):
        sts_by_paper.setdefault(s["paper"], []).append(i)
        out_st.append({
            "p": s["paper"], "k": s["kind"],
            "t": inline(s["title"], macros.get(s["paper"])) if s["open"] and s["title"] else "",
            "h": None, "tr": s["truncated"],
        })
        # seuls les articles sous licence ouverte voient leurs énoncés reproduits
        if s["open"]:
            bodies[i] = safe_html(s["body"], macros.get(s["paper"]))
    out_papers = {}
    for p in papers:
        out_papers[p["id"]] = {
            "a": anchor(p["id"]), "t": inline(p["title"]), "au": [html.escape(a) for a in p["authors"]],
            "d": p["created"], "c": p["categories"], "lic": short_license(p["license"]),
            "licUrl": p["license"], "open": any(l in p["license"] for l in config.OPEN_LICENSES),
            "abs": inline(p["abstract"]), "sts": sts_by_paper.get(p["id"], []),
            "msc": html.escape(p.get("msc", "")),
        }
    # période d'après les identifiants (AAMM.xxxxx = mois de dépôt sur arXiv)
    months = sorted({p["id"][:4] for p in papers if re.match(r"\d{4}\.", p["id"])})
    data = {
        "built": dt.date.today().isoformat(),
        "period": [month_label(months[0]), month_label(months[-1])] if months else ["", ""],
        "branches": config.CATEGORIES,
        "kinds": config.ENVIRONMENTS,
        "concepts": [{
            "s": c["slug"], "en": html.escape(c["key"]), "fr": html.escape(c["fr"] or ""),
            "b": c["branch"], "src": c["source"], "al": [html.escape(a) for a in c["aliases"]],
            "p": c["papers"], "df": c["definitions"], "st": c["statements"], "rel": c["related"],
        } for c in concepts],
        "papers": out_papers,
        "statements": out_st,
        "withSource": len({s["paper"] for s in statements}),
    }
    dump = lambda o: json.dumps(o, ensure_ascii=False, separators=(",", ":")).replace("</", "<\\/")
    blob = dump(data)

    # le texte des énoncés part dans des fichiers séparés (limite de 16 Mo par fichier publié)
    chunk_dir = config.SITE / "data"
    chunk_dir.mkdir(parents=True, exist_ok=True)
    for old_chunk in chunk_dir.glob("enonces-*.js"):
        old_chunk.unlink()
    chunks, cur, size = [], {}, 0
    for i, h in bodies.items():
        cur[i] = h
        size += len(h.encode())
        if size > CHUNK_BYTES:
            chunks.append(cur); cur, size = {}, 0
    if cur:
        chunks.append(cur)
    tags = []
    for n, ch in enumerate(chunks):
        name = f"enonces-{n:02d}.js"
        (chunk_dir / name).write_text(f"Object.assign(window.WIKI_H = window.WIKI_H || {{}}, {dump(ch)});\n")
        tags.append(f'<script src="data/{name}"></script>')

    tpl = (config.ROOT / "templates" / "page.html").read_text()
    css = (config.ROOT / "static" / "style.css").read_text()
    js = (config.ROOT / "static" / "app.js").read_text()
    body = (tpl.replace("/*STYLE*/", css).replace("/*APP*/", js)
               .replace("/*DATA*/", f"window.WIKI = {blob};")
               .replace("<!--CHUNKS-->", "\n".join(tags)))
    config.SITE.mkdir(parents=True, exist_ok=True)
    (config.SITE / "artifact.html").write_text(body)
    (config.SITE / "index.html").write_text(
        '<!doctype html>\n<html lang="fr">\n<head>\n<meta charset="utf-8">\n'
        '<meta name="viewport" content="width=device-width, initial-scale=1, viewport-fit=cover">\n'
        "</head>\n<body>\n" + body + "\n</body>\n</html>\n")
    size = (config.SITE / "index.html").stat().st_size / 1e6
    print(f"site/index.html : {len(concepts)} concepts, {len(papers)} articles, "
          f"{len(statements)} énoncés, page {size:.1f} Mo + {len(chunks)} fichier(s) d'énoncés")


if __name__ == "__main__":
    main()
