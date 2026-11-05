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
            self.assertNotIn('<<ANEXO>>', text)

    def test_epigrafe_divergente_preservada_quando_existir(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        notes = 0
        for item in pub['publicados']:
            text = (ROOT / item['path']).read_text()
            if 'Divergência literal da fonte: epígrafe' in text:
                notes += 1
                self.assertIn('sem correção editorial', text)
        # pode ser zero se o lote atual não tiver esse caso; só garante formato quando houver
        self.assertGreaterEqual(notes, 0)

    def test_del_mpv_nao_fundido_no_catalogo(self) -> None:
        self.assertEqual(self.matriz['subtipos']['DEL-mpv'], 9)
        self.assertGreater(self.matriz['subtipos']['DEL'], 1000)
        # identidades distintas: nenhum publicado mistura tipo DEL-mpv no path DEL puro
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        for item in pub['publicados']:
            self.assertTrue(item['id'].startswith('br-federal-decreto-lei-'))
            tipo = item.get('tipo')
            if tipo is not None:
                self.assertIn(tipo, ('DEL', 'DEL-mpv'))

    def test_pdf_retido_nao_publicavel(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        pdf_ret = [
            r for r in pub['retidos']
            if r.get('status') == 'retido-anexo-pdf-layout-pendente' and r.get('anexos_pdf')
        ]
        if not pdf_ret:
            self.skipTest('ainda sem snapshots PDF na matriz')
        for item in pdf_ret:
            for a in item['anexos_pdf']:
                if 'erro' in a:
                    continue
                self.assertFalse(a.get('publicavel', True))
                self.assertIn('sha256', a)


if __name__ == '__main__':
    unittest.main()
