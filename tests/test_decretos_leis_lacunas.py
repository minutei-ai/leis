#!/usr/bin/env python3
"""Testes lacunas de decretos-leis (#96)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class DecretosLeisLacunasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provas = ROOT / 'provas' / 'decretos-leis-lacunas'
        self.matriz = json.loads((self.provas / 'matriz-lote.json').read_text())

    def test_reconcile_bate_ordem_de_grandeza(self) -> None:
        self.assertEqual(self.matriz['ausentes_canonicos'], 738)
        self.assertIn('DEL', self.matriz['subtipos'])
        self.assertIn('DEL-mpv', self.matriz['subtipos'])
        self.assertEqual(self.matriz['subtipos']['DEL-mpv'], 9)

    def test_publicados(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        for item in pub['publicados']:
            text = (ROOT / item['path']).read_text()
            self.assertIn('decreto-lei', text)
            self.assertIn('vigencia_certificada', text)


if __name__ == '__main__':
    unittest.main()
