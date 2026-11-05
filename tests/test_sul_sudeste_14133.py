#!/usr/bin/env python3
"""Testes do lote Sul/Sudeste 14.133 (namespace próprio)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts"))
sys.dont_write_bytecode = True
import sul_sudeste_14133 as ss  # noqa: E402

class TestSulSudeste14133Index(unittest.TestCase):
    def setUp(self) -> None:
        self.idx = json.loads(
            (ROOT / "metadados/sul-sudeste-14133/index.json").read_text(encoding="utf-8")
        )

    def test_seven_ufs_and_capitals(self) -> None:
        self.assertEqual(self.idx["tema"], "sul-sudeste-14133")
        self.assertEqual(set(self.idx["ufs"]), set(ss.UFS))
        self.assertEqual(len(self.idx["estaduais"]), 7)
        self.assertEqual(len(self.idx["capitais"]), 7)
        self.assertEqual(self.idx["issues"], [73, 101])

    def test_pr_geral_reuse(self) -> None:
        pr = next(u for u in self.idx["estaduais"] if u["uf"] == "PR")
        self.assertEqual(pr["status_acervo"], "decreto-geral-publicado")
        dec = pr["decretos_14133"][0]
        self.assertEqual(dec["norma_id"], "br-pr-ato-259084")
        self.assertTrue(dec["reuso"])
        self.assertTrue((ROOT / dec["arquivo"]).is_file())

    def test_mg_suite_not_geral(self) -> None:
        mg = next(u for u in self.idx["estaduais"] if u["uf"] == "MG")
        self.assertEqual(mg["status_acervo"], "suite-tematica-sem-decreto-geral")
        for d in mg["decretos_14133"]:
            self.assertNotEqual(d["carater"], "regulamento-geral-estadual")
            self.assertTrue(d["reuso"])
            self.assertTrue((ROOT / d["arquivo"]).is_file())

    def test_sp_capital_complete_reuse(self) -> None:
        sp = next(c for c in self.idx["capitais"] if c["ibge"] == "3550308")
        self.assertEqual(sp["decreto_14133_carater"], "geral")
        self.assertTrue(sp.get("reuso"))
        self.assertTrue((ROOT / sp["lei_organica"]).is_file())
        self.assertTrue((ROOT / sp["decreto_14133"]).is_file())

    def test_bh_parcial_lo_pendente(self) -> None:
        bh = next(c for c in self.idx["capitais"] if c["ibge"] == "3106200")
        self.assertEqual(bh["decreto_14133_carater"], "parcial-criterio-julgamento")
        self.assertTrue(str(bh["lei_organica"]).startswith("pendente"))
        self.assertTrue(bh.get("bloqueios"))

    def test_sc_especifico_not_geral(self) -> None:
        sc = next(u for u in self.idx["estaduais"] if u["uf"] == "SC")
        dec = sc["decretos_14133"][0]
        self.assertIn("especifico", dec["carater"])
        self.assertTrue((ROOT / dec["arquivo"]).is_file())
        md = (ROOT / dec["arquivo"]).read_text(encoding="utf-8")
        self.assertIn("14.133", md)
        self.assertRegex(md, r"(?i)espec[ií]fico|n[aã]o [eé] regulamento geral")

    def test_poa_tematico_not_geral(self) -> None:
        poa = next(c for c in self.idx["capitais"] if c["ibge"] == "4314902")
        self.assertEqual(poa["decreto_14133_carater"], "especifico-contratacoes-diretas")
        self.assertTrue((ROOT / poa["decreto_14133"]).is_file())

    def test_es_suite_not_geral(self) -> None:
        es = next(u for u in self.idx["estaduais"] if u["uf"] == "ES")
        self.assertEqual(es["status_acervo"], "suite-tematica-sem-decreto-geral")
        ids = {d["norma_id"] for d in es["decretos_14133"]}
        self.assertIn("br-es-decreto-2023-03-28-5352-r", ids)
        for d in es["decretos_14133"]:
            self.assertNotEqual(d["carater"], "regulamento-geral-estadual")
            self.assertTrue((ROOT / d["arquivo"]).is_file())
            md = (ROOT / d["arquivo"]).read_text(encoding="utf-8")
            self.assertIn("14.133", md)
        self.assertTrue(es.get("bloqueios"))
        # 5354/5545: fonte capturada, conversão bbox pendente
        ext = {x["titulo"] for x in es.get("identificacao_externa") or []}
        self.assertTrue(any("5.354" in t for t in ext))
        self.assertTrue(any("5.545" in t for t in ext))

    def test_bloqueios_concretos_floripa(self) -> None:
        flo = next(c for c in self.idx["capitais"] if c["ibge"] == "4205407")
        self.assertTrue(flo.get("bloqueios"))

    def test_does_not_touch_shared_indexes_paths(self) -> None:
        # Namespace isolation: shared indexes exist but this lote has its own
        self.assertTrue((ROOT / "metadados/sul-sudeste-14133/index.json").is_file())
        self.assertTrue((ROOT / "metadados/sul-sudeste-14133/PENDENCIAS.md").is_file())


class TestSulSudeste14133Verify(unittest.TestCase):
    def test_verify_script(self) -> None:
        ss.verify()


if __name__ == "__main__":
    unittest.main()
