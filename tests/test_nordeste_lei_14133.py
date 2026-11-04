"""Testes setoriais do recorte Nordeste issues #73/#101.

Lê somente o repositório; não acessa a rede.
Não altera nem depende da atualização dos índices compartilhados.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
META = ROOT / "metadados/nordeste-lei-14133/index.json"
RECORT = ["AL", "BA", "CE", "MA", "PB", "PE", "PI", "RN", "SE"]


def sha256_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def strip_note(md: str) -> str:
    return re.sub(
        r"(?s)<!-- nota-edicao:inicio -->.*?<!-- nota-edicao:fim -->\s*",
        "",
        md,
    ).lstrip("\n")


class TestNordesteInventario(unittest.TestCase):
    @classmethod
    def setUpClass(cls) -> None:
        cls.idx = json.loads(META.read_text(encoding="utf-8"))

    def test_recorte_nove_ufs(self) -> None:
        self.assertEqual(self.idx["issues"], [73, 101])
        self.assertEqual(self.idx["recorte_ufs"], RECORT)
        self.assertEqual([u["uf"] for u in self.idx["ufs"]], RECORT)
        self.assertEqual(len(self.idx["capitais"]), 9)

    def test_gerais_estaduais_publicados(self) -> None:
        for uf, nid in [
            ("RN", "br-rn-decreto-2023-03-07-32449"),
            ("SE", "br-se-decreto-2023-06-28-342"),
            ("PI", "br-pi-decreto-2023-03-07-21872"),
        ]:
            with self.subTest(uf=uf):
                entry = next(u for u in self.idx["ufs"] if u["uf"] == uf)
                self.assertEqual(entry["status_acervo"], "decreto-geral-publicado")
                dec = entry["decretos_14133"][0]
                self.assertEqual(dec["norma_id"], nid)
                self.assertEqual(dec["carater"], "regulamento-geral-estadual")
                path = ROOT / dec["arquivo"]
                self.assertTrue(path.is_file(), path)
                text = path.read_text(encoding="utf-8")
                self.assertIn("nota-edicao:inicio", text)
                self.assertIn("14.133", text)
                self.assertGreaterEqual(len(re.findall(r"(?m)^Art\.?\s*\d+", strip_note(text))), 100)

    def test_hashes_e_snapshots_gerais(self) -> None:
        cases = [
            ("RN", "provas/regulamentacao-14133-ufs/RN/fontes.json", "estaduais/RN/br-rn-decreto-2023-03-07-32449.md"),
            ("SE", "provas/regulamentacao-14133-ufs/SE/fontes.json", "estaduais/SE/br-se-decreto-2023-06-28-342.md"),
            ("PI", "provas/regulamentacao-14133-ufs/PI/fontes.json", "estaduais/PI/br-pi-decreto-2023-03-07-21872.md"),
        ]
        for uf, fontes_path, md_path in cases:
            with self.subTest(uf=uf):
                fontes = json.loads((ROOT / fontes_path).read_text(encoding="utf-8"))
                entry = fontes["fontes"][0]
                snap = ROOT / entry["arquivo"]
                self.assertTrue(snap.is_file(), snap)
                raw = lzma.open(snap).read()
                self.assertEqual(sha256_bytes(raw), entry["sha256_conteudo"])
                self.assertEqual(sha256_bytes(snap.read_bytes()), entry["sha256_arquivo_xz"])
                md = (ROOT / md_path).read_text(encoding="utf-8")
                self.assertEqual(sha256_bytes(md.encode("utf-8")), entry["sha256_markdown"])
                self.assertEqual(
                    sha256_bytes(strip_note(md).encode("utf-8")),
                    entry["sha256_corpo_markdown"],
                )
                self.assertIn(entry["url"], md)
                self.assertIn(entry["sha256_conteudo"], md)

    def test_pe_suite_e_ba_ce_tematicos(self) -> None:
        pe = next(u for u in self.idx["ufs"] if u["uf"] == "PE")
        self.assertEqual(pe["status_acervo"], "suite-tematica-sem-decreto-geral")
        for d in pe["decretos_14133"]:
            self.assertNotEqual(d["carater"], "regulamento-geral-estadual")
            self.assertTrue((ROOT / d["arquivo"]).is_file(), d["arquivo"])
        ba = next(u for u in self.idx["ufs"] if u["uf"] == "BA")
        self.assertTrue(any(d.get("reutilizado") for d in ba["decretos_14133"]))
        ce = next(u for u in self.idx["ufs"] if u["uf"] == "CE")
        self.assertEqual(ce["decretos_14133"][0]["carater"], "etp-tr")

    def test_capitais_lo_publicadas(self) -> None:
        expected = {
            "2927408": "municipais/2927408/br-municipal-2927408-lei-organica-consolidada-2024.md",
            "2304400": "municipais/2304400/br-municipal-2304400-lei-organica.md",
            "2507507": "municipais/2507507/br-municipal-2507507-lei-organica-1990.md",
            "2611606": "municipais/2611606/br-municipal-2611606-lei-organica-1990-04-04.md",
            "2408102": "municipais/2408102/br-municipal-2408102-lei-organica-1990.md",
        }
        for cap in self.idx["capitais"]:
            with self.subTest(ibge=cap["ibge"]):
                if cap["ibge"] in expected:
                    self.assertEqual(cap["lei_organica"], expected[cap["ibge"]])
                    path = ROOT / cap["lei_organica"]
                    self.assertTrue(path.is_file(), path)
                    text = path.read_text(encoding="utf-8")
                    self.assertIn("nota-edicao:inicio", text)
                    self.assertRegex(text, r"(?i)lei org")
                    prova = ROOT / f"provas/nordeste-lei-14133/capitais/{cap['ibge']}/fontes.json"
                    self.assertTrue(prova.is_file(), prova)
                    fontes = json.loads(prova.read_text(encoding="utf-8"))
                    entry = fontes["fontes"][0]
                    snap = ROOT / entry["arquivo"]
                    self.assertTrue(snap.is_file())
                    self.assertEqual(sha256_bytes(lzma.open(snap).read()), entry["sha256_conteudo"])
                    self.assertEqual(sha256_bytes(text.encode("utf-8")), entry["sha256_markdown"])
                else:
                    self.assertEqual(cap["lei_organica"], "ausente")
                self.assertEqual(cap["decreto_14133"], "ausente")

    def test_nao_duplica_am_df_sp(self) -> None:
        blob = META.read_text(encoding="utf-8")
        self.assertNotIn("br-am-decreto", blob)
        self.assertNotIn("br-df-decreto", blob)
        self.assertNotIn("3550308", blob)

    def test_tentativas_registradas(self) -> None:
        for u in self.idx["ufs"]:
            with self.subTest(uf=u["uf"]):
                if u["uf"] in {"AL", "MA", "PB", "CE", "PI", "SE"}:
                    self.assertTrue(u.get("tentativas"), u["uf"])


if __name__ == "__main__":
    unittest.main()
