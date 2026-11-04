"""Regressões do lote de Constituições estaduais / LO-DF (issues #86/#57/#73/#101).

Lê somente arquivos do repositório; não acessa a rede.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import sys
import unittest
from pathlib import Path

from bs4 import BeautifulSoup

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
import nucleo_licitacoes as nl  # noqa: E402

NOTE_RE = re.compile(r"<!-- nota-edicao:inicio -->.*?<!-- nota-edicao:fim -->\s*", re.S)
CAT = ROOT / "metadados" / "constituicoes-estaduais" / "index.json"


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strip_note(md: str) -> str:
    return NOTE_RE.sub("", md, count=1)


def from_marker(folded: str, markers: list[str]) -> str:
    for m in markers:
        i = folded.find(m)
        if i >= 0:
            return folded[i:]
    return folded


class TestConstituicoesEstaduaisLote(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.catalog = json.loads(CAT.read_text(encoding="utf-8"))

    def test_catalog_shape(self) -> None:
        self.assertEqual(self.catalog["tema"], "constituicoes-estaduais")
        self.assertEqual(self.catalog["cobertura"], "parcial")
        ids = {d["norma_id"] for d in self.catalog["documentos"]}
        self.assertIn("br-df-lei-organica-1993-06-08", ids)
        self.assertIn("br-sc-constituicao-1989", ids)
        self.assertIn("br-ba-norma-27298", ids)
        self.assertIn("br-es-norma-33122", ids)
        self.assertIn("br-pr-ato-9779", ids)
        self.assertIn("br-sp-norma-155101", ids)
        for d in self.catalog["documentos"]:
            path = ROOT / d["arquivo"]
            self.assertTrue(path.is_file(), d["arquivo"])
            self.assertIs(d["edicao"]["vigencia_certificada"], False)

    def test_df_lei_organica_fold(self) -> None:
        fontes = json.loads(
            (ROOT / "provas/constituicoes-estaduais/DF/fontes.json").read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        self.assertEqual(sha256_bytes(raw), entry["sha256_conteudo"])
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        div = soup.select_one("#div_texto")
        self.assertIsNotNone(div)
        html_fold = from_marker(
            nl.strip_fold(div.get_text(" ")),
            ["preambulo", "leiaorganicadodistritofederal"],
        )
        md = strip_note(
            (ROOT / "estaduais/DF/br-df-lei-organica-1993-06-08.md").read_text(encoding="utf-8")
        )
        md_fold = from_marker(
            nl.strip_fold(nl.md_text_all(md)),
            ["preambulo", "leiaorganicadodistritofederal"],
        )
        self.assertEqual(md_fold, html_fold)
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_markdown"])

    def test_sc_constituicao_fold(self) -> None:
        fontes = json.loads(
            (ROOT / "provas/constituicoes-estaduais/SC/fontes.json").read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        self.assertEqual(sha256_bytes(raw), entry["sha256_conteudo"])
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        body = soup.body
        for tag in body.find_all(["script", "style"]):
            tag.decompose()
        html_fold = from_marker(
            nl.strip_fold(body.get_text(" ")),
            ["constituicaodoestadodesantacatarina", "preambulo"],
        )
        md = strip_note(
            (ROOT / "estaduais/SC/br-sc-constituicao-1989.md").read_text(encoding="utf-8")
        )
        md_fold = from_marker(
            nl.strip_fold(nl.md_text_all(md)),
            ["constituicaodoestadodesantacatarina", "preambulo"],
        )
        self.assertTrue(md_fold == html_fold or md_fold in html_fold or html_fold in md_fold)
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_markdown"])

    def test_ba_source_hash(self) -> None:
        fontes = json.loads(
            (ROOT / "provas/constituicoes-estaduais/BA/fontes.json").read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        self.assertEqual(sha256_bytes(raw), "3af9d63a7899618595d6b0f38fa0eeaaa2b6a1e1c74c1e4a269b666ac2520e1e")
        md = (ROOT / "estaduais/BA/br-ba-norma-27298.md").read_text(encoding="utf-8")
        self.assertIn("CONSTITUIÇÃO DO ESTADO DA BAHIA", md)
        self.assertIn("nota-edicao:inicio", md)
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_markdown"])


class TestLicitacoesLocaisIndex(unittest.TestCase):
    def test_index_links_uf_catalogs(self) -> None:
        idx = json.loads((ROOT / "metadados/licitacoes-locais/index.json").read_text(encoding="utf-8"))
        self.assertEqual(idx["issue"], 57)
        self.assertEqual(idx["cobertura"], "parcial")
        ufs = {u["uf"] for u in idx["ufs"]}
        self.assertEqual(ufs, {"PR", "SP", "MG", "GO"})
        for u in idx["ufs"]:
            self.assertTrue((ROOT / u["catalogo"]).is_file())
            for d in u["documentos"]:
                self.assertTrue((ROOT / d["arquivo"]).is_file(), d["arquivo"])
    def test_bh_complementary_decrees_published(self) -> None:
        cat = json.loads((ROOT / "metadados/licitacoes-locais/MG.json").read_text(encoding="utf-8"))
        ids = {d["norma_id"] for d in cat["documentos"]}
        for nid in [
            "br-municipal-3106200-decreto-2021-12-21-17813",
            "br-municipal-3106200-decreto-2022-09-20-18096",
            "br-municipal-3106200-decreto-2023-01-19-18240",
            "br-municipal-3106200-decreto-2023-01-25-18242",
            "br-municipal-3106200-decreto-2023-03-28-18289",
        ]:
            self.assertIn(nid, ids)
            path = next(d["arquivo"] for d in cat["documentos"] if d["norma_id"] == nid)
            self.assertTrue((ROOT / path).is_file())
        for p in idx["prioritarios_issue"]:
            self.assertEqual(p["status"].split("-")[0], "publicado")


class TestRegulamentacao14133Ufs(unittest.TestCase):
    def test_twenty_seven_ufs(self) -> None:
        idx = json.loads(
            (ROOT / "metadados/regulamentacao-14133-ufs/index.json").read_text(encoding="utf-8")
        )
        self.assertEqual(idx["issue"], 73)
        self.assertEqual(len(idx["ufs"]), 27)
        pr = next(u for u in idx["ufs"] if u["uf"] == "PR")
        self.assertEqual(pr["status_acervo"], "decreto-geral-publicado")
        self.assertTrue((ROOT / pr["decretos_14133"][0]["arquivo"]).is_file())


class TestCapitaisInventario(unittest.TestCase):
    def test_twenty_six_capitals(self) -> None:
        idx = json.loads(
            (ROOT / "metadados/capitais-lei-organica-14133/index.json").read_text(encoding="utf-8")
        )
        self.assertEqual(idx["issue"], 101)
        self.assertEqual(len(idx["capitais"]), 26)
        sp = next(c for c in idx["capitais"] if c["ibge"] == "3550308")
        self.assertNotEqual(sp["lei_organica"], "ausente")
        self.assertEqual(sp["decreto_14133_carater"], "geral")
        self.assertTrue((ROOT / sp["lei_organica"]).is_file())
        self.assertTrue((ROOT / sp["decreto_14133"]).is_file())



if __name__ == "__main__":
    unittest.main()
