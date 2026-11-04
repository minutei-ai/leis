"""ANVISA RDC 50 + RFB 2110 + CMN 4966 (issue #75)."""
from __future__ import annotations

import json
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MANIFEST = json.loads((ROOT / 'metadados/atos-infralegais-orgaos.json').read_text(encoding='utf-8'))
SLUG_RDC = 'br-federal-rdc-anvisa-2002-02-21-50'
SLUG_RFB_V = 'br-federal-in-rfb-2022-10-17-2110'
SLUG_RFB_O = 'br-federal-in-rfb-2022-10-17-2110-original'
SLUG_CMN = 'br-federal-resolucao-cmn-2021-11-25-4966'


class TestAtosInfralegaisOrgaos(unittest.TestCase):
    def test_catalogo_tres_orgaos(self):
        cats = MANIFEST['catalogo_orgaos']
        self.assertIn('anvisa', cats)
        self.assertIn('rfb', cats)
        self.assertIn('cmn-bcb', cats)
        for org in cats.values():
            self.assertTrue(org['fontes_oficiais'])
            self.assertTrue(org['ainda_nao_inventariado'])
            self.assertNotEqual(org.get('cobertura_completa'), True)

    def test_rdc50_publicada_com_tabelas_pesquisaveis_e_facsimile(self):
        docs = {d['id']: d for d in MANIFEST['documentos']}
        self.assertIn(SLUG_RDC, docs)
        path = ROOT / docs[SLUG_RDC]['arquivo']
        text = path.read_text(encoding='utf-8')
        self.assertIn('norma_tipo: "rdc"', text)
        self.assertIn('orgao_emissor: "anvisa"', text)
        self.assertIn('vigencia_certificada: false', text)
        self.assertIn('fac-simile:inicio', text)
        self.assertGreater(docs[SLUG_RDC]['tabelas'], 40)
        self.assertTrue((ROOT / 'provas/atos-infralegais-orgaos/fac-similes/rdc-anvisa-50-2002-fig1.jpg').is_file())
        self.assertRegex(text, r'(?m)^Art\.\s*1')
        self.assertIn('<table', text)
        self.assertIn('Sala de atendimento individualizado', text)
        rec = json.loads((ROOT / f'provas/atos-infralegais-orgaos/reconciliacao-{SLUG_RDC}.json').read_text())
        audit = rec['auditoria_tabelas_diagrama']
        self.assertGreaterEqual(audit['soma_tabelas_pesquisaveis'], 40)
        self.assertTrue(audit['conteudo_celulas_pesquisavel'])

    def test_rfb_2110_edicoes_distintas(self):
        docs = {d['id']: d for d in MANIFEST['documentos']}
        self.assertIn(SLUG_RFB_V, docs)
        self.assertIn(SLUG_RFB_O, docs)
        v = (ROOT / docs[SLUG_RFB_V]['arquivo']).read_text(encoding='utf-8')
        o = (ROOT / docs[SLUG_RFB_O]['arquivo']).read_text(encoding='utf-8')
        self.assertIn('norma_tipo: "in"', v)
        self.assertIn('orgao_emissor: "rfb"', v)
        self.assertIn('"idAto": 126687', v)
        self.assertIn('sijut-vigente', v)
        self.assertIn('sijut-original', o)
        self.assertRegex(v, r'(?m)^Art\.\s*1')
        self.assertRegex(o, r'(?m)^Art\.\s*1')
        self.assertNotEqual(v, o)
        self.assertIn('previd', v.lower())

    def test_cmn_4966_dou_publicada(self):
        docs = {d['id']: d for d in MANIFEST['documentos']}
        self.assertIn(SLUG_CMN, docs)
        text = (ROOT / docs[SLUG_CMN]['arquivo']).read_text(encoding='utf-8')
        self.assertIn('norma_tipo: "resolucao-cmn"', text)
        self.assertIn('orgao_emissor: "cmn"', text)
        self.assertRegex(text, r'(?m)^Art\.\s*1')
        self.assertIn('instrumento financeiro', text.lower())
        self.assertTrue(SLUG_CMN.startswith('br-federal-resolucao-cmn-'))

    def test_pendencias_residuais_sem_falso_negativo(self):
        pend = MANIFEST['pendencias_acesso']
        self.assertGreaterEqual(len(pend), 1)
        temas = {p.get('tema') for p in pend}
        self.assertTrue(any('bcb' in (t or '') for t in temas) or any('sijut' in (t or '') for t in temas))
        for p in pend:
            self.assertNotEqual(p['estado_acesso'], 'inexistente')
            self.assertIn('inexist', p['leitura'].lower())

    def test_identidade_com_orgao_e_especie(self):
        self.assertTrue(SLUG_RDC.startswith('br-federal-rdc-anvisa-'))
        self.assertTrue(SLUG_RFB_V.startswith('br-federal-in-rfb-'))
        self.assertTrue(SLUG_CMN.startswith('br-federal-resolucao-cmn-'))
        for d in MANIFEST['documentos']:
            self.assertIn(d['orgao_emissor'], d['id'])

    def test_escopo_parcial(self):
        escopo = MANIFEST.get('escopo') or {}
        self.assertEqual(escopo.get('estado'), 'parcial')
        self.assertTrue(escopo.get('nao_cataloga_como_cobertura_completa'))

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
