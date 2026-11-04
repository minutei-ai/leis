"""Cobertura por identidade da série Emendas CF/1988 nº 1–141 (issue #63)."""
from __future__ import annotations

import json
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import emendas_cf1988_serie_1_141 as lote  # noqa: E402

PROVAS = ROOT / 'provas/emendas-cf1988/serie-1-141'
MATRIZ = PROVAS / 'matriz-serie.json'
FED = ROOT / 'federal'


class TestEmendasCf1988Serie1141(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.matriz = json.loads(MATRIZ.read_text(encoding='utf-8'))
        cls.fresh = lote.scan()

    def test_matriz_completa_1_a_141(self):
        self.assertEqual(self.matriz['lote'], lote.LOTE)
        self.assertEqual(self.matriz['issue'], 63)
        self.assertEqual(self.matriz['numeros_alvo'], list(range(1, 142)))
        self.assertEqual(self.matriz['lacunas'], [])
        self.assertEqual(self.matriz['contagem']['publicados'], 141)
        self.assertEqual(self.matriz['recuperados'], list(range(1, 142)))
        self.assertEqual(self.matriz['recuperados'], self.fresh['recuperados'])
        self.assertEqual(self.matriz['lacunas'], self.fresh['lacunas'])

    def test_arquivos_publicados_sao_serie_cf1988(self):
        for item in self.matriz['itens']:
            with self.subTest(numero=item['numero']):
                path = ROOT / item['arquivo']
                self.assertTrue(path.is_file(), path)
                self.assertNotIn('revisao', path.name.lower())
                m = re.fullmatch(
                    r'federal/br-federal-emenda-constitucional-(\d{4})-\d{2}-\d{2}-(\d+)\.md',
                    item['arquivo'],
                )
                self.assertIsNotNone(m)
                self.assertGreaterEqual(int(m.group(1)), 1988)
                self.assertEqual(int(m.group(2)), item['numero'])
                self.assertEqual(item['serie'], 'cf-1988')
                self.assertTrue(item['nao_e_revisao'])
                self.assertTrue(item['nao_e_constituicao_historica'])

    def test_historicas_e_revisao_fora_da_serie(self):
        for hist in self.matriz['emendas_historicas_no_acervo_nao_contam_nesta_serie']:
            self.assertLess(int(hist['data'][:4]), 1988)
            self.assertTrue((ROOT / hist['arquivo']).is_file())
        self.assertEqual(self.matriz['emendas_revisao_no_acervo'], [])
        # Constituição consolidada não conta como emenda coletada.
        constituicao = FED / 'br-federal-constituicao-1988-10-05.md'
        self.assertTrue(constituicao.is_file())
        ids = {item['arquivo'] for item in self.matriz['itens']}
        self.assertNotIn('federal/br-federal-constituicao-1988-10-05.md', ids)

    def test_provas_de_faixa_existem(self):
        for rel in (
            'provas/emendas-cf1988/faixa-001-050/',
            'provas/emendas-cf1988/faixa-051-100/',
            'provas/emendas-cf1988/faixa-101-141/',
        ):
            self.assertTrue((ROOT / rel).is_dir(), rel)
        self.assertEqual(
            self.matriz['lotes_faixa_preexistentes']['prs_merged'],
            lote.PRS,
        )


if __name__ == '__main__':
    unittest.main()
