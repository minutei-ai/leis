#!/usr/bin/env python3
"""Testes offline do lote histórico constitucional (#79)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]


class HistoricoConstitucionalTest(unittest.TestCase):
    def setUp(self) -> None:
        self.provas = ROOT / 'provas' / 'historico-constitucional'
        self.federal = ROOT / 'federal'
        self.matriz = json.loads((self.provas / 'matriz-lote.json').read_text())
        self.catalogo = json.loads((self.provas / 'catalogo-lote.json').read_text())

    def test_oito_itens_publicados(self) -> None:
        publicados = [m for m in self.matriz if m.get('status') == 'publicado']
        self.assertEqual(len(publicados), 8)
        self.assertEqual(len(self.catalogo), 8)

    def test_arquivos_existem_com_serie_e_sem_vigencia(self) -> None:
        for item in self.catalogo:
            path = self.federal / f"{item['id']}.md"
            self.assertTrue(path.exists(), item['id'])
            text = path.read_text()
            self.assertIn(item['serie'], text)
            self.assertIn('vigencia_certificada', text)
            self.assertIn('false', text.split('vigencia_certificada', 1)[1][:40])

    def test_ec1969_nao_colide_com_ec1992(self) -> None:
        a = self.federal / 'br-federal-emenda-constitucional-1969-10-17-1.md'
        b = self.federal / 'br-federal-emenda-constitucional-1992-03-31-1.md'
        self.assertTrue(a.exists())
        self.assertTrue(b.exists())
        self.assertNotEqual(a.read_bytes(), b.read_bytes())
        self.assertIn('constituicao-1967', a.read_text())

    def test_adct_peca_da_edicao_1946(self) -> None:
        adct = next(i for i in self.catalogo if i['id'].endswith('-adct'))
        self.assertEqual(adct.get('peca_de'), 'br-federal-constituicao-1946-09-18')
        text = (self.federal / f"{adct['id']}.md").read_text()
        self.assertIn('peca_de', text)

    def test_cf1988_preservada(self) -> None:
        self.assertTrue((self.federal / 'br-federal-constituicao-1988-10-05.md').exists())


if __name__ == '__main__':
    unittest.main()
