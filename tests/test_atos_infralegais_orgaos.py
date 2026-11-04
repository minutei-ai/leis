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
        self.assertIn('visao_path: "original"', o)
        self.assertIn('visao_payload: "conjunta"', o)
        self.assertEqual(docs[SLUG_RFB_O].get('visao_payload'), 'conjunta')
        self.assertRegex(v, r'(?m)^Art\.\s*1')
        self.assertRegex(o, r'(?m)^Art\.\s*1')
        self.assertNotEqual(v, o)
        self.assertIn('previd', v.lower())
        multi = ROOT / 'provas/atos-infralegais-orgaos/fontes/rfb-2110-multivigente.json.xz'
        self.assertTrue(multi.is_file())

    def test_cmn_4966_dou_publicada(self):
        docs = {d['id']: d for d in MANIFEST['documentos']}
        self.assertIn(SLUG_CMN, docs)
        text = (ROOT / docs[SLUG_CMN]['arquivo']).read_text(encoding='utf-8')
        self.assertIn('norma_tipo: "resolucao-cmn"', text)
        self.assertIn('orgao_emissor: "cmn"', text)
        self.assertRegex(text, r'(?m)^Art\.\s*1')
        self.assertIn('instrumento financeiro', text.lower())
        self.assertTrue(SLUG_CMN.startswith('br-federal-resolucao-cmn-'))
        self.assertEqual(docs[SLUG_CMN].get('edicao_tipo'), 'original')

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
        especie = MANIFEST.get('especie') or {}
        self.assertIn('rdc', especie.get('norma_tipos') or [])
        self.assertIn('Resolução CMN', (especie.get('nota') or ''))

    def test_escopo_parcial(self):
        escopo = MANIFEST.get('escopo') or {}
        self.assertEqual(escopo.get('estado'), 'parcial')
        self.assertTrue(escopo.get('nao_cataloga_como_cobertura_completa'))

    def test_catalogos_paginacao_periodo_ids_estados(self):
        ptr = MANIFEST.get('catalogos_paginacao')
        self.assertTrue(ptr)
        cats = json.loads((ROOT / ptr).read_text(encoding='utf-8'))
        for org in ('anvisa', 'rfb', 'cmn-bcb'):
            self.assertIn(org, cats['por_orgao'])
        rfb = cats['por_orgao']['rfb']['fontes_catalogo']
        idx = next(f for f in rfb if 'indexa' in f['sistema'].lower() or 'pesquisar' in (f.get('url') or ''))
        self.assertTrue(idx['paginacao_parametros_tentados'])
        self.assertTrue(idx['ids_oficiais_preservados'])
        self.assertIn(126687, {i.get('idAto') for i in idx['ids_oficiais_preservados'] if 'idAto' in i})
        self.assertIn('inexist', idx['leitura'].lower())
        anvisa = cats['por_orgao']['anvisa']['fontes_catalogo']
        self.assertTrue(any(f.get('estado_acesso') == 'http-403' for f in anvisa))
        cmn = cats['por_orgao']['cmn-bcb']['fontes_catalogo']
        self.assertTrue(any(f.get('estado_acesso') == 'shell-javascript' for f in cmn))

    def test_diferencas_edicoes_rfb_e_cmn_dou_neq_bcb(self):
        ptr = MANIFEST.get('diferencas_edicoes')
        dif = json.loads((ROOT / ptr).read_text(encoding='utf-8'))
        rfb = dif['rfb_2110']
        hashes = {
            rfb['variantes']['original_path']['sha256_segmentos'],
            rfb['variantes']['vigente']['sha256_segmentos'],
            rfb['variantes']['multivigente']['sha256_segmentos'],
        }
        self.assertEqual(len(hashes), 3)
        self.assertTrue(rfb['diferenca_markdown_original_vs_vigente'])
        self.assertGreaterEqual(len(rfb['modificadores_no_historico_sijut']), 3)
        cmn = dif['cmn_4966']
        self.assertIs(cmn['equivalencia'], False)
        self.assertEqual(cmn['edicao_publicada']['tipo'], 'original')
        self.assertEqual(cmn['edicao_nao_recuperada']['tipo'], 'consolidada')
        leitura = cmn['leitura'].lower().replace('nao', 'não')
        self.assertTrue('não equivale' in leitura or '≠' in cmn['leitura'])

    def test_relacoes_com_desconhecidos(self):
        relacoes = MANIFEST.get('relacoes') or []
        self.assertGreaterEqual(len(relacoes), 5)
        tipos = {r['tipo'] for r in relacoes}
        self.assertIn('alteracao', tipos)
        self.assertIn('variante-edicao', tipos)
        self.assertIn('edicao-nao-equivalente', tipos)
        for r in relacoes:
            self.assertTrue(r.get('desconhecidos'), r.get('id'))
            self.assertTrue(r.get('fonte') or r.get('leitura'), r.get('id'))

    def test_classificacao_normativo_vs_nao_normativo(self):
        ptr = MANIFEST.get('classificacao_fontes')
        clf = json.loads((ROOT / ptr).read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(clf['incluidos_como_normativos_neste_lote']), 4)
        excl = {e['tipo'] for e in clf['excluidos_explicitamente']}
        for tipo in ('consulta-publica', 'noticia', 'ato-individual', 'resolucao-bcb-ou-comunicado-mesmo-numero'):
            self.assertIn(tipo, excl)

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
