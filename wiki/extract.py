"""Extraction des définitions, théorèmes, conjectures… depuis les sources LaTeX.

Usage : python -m wiki.extract
Sortie : data/statements.jsonl
"""
import json
import re

from . import config, latex
from .fetch_sources import is_open, safe_dir
from .render import plain_text

ARTICLES = re.compile(r"^(?:an?|the|our|we call|call)\s+", re.I)


def normalize_term(raw):
    """« Homotopy groups » -> « homotopy group » ; None si inexploitable."""
    if "$" in raw or "\\(" in raw:
        return None  # terme contenant des formules : écarté dans ce prototype
    t = plain_text(raw).lower()
    t = re.sub(r"[^a-z0-9\-' ]", " ", t)
    t = re.sub(r"-{2,}", "-", t)
    t = ARTICLES.sub("", " ".join(t.split())).strip(" -'")
    words = t.split()
    if not words or len(t) < 4 or len(words) > 5 or not re.search(r"[a-z]{3}", t):
        return None
    last = words[-1]
    if last.endswith("ies") and len(last) > 4:
        last = last[:-3] + "y"
    elif last.endswith(("xes", "ches", "shes")):
        last = last[:-2]
    elif last.endswith("s") and not last.endswith(("ss", "us", "is", "ous", "ics")):
        last = last[:-1]
    words[-1] = last
    return " ".join(words)


def extract_paper(paper):
    d = config.SRC / safe_dir(paper["id"])
    if not d.exists():
        return [], {}
    tex = latex.load_project(d)
    if not tex:
        return [], {}
    envs = latex.theorem_envs(tex)
    macros = latex.macros(latex.preamble_files(d) + "\n" + tex)
    out = []
    for n, (kind, env, title, body) in enumerate(latex.environments(tex, envs)):
        if kind not in config.ENVIRONMENTS or len(body) < 20:
            continue
        terms = []
        if kind == "definition":
            terms = sorted({t for t in map(normalize_term, latex.defined_terms(body)) if t})
        out.append({
            "paper": paper["id"],
            "n": n,
            "kind": kind,
            "title": title,
            "body": body[:config.MAX_STATEMENT_CHARS],
            "truncated": len(body) > config.MAX_STATEMENT_CHARS,
            "terms": terms,
            "open": is_open(paper),
        })
    return out, macros


def main():
    papers = [json.loads(l) for l in (config.DATA / "papers.jsonl").read_text().splitlines()]
    statements, all_macros = [], {}
    with_src = 0
    for p in papers:
        st, mac = extract_paper(p)
        if st or mac:
            with_src += 1
        statements += st
        if mac:
            all_macros[p["id"]] = mac
    (config.DATA / "statements.jsonl").write_text(
        "".join(json.dumps(s, ensure_ascii=False) + "\n" for s in statements))
    (config.DATA / "macros.json").write_text(json.dumps(all_macros, ensure_ascii=False))
    kinds = {}
    for s in statements:
        kinds[s["kind"]] = kinds.get(s["kind"], 0) + 1
    print(f"{with_src} articles analysés, {len(statements)} énoncés : {kinds}")


if __name__ == "__main__":
    main()
