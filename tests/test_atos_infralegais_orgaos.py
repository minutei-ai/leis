"""ANVISA RDC 50 + catálogo RFB/CMN (issue #75)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'metadados/atos-infralegais-orgaos.json').read_text(encoding='utf-8'))
SLUG = 'br-federal-rdc-anvisa-2002-02-21-50'


class TestAtosInfralegaisOrgaos(unittest.TestCase):
    def test_catalogo_tres_orgaos(self):
        cats = MANIFEST['catalogo_orgaos']
        self.assertIn('anvisa', cats)
        self.assertIn('rfb', cats)
        self.assertIn('cmn-bcb', cats)
        for org in cats.values():
            self.assertTrue(org['fontes_oficiais'])
            self.assertTrue(org['ainda_nao_inventariado'])

    def test_rdc50_publicada_com_tabelas_e_facsimile(self):
        docs = {d['id']: d for d in MANIFEST['documentos']}
        self.assertIn(SLUG, docs)
        path = ROOT / docs[SLUG]['arquivo']
        text = path.read_text(encoding='utf-8')
        self.assertIn('norma_tipo: "rdc"', text)
        self.assertIn('orgao_emissor: "anvisa"', text)
        self.assertIn('vigencia_certificada: false', text)
        self.assertIn('fac-simile:inicio', text)
        self.assertGreater(docs[SLUG]['tabelas'], 40)
        self.assertTrue((ROOT / 'provas/atos-infralegais-orgaos/fac-similes/rdc-anvisa-50-2002-fig1.jpg').is_file())
        self.assertRegex(text, r'(?m)^Art\.\s*1')
        self.assertIn('<table', text)

    def test_pendencias_rfb_cmn_sem_falso_negativo(self):
        pend = {p['slug_previsto']: p for p in MANIFEST['pendencias_acesso']}
        self.assertIn('br-federal-in-rfb-2022-10-17-2110', pend)
        self.assertIn('br-federal-resolucao-cmn-2021-11-25-4966', pend)
        rfb = pend['br-federal-in-rfb-2022-10-17-2110']
        self.assertEqual(rfb['id_oficial']['idAto'], 126687)
        cmn = pend['br-federal-resolucao-cmn-2021-11-25-4966']
        self.assertEqual(cmn['norma_tipo'], 'resolucao-cmn')
        for p in pend.values():
            self.assertNotEqual(p['estado_acesso'], 'inexistente')
            self.assertIn('inexist', p['leitura'].lower())

    def test_identidade_com_orgao_e_especie(self):
        self.assertTrue(SLUG.startswith('br-federal-rdc-anvisa-'))
        for p in MANIFEST['pendencias_acesso']:
            self.assertIn(p['orgao_emissor'], p['slug_previsto'])

    def test_verify(self):
        import os, subprocess, sys
        env = {**os.environ, 'PYTHONPATH': str(ROOT / 'scripts')}
        proc = subprocess.run(
            [sys.executable, str(ROOT / 'scripts/atos_infralegais_orgaos.py'), 'verify'],
            cwd=ROOT, capture_output=True, text=True, env=env,
        )
        self.assertEqual(proc.returncode, 0, proc.stderr + proc.stdout)


if __name__ == '__main__':
    unittest.main()
