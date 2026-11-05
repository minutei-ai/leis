#!/usr/bin/env python3
"""Testes espécies históricas LCT/AIT/ACP (#90)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class EspeciesHistoricasTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provas = ROOT / 'provas' / 'especies-historicas'
        self.matriz = json.loads((self.provas / 'matriz-lote.json').read_text())

    def test_tres_especies_catalogadas(self) -> None:
        especies = self.matriz['especies']
        self.assertEqual(especies['LCT']['catalogo_total'], 21)
        self.assertEqual(especies['AIT']['catalogo_total'], 17)
        self.assertEqual(especies['ACP']['catalogo_total'], 105)

    def test_publicados_com_serie_propria(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        for item in pub['publicados']:
            text = (ROOT / item['path']).read_text()
            self.assertIn(item['serie'], text)
            self.assertNotIn('lei-complementar', item['id'])
            self.assertIn('vigencia_certificada', text)


if __name__ == '__main__':
    unittest.main()
