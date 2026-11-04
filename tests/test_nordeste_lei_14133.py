"""Testes setoriais do recorte Nordeste issues #73/#101.

Lê somente o repositório; não acessa a rede.
Não altera nem depende da atualização dos índices compartilhados.
"""
from __future__ import annotations

import hashlib
import json
import lzma
import re
import subprocess
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
                self.assertEqual(dec.get("colacao_oficial_status"), "desconhecido")
                path = ROOT / dec["arquivo"]
                self.assertTrue(path.is_file(), path)
                text = path.read_text(encoding="utf-8")
                self.assertIn("nota-edicao:inicio", text)
                self.assertIn("14.133", text)
                self.assertGreaterEqual(
                    len(re.findall(r"(?m)^Art\.?\s*\d+", strip_note(text))), 100
                )

    def test_hashes_e_snapshots_gerais(self) -> None:
        cases = [
            (
                "RN",
                "provas/regulamentacao-14133-ufs/RN/fontes.json",
                "estaduais/RN/br-rn-decreto-2023-03-07-32449.md",
            ),
            (
                "SE",
                "provas/regulamentacao-14133-ufs/SE/fontes.json",
                "estaduais/SE/br-se-decreto-2023-06-28-342.md",
            ),
            (
                "PI",
                "provas/regulamentacao-14133-ufs/PI/fontes.json",
                "estaduais/PI/br-pi-decreto-2023-03-07-21872.md",
            ),
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

    def test_ce_wayback_proveniencia(self) -> None:
        ce = next(u for u in self.idx["ufs"] if u["uf"] == "CE")
        dec = ce["decretos_14133"][0]
        self.assertEqual(dec["carater"], "etp-tr")
        self.assertEqual(dec.get("proveniencia"), "wayback-arquivo-url-oficial")
        self.assertEqual(dec.get("colacao_oficial_status"), "desconhecido")
        self.assertIs(dec.get("equivalente_captura_oficial_atual"), False)
        self.assertTrue(dec.get("wayback_timestamp"))
        fontes = json.loads(
            (ROOT / "provas/regulamentacao-14133-ufs/CE/fontes.json").read_text(
                encoding="utf-8"
            )
        )
        fe = fontes["fontes"][0]
        self.assertEqual(fe["proveniencia"], "wayback-arquivo-url-oficial")
        self.assertEqual(fe["colacao_oficial_status"], "desconhecido")
        self.assertIs(fe["equivalente_captura_oficial_atual"], False)
        self.assertEqual(fe["wayback_timestamp"], "20230323115514")
        self.assertIn("015", str(fe.get("edicao_identidade")))
        md = (ROOT / "estaduais/CE/br-ce-decreto-2023-01-19-35283.md").read_text(
            encoding="utf-8"
        )
        self.assertIn("Wayback", md)
        self.assertIn("desconhecido", md)
        self.assertIn("Nº015", md.replace("N°015", "Nº015"))
        self.assertEqual(
            sha256_bytes(lzma.open(ROOT / fe["arquivo"]).read()),
            fe["sha256_conteudo"],
        )

    def test_pe_suite_e_ba_ce_tematicos(self) -> None:
        pe = next(u for u in self.idx["ufs"] if u["uf"] == "PE")
        self.assertEqual(pe["status_acervo"], "suite-tematica-sem-decreto-geral")
        for d in pe["decretos_14133"]:
            self.assertNotEqual(d["carater"], "regulamento-geral-estadual")
            self.assertTrue((ROOT / d["arquivo"]).is_file(), d["arquivo"])
        ba = next(u for u in self.idx["ufs"] if u["uf"] == "BA")
        self.assertTrue(any(d.get("reutilizado") for d in ba["decretos_14133"]))

    def test_capitais_lo_publicadas(self) -> None:
        expected = {
            "2927408": "municipais/2927408/br-municipal-2927408-lei-organica-consolidada-2024.md",
            "2304400": "municipais/2304400/br-municipal-2304400-lei-organica.md",
            "2507507": "municipais/2507507/br-municipal-2507507-lei-organica-1990.md",
            "2611606": "municipais/2611606/br-municipal-2611606-lei-organica-1990-04-04.md",
            "2408102": "municipais/2408102/br-municipal-2408102-lei-organica-1990.md",
            "2704302": "municipais/2704302/br-municipal-2704302-lei-organica.md",
            "2800308": "municipais/2800308/br-municipal-2800308-lei-organica-1990.md",
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
                    self.assertEqual(
                        sha256_bytes(lzma.open(snap).read()), entry["sha256_conteudo"]
                    )
                    self.assertEqual(
                        sha256_bytes(text.encode("utf-8")), entry["sha256_markdown"]
                    )
                else:
                    # São Luís / Teresina: falha de acesso → nao-recuperado
                    self.assertEqual(cap["lei_organica"], "nao-recuperado")
                    self.assertTrue(
                        any(t.get("bloqueio") for t in cap.get("tentativas", [])),
                        cap["ibge"],
                    )

    def test_aracaju_geral_e_fortaleza_transicao(self) -> None:
        aju = next(c for c in self.idx["capitais"] if c["ibge"] == "2800308")
        self.assertEqual(aju["decreto_14133_carater"], "regulamento-geral-municipal")
        self.assertTrue(aju["decreto_14133"].endswith("7178.md"))
        path = ROOT / aju["decreto_14133"]
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("7.178", text)
        self.assertIn("regulamento-geral-municipal", text)
        fontes = json.loads(
            (
                ROOT
                / "provas/nordeste-lei-14133/capitais/2800308/fontes-decreto-7178.json"
            ).read_text(encoding="utf-8")
        )
        entry = fontes["fontes"][0]
        self.assertEqual(
            sha256_bytes(lzma.open(ROOT / entry["arquivo"]).read()),
            entry["sha256_conteudo"],
        )
        self.assertEqual(sha256_bytes(text.encode()), entry["sha256_markdown"])

        ce = next(c for c in self.idx["capitais"] if c["ibge"] == "2304400")
        self.assertEqual(ce["decreto_14133_carater"], "marco-temporal-transicao")
        path = ROOT / ce["decreto_14133"]
        self.assertTrue(path.is_file())
        text = path.read_text(encoding="utf-8")
        self.assertIn("15.317", text)
        self.assertNotIn("regulamento-geral-municipal", text)

    def test_matriz_nao_infere_ausencia_por_http(self) -> None:
        for uf in ("AL", "PB", "MA"):
            entry = next(u for u in self.idx["ufs"] if u["uf"] == uf)
            self.assertNotEqual(entry["status_acervo"], "sem-legislacao")
            self.assertTrue(entry.get("tentativas"), uf)
            if uf in {"AL", "PB"}:
                self.assertIn("nao-recuperado", entry["status_acervo"])
        for cap in self.idx["capitais"]:
            if cap["ibge"] in {"2111300", "2211001"}:
                self.assertEqual(cap["lei_organica"], "nao-recuperado")
                self.assertEqual(cap["decreto_14133"], "nao-recuperado")

    def test_auditoria_pdf_colacao(self) -> None:
        path = ROOT / "provas/nordeste-lei-14133/auditoria-pdfs-colacao.json"
        self.assertTrue(path.is_file())
        aud = json.loads(path.read_text(encoding="utf-8"))
        labels = {i["label"] for i in aud["itens"]}
        for need in ["RN-32449", "SE-342", "PI-21872", "LO-Recife", "LO-Salvador"]:
            self.assertIn(need, labels)
        for item in aud["itens"]:
            self.assertIs(item.get("fold_ok"), False)
            self.assertEqual(item.get("colacao_oficial_status"), "desconhecido")

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

    def test_script_verify_offline(self) -> None:
        proc = subprocess.run(
            ["python3", "scripts/nordeste_lei_14133.py", "verify"],
            cwd=ROOT,
            capture_output=True,
            text=True,
            check=False,
        )
        self.assertEqual(proc.returncode, 0, proc.stdout + proc.stderr)
        self.assertIn("VERIFY OK", proc.stdout)


if __name__ == "__main__":
    unittest.main()
