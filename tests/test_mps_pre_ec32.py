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
            self.assertNotIn('medida-provisoria-pos-ec32', text)
            self.assertNotIn('<<ANEXO>>', text)

    def test_identidade_reedicao_na_matriz(self) -> None:
        aus = json.loads((self.provas / 'ausencias.json').read_text())
        with_reed = [a for a in aus if a.get('reedicao') not in (None, '', '0', 0)]
        self.assertGreater(len(with_reed), 0)
        sample = with_reed[0]
        self.assertIn('-', sample['chave'])
        self.assertIn(f"-{int(str(sample['reedicao']).strip())}", sample['id'])

    def test_publicados_nao_fundem_com_pos_ec32(self) -> None:
        pub_path = self.provas / 'matriz-publicacao.json'
        if not pub_path.exists():
            self.skipTest('publicação ainda não executada')
        pub = json.loads(pub_path.read_text())
        self.assertGreaterEqual(pub['n_publicados'], 4)
        for item in pub['publicados']:
            # identidade numero[-reedicao] no id
            tail = item['id'].rsplit('-', 2)
            self.assertTrue(item['id'].startswith('br-federal-medida-provisoria-'))
            text = (ROOT / item['path']).read_text()
            self.assertIn('medida-provisoria-pre-ec32', text)

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
