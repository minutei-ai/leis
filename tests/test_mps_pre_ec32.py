#!/usr/bin/env python3
"""Testes MPs pré-EC 32 (#95)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class MpsPreEc32Test(unittest.TestCase):
    def setUp(self) -> None:
        self.provas = ROOT / 'provas' / 'mps-pre-ec32'
        self.matriz = json.loads((self.provas / 'matriz-lote.json').read_text())

    def test_lote_separado_da_pos(self) -> None:
        self.assertEqual(self.matriz['corte_operacional'], '2001-09-11')
        self.assertGreater(self.matriz['ausentes_canonicos'], 1000)

    def test_publicados_serie_pre(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        for item in pub['publicados']:
            text = (ROOT / item['path']).read_text()
            self.assertIn('medida-provisoria-pre-ec32', text)


if __name__ == '__main__':
    unittest.main()
