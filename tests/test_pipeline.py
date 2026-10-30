"""Test de l'extraction et du rendu sur un petit projet LaTeX : python -m tests.test_pipeline"""
from pathlib import Path

from wiki import latex
from wiki.extract import normalize_term
from wiki.render import latex_to_html

d = Path(__file__).parent / "fixtures" / "sample"
tex = latex.load_project(d)
envs = latex.theorem_envs(tex)
assert envs["defi"] == "definition" and envs["conj*"] == "conjecture", envs
mac = latex.macros(tex)
assert mac["\\Z"] == "\\mathbb{Z}" and mac["\\Homeo"] == "\\operatorname{Homeo}", mac
found = latex.environments(tex, envs)
kinds = [k for k, *_ in found]
assert kinds == ["definition", "theorem", "conjecture"], kinds
terms = {normalize_term(t) for t in latex.defined_terms(found[0][3])}
assert "slice knot" in terms, terms
assert "<em>4-ball genera</em>" in latex_to_html(found[0][3], mac)
assert found[1][2] == "Main"
h = latex_to_html(found[1][3], mac)
assert "\\left|\\sigma(K)\\right|" in h and "\\mathbb{Z}" in h and "[réf.]" in h, h
assert "comment" not in h and "\\label" not in h, h
h2 = latex_to_html(found[0][3], mac)
assert "\\begin{aligned}" in h2 and "\\label" not in h2, h2
h3 = latex_to_html(found[2][3], mac)
assert "<strong>fibered knot</strong>" in h3 and "“nice”—compare" in h3 and "<ul><li>" in h3, h3
print("termes :", terms)
print(h, h2, h3, sep="\n")
print("OK")
