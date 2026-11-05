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
        self.assertIn("br-pe-constituicao-1989", ids)
        self.assertIn("br-es-norma-33122", ids)
        self.assertIn("br-pr-ato-9779", ids)
        self.assertIn("br-sp-norma-155101", ids)
        self.assertNotIn("PE", self.catalog["ausentes"])
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
        md_full = (ROOT / "estaduais/DF/br-df-lei-organica-1993-06-08.md").read_text(encoding="utf-8")
        md = strip_note(md_full)
        md_fold = from_marker(
            nl.strip_fold(nl.md_text_all(md)),
            ["preambulo", "leiaorganicadodistritofederal"],
        )
        self.assertEqual(md_fold, html_fold)
        self.assertEqual(sha256_bytes(md_full.encode("utf-8")), entry["sha256_markdown"])
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_corpo_markdown"])

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
        md_full = (ROOT / "estaduais/SC/br-sc-constituicao-1989.md").read_text(encoding="utf-8")
        md = strip_note(md_full)
        md_fold = from_marker(
            nl.strip_fold(nl.md_text_all(md)),
            ["constituicaodoestadodesantacatarina", "preambulo"],
        )
        self.assertTrue(md_fold == html_fold or md_fold in html_fold or html_fold in md_fold)
        self.assertEqual(sha256_bytes(md_full.encode("utf-8")), entry["sha256_markdown"])
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_corpo_markdown"])

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

    def test_pe_constituicao_fold(self) -> None:
        fontes = json.loads(
            (ROOT / "provas/constituicoes-estaduais/PE/fontes.json").read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        self.assertEqual(sha256_bytes(raw), entry["sha256_conteudo"])
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        div = soup.select_one("#divTexto")
        self.assertIsNotNone(div)
        for tag in div.find_all(["script", "style"]):
            tag.decompose()

        def plain_blocks(container) -> str:
            blocks = []
            for p in container.find_all(["p", "h1", "h2", "h3", "h4"]):
                parent = p.parent
                skip = False
                while parent is not None and parent is not container:
                    if getattr(parent, "name", None) in ("p", "h1", "h2", "h3", "h4", "li"):
                        skip = True
                        break
                    parent = parent.parent
                if skip:
                    continue
                t = re.sub(r"[ \t]{2,}", " ", p.get_text("", strip=False).replace("\xa0", " ")).strip()
                if t:
                    blocks.append(t)
            return "\n\n".join(blocks) + "\n"

        plain = plain_blocks(div)
        lines = plain.split("\n\n")
        start = next(
            i
            for i, ln in enumerate(lines)
            if re.search(r"CONSTITUI[CÇ][AÃ]O DO\s+ESTADO DE PERNAMBUCO", ln, re.I)
        )
        plain = "\n\n".join(lines[start:])
        if not plain.endswith("\n"):
            plain += "\n"
        md_full = (ROOT / "estaduais/PE/br-pe-constituicao-1989.md").read_text(encoding="utf-8")
        md = strip_note(md_full)
        self.assertEqual(nl.strip_fold(plain), nl.strip_fold(nl.md_text_all(md)))
        self.assertEqual(sha256_bytes(md_full.encode("utf-8")), entry["sha256_markdown"])
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_corpo_markdown"])


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
        for p in idx["prioritarios_issue"]:
            self.assertEqual(p["status"].split("-")[0], "publicado")
        mg = next(u for u in idx["ufs"] if u["uf"] == "MG")
        mg_ids = {d["norma_id"] for d in mg["documentos"]}
        self.assertIn("br-municipal-3106200-decreto-2024-02-05-18621", mg_ids)

    def test_bh_complementary_decrees_published(self) -> None:
        cat = json.loads((ROOT / "metadados/licitacoes-locais/MG.json").read_text(encoding="utf-8"))
        ids = {d["norma_id"] for d in cat["documentos"]}
        for nid in [
            "br-municipal-3106200-decreto-2021-12-21-17813",
            "br-municipal-3106200-decreto-2022-09-20-18096",
            "br-municipal-3106200-decreto-2023-01-19-18240",
            "br-municipal-3106200-decreto-2023-01-25-18242",
            "br-municipal-3106200-decreto-2023-03-28-18289",
            "br-municipal-3106200-decreto-2024-02-05-18621",
        ]:
            self.assertIn(nid, ids)
            path = next(d["arquivo"] for d in cat["documentos"] if d["norma_id"] == nid)
            self.assertTrue((ROOT / path).is_file())
            cob = ROOT / next(d["provas"]["cobertura"] for d in cat["documentos"] if d["norma_id"] == nid)
            self.assertTrue(cob.is_file(), cob)
        pend = next(p for p in cat["pendencias"] if p["id"] == "bh-18289-consolidacao-18621")
        self.assertEqual(pend["alterador_publicado"], "br-municipal-3106200-decreto-2024-02-05-18621")
        self.assertIn("parcialmente-atendida", pend["tipo"])


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
        df = next(u for u in idx["ufs"] if u["uf"] == "DF")
        self.assertEqual(df["status_acervo"], "decreto-geral-publicado")
        self.assertEqual(df["decretos_14133"][0]["norma_id"], "br-df-decreto-2023-03-16-44330")
        self.assertTrue((ROOT / df["decretos_14133"][0]["arquivo"]).is_file())
        am = next(u for u in idx["ufs"] if u["uf"] == "AM")
        self.assertEqual(am["status_acervo"], "decreto-geral-publicado")
        self.assertEqual(am["decretos_14133"][0]["norma_id"], "br-am-decreto-2023-03-10-47133")
        self.assertEqual(am["decretos_14133"][0]["carater"], "regulamento-geral-estadual")
        self.assertTrue((ROOT / am["decretos_14133"][0]["arquivo"]).is_file())
        self.assertEqual(set(idx["resumo"]["decreto_geral_publicado"]), {"PR", "DF", "AM"})

    def test_opaque_id_reuse_and_classifications(self) -> None:
        idx = json.loads(
            (ROOT / "metadados/regulamentacao-14133-ufs/index.json").read_text(encoding="utf-8")
        )
        mg = next(u for u in idx["ufs"] if u["uf"] == "MG")
        self.assertEqual(mg["status_acervo"], "suite-tematica-sem-decreto-geral")
        mg_ids = {d["norma_id"] for d in mg["decretos_14133"]}
        self.assertIn("br-mg-decreto-2024-02-23-48779", mg_ids)  # SRP
        self.assertIn("br-mg-decreto-2023-03-17-48587", mg_ids)
        for d in mg["decretos_14133"]:
            self.assertTrue((ROOT / d["arquivo"]).is_file(), d["arquivo"])
            self.assertNotEqual(d["carater"], "regulamento-geral-estadual")
        sp = next(u for u in idx["ufs"] if u["uf"] == "SP")
        self.assertEqual(sp["status_acervo"], "suite-tematica-e-transitorio")
        sp67 = next(d for d in sp["decretos_14133"] if d["norma_id"] == "br-sp-norma-207462")
        self.assertEqual(sp67["carater"], "aplicacao-transitoria-regulamentos-federais")
        go = next(u for u in idx["ufs"] if u["uf"] == "GO")
        self.assertEqual(go["status_acervo"], "suite-tematica-sem-decreto-geral")
        pe = next(u for u in idx["ufs"] if u["uf"] == "PE")
        self.assertEqual(pe["status_acervo"], "leis-e-decreto-especifico-sem-geral")
        pe_dec = pe["decretos_14133"][0]
        self.assertEqual(pe_dec["norma_id"], "br-pe-decreto-2023-12-12-55916")
        self.assertEqual(pe_dec["carater"], "especifico-gratificacoes-lei-18384")
        self.assertTrue((ROOT / pe_dec["arquivo"]).is_file())
        rn = next(u for u in idx["ufs"] if u["uf"] == "RN")
        self.assertEqual(rn["status_acervo"], "identificado-fora-do-acervo")
        self.assertEqual(rn["decretos_14133"], [])

    def test_am_47133_fold(self) -> None:
        fontes = json.loads(
            (ROOT / "provas/regulamentacao-14133-ufs/AM/fontes.json").read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        self.assertEqual(sha256_bytes(raw), entry["sha256_conteudo"])
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        for tag in soup.find_all(["script", "style", "nav", "header", "footer"]):
            tag.decompose()
        html_fold = from_marker(
            nl.strip_fold(soup.body.get_text(" ") if soup.body else ""),
            ["decretono47133de10demarcode2023regulamenta"],
        )
        stop = "estetextonaosubstituiopublicadonodoede10demarcode2023"
        hi = html_fold.find(stop)
        if hi >= 0:
            html_fold = html_fold[: hi + len(stop)]
        md_full = (ROOT / "estaduais/AM/br-am-decreto-2023-03-10-47133.md").read_text(encoding="utf-8")
        md = strip_note(md_full)
        md_fold = from_marker(
            nl.strip_fold(nl.md_text_all(md)),
            ["decretono47133de10demarcode2023regulamenta"],
        )
        mi = md_fold.find(stop)
        if mi >= 0:
            md_fold = md_fold[: mi + len(stop)]
        self.assertEqual(md_fold, html_fold)
        self.assertEqual(sha256_bytes(md_full.encode("utf-8")), entry["sha256_markdown"])
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_corpo_markdown"])
        self.assertIn("REGULAMENTA", md)
        self.assertIn("14.133", md)

    def test_pe_55916_fold(self) -> None:
        fontes = json.loads(
            (ROOT / "provas/regulamentacao-14133-ufs/PE/fontes.json").read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        self.assertEqual(entry["carater"], "especifico-gratificacoes-lei-18384")
        raw = lzma.open(ROOT / entry["arquivo"]).read()
        self.assertEqual(sha256_bytes(raw), entry["sha256_conteudo"])
        soup = BeautifulSoup(raw.decode("utf-8", errors="replace"), "lxml")
        div = soup.select_one("#divTexto")
        self.assertIsNotNone(div)
        html_fold = from_marker(nl.strip_fold(div.get_text(" ")), ["decretono55916"])
        md_full = (ROOT / "estaduais/PE/br-pe-decreto-2023-12-12-55916.md").read_text(encoding="utf-8")
        md = strip_note(md_full)
        md_fold = from_marker(nl.strip_fold(nl.md_text_all(md)), ["decretono55916"])
        self.assertEqual(md_fold, html_fold)
        self.assertEqual(sha256_bytes(md_full.encode("utf-8")), entry["sha256_markdown"])
        self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_corpo_markdown"])
        self.assertIn("18.384", md)
        self.assertIn("Não é regulamento geral", md_full)


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
        go = next(c for c in idx["capitais"] if c["ibge"] == "5208707")
        self.assertEqual(go["decreto_14133_carater"], "parcial-art60")
        bh = next(c for c in idx["capitais"] if c["ibge"] == "3106200")
        self.assertEqual(bh["decreto_14133_carater"], "parcial-criterio-julgamento")
        self.assertTrue(str(bh["lei_organica"]).startswith("pendente"))
        self.assertEqual(idx["resumo"]["com_decreto_14133_geral"], 1)



if __name__ == "__main__":
    unittest.main()
