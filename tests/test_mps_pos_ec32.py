#!/usr/bin/env python3
"""Testes do lote MPs pós-EC 32 (#84)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MpsPosEc32Test(unittest.TestCase):
    def setUp(self) -> None:
        self.provas = ROOT / 'provas' / 'mps-pos-ec32'
        self.matriz = json.loads((self.provas / 'matriz-lote.json').read_text())

    def test_reconcile_tem_ausencias(self) -> None:
        self.assertGreaterEqual(self.matriz['ausentes_canonicos'], 190)
        self.assertEqual(self.matriz['corte_operacional'], '2001-09-11')

    def test_publicados_quando_existirem(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        for item in pub['publicados']:
            path = ROOT / item['path']
            self.assertTrue(path.exists(), item['id'])
            text = path.read_text()
            self.assertIn('medida-provisoria-pos-ec32', text)
            self.assertIn('vigencia_certificada', text)
            self.assertNotIn('<<ANEXO>>', text)


if __name__ == '__main__':
    unittest.main()
