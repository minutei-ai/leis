#!/usr/bin/env python3
"""Testes do lote MPs pós-EC 32 (#84)."""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT / 'scripts'))
import mps_anexo_recovery as ar  # noqa: E402


class MpsPosEc32Test(unittest.TestCase):
    def setUp(self) -> None:
        self.provas = ROOT / 'provas' / 'mps-pos-ec32'
        self.matriz = json.loads((self.provas / 'matriz-lote.json').read_text())

    def test_reconcile_tem_ausencias(self) -> None:
        self.assertGreaterEqual(self.matriz['ausentes_canonicos'], 190)
        self.assertEqual(self.matriz['corte_operacional'], '2001-09-11')

    def test_marcador_oficial_escapado_detectado(self) -> None:
        html = '<p><span>&lt;&lt;ANEXO&gt;&gt;</span></p>'
        self.assertTrue(ar.html_has_anexo_mark(html))
        diag = ar.diagnose_marker_in_html(html)
        self.assertEqual(diag['origem'], 'placeholder-oficial-normas.leg.br')
        self.assertGreaterEqual(diag['marcadores_escapados'], 1)

    def test_publicados_quando_existirem(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        self.assertGreaterEqual(pub['n_publicados'], 9)
        for item in pub['publicados']:
            path = ROOT / item['path']
            self.assertTrue(path.exists(), item['id'])
            text = path.read_text()
            self.assertIn('medida-provisoria-pos-ec32', text)
            self.assertIn('vigencia_certificada', text)
            self.assertNotIn('<<ANEXO>>', text)
            self.assertNotIn('<<TABELA>>', text)

    def test_diagnostico_ou_limites_documentam_bloqueios(self) -> None:
        limites = self.provas / 'limites.json'
        if not limites.exists():
            self.skipTest('limites ainda não gerados')
        data = json.loads(limites.read_text())
        self.assertEqual(data['issue'], 84)
        nota = data.get('nota', '').lower()
        self.assertTrue('placeholder' in nota or 'oficial' in nota)


if __name__ == '__main__':
    unittest.main()
