#!/usr/bin/env python3
"""Testes do contrato global / inventários #70 #74 #77 #83.

Offline. Não certifica completude nacional nem vigência.
"""
from __future__ import annotations

import json
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True

import cobertura_nacional as cn  # noqa: E402

PROVAS = ROOT / 'provas/cobertura-nacional'


class CoberturaNacionalTest(unittest.TestCase):
    def test_contrato_global_versionado(self):
        text = (ROOT / 'metadados/CONTRATO-acervo.md').read_text(encoding='utf-8')
        self.assertIn('Versão `1`', text)
        self.assertIn('CONTRATO.md', text)
        self.assertIn('norma_id', text)
        self.assertIn('cobertura_transcricao', text)
        self.assertIn('BM25', text)

    def test_complemento_nao_fundir(self):
        self.assertEqual(cn.catalogue_number('1599', None), '1599')
        self.assertEqual(cn.catalogue_number('1599', 'A'), '1599-a')
        self.assertNotEqual(cn.catalogue_number('1599', 'A'), cn.catalogue_number('1599', None))
        # reedicao distinta
        self.assertEqual(cn.catalogue_number('1599', None, '2'), '1599-2')
        self.assertNotEqual(cn.catalogue_number('1599', 'A'), cn.catalogue_number('1599', None, '2'))

    def test_lc1_1962_vs_1967(self):
        casos = json.loads((PROVAS / 'identidade-casos.json').read_text(encoding='utf-8'))['casos']
        lc = next(c for c in casos if c['id'] == 'lc1-1962-vs-1967')
        ids = {e['norma_id'] for e in lc['entradas']}
        self.assertEqual(len(ids), 2)
        self.assertTrue((ROOT / 'federal/br-federal-lei-complementar-1967-11-09-1.md').is_file())
        self.assertFalse(list(ROOT.glob('federal/br-federal-lei-complementar-1962-*-1.md')))

    def test_opaque_path_not_legal_number(self):
        cand = cn.path_identity_candidate('estaduais/AC/br-ac-norma-1121.md')
        self.assertTrue(cand['caminho_opaco'])
        self.assertEqual(cand['provedor_id'], '1121')
        self.assertIsNone(cand['numero'])
        head = (ROOT / 'estaduais/AC/br-ac-norma-1121.md').read_text(encoding='utf-8')[:400]
        self.assertIn('300', head)
        other = cn.path_identity_candidate('estaduais/AC/br-ac-norma-120.md')
        self.assertEqual(other['provedor_id'], '120')
        self.assertNotEqual(cand['provedor_id'], other['provedor_id'])

    def test_unnumbered_state_distinct(self):
        cand = cn.path_identity_candidate('federal/br-federal-decreto-1823-01-09-seq-sf-1.md')
        self.assertEqual(cand['numero_estado'], 'sem-numero')
        self.assertIsNone(cand['numero'])
        self.assertEqual(cand.get('provedor_token_namespace'), 'seq-sf')

    def test_ibge_special_entities(self):
        captura = cn.load_json(PROVAS / 'ibge-municipios-captura.json')
        slim = cn.load_ibge_slim()
        self.assertEqual(len(slim), 5571)
        self.assertEqual(captura['municipios'], 5569)
        especiais = {x['ibge'] for x in slim if x['classificacao'] == 'entidade-especial'}
        self.assertEqual(especiais, {'5300108', '2605459'})
        terr = cn.load_json(PROVAS / 'inventario-territorial.json')
        self.assertEqual(terr['resumo']['municipios_no_ibge'], 5569)
        self.assertNotIn('5300108', {m['ibge'] for m in terr['municipios_publicados']})
        self.assertIn('licitacoes-locais', terr['resumo']['lote_tematico_licitacoes_locais'])

    def test_facsimile_inventory_and_examples(self):
        fac = cn.load_json(PROVAS / 'inventario-fac-similes.json')
        by = {d['arquivo']: d for d in fac['documentos']}
        for rel in (
            'federal/br-federal-decreto-1954-02-25-35110.md',
            'federal/br-federal-decreto-1955-06-14-37491.md',
        ):
            self.assertTrue(by[rel]['fac_simile_oficial'])
            self.assertEqual(by[rel]['representacao'], 'fac-simile')
            self.assertEqual(by[rel]['cobertura_transcricao'], 'ausente')
            self.assertFalse(by[rel]['texto_integral_pesquisavel'])
        self.assertGreaterEqual(fac['resumo']['fac_simile_oficial'], 2)

    def test_cpp_annex_asset_and_pending_transcription(self):
        asset = ROOT / 'assets/federal/br-federal-decreto-lei-1941-10-03-3689/anexo-formulario-boletim-individual.png'
        self.assertEqual(
            cn.sha256_file(asset),
            'd8811277f5d8730d50454357d574094a0ff06a97a55d933a698f410f0880c9b1',
        )
        md = (ROOT / 'federal/br-federal-decreto-lei-1941-10-03-3689.md').read_text(encoding='utf-8')
        self.assertIn('anexo-formulario-boletim-individual.png', md)
        self.assertIn('transcrição pendente', md.lower())
        self.assertIn('3.992', md)
        evid = cn.load_json(PROVAS / 'cpp-anexo-formulario.json')
        self.assertEqual(evid['cobertura_transcricao'], 'ausente')
        self.assertEqual(evid['vigencia_campos_formulario'], 'nao-atribuida')

    def test_export_preserves_full_markdown_hash(self):
        rel = 'federal/edicoes/br-federal-lei-2021-04-01-14133-consolidada.md'
        doc = cn.export_document(rel)
        meta, body, body_hash = cn.markdown_body_hash(ROOT / rel)
        self.assertIsNotNone(meta)
        self.assertEqual(doc['sha256_markdown'], body_hash)
        self.assertEqual(doc['markdown_integral'], body)
        self.assertFalse(doc['vigencia_certificada'])
        self.assertIn('norma_id', meta)
        self.assertGreater(len(doc['markdown_integral']), 1000)

    def test_bm25_filter_and_negative_facsimile(self):
        demo = cn.load_json(PROVAS / 'bm25-demonstracao.json')
        self.assertTrue(demo['filtro_combinado_resultado'])
        self.assertTrue(all(x['igual'] and not x['truncado'] for x in demo['integridade_export']))
        neg = demo['caso_negativo_facsimile']
        self.assertFalse(neg['corpo_normativo_pesquisavel'])
        mapping = cn.load_json(PROVAS / 'bm25-mapeamento.json')
        self.assertEqual(mapping['properties']['markdown_integral']['type'], 'text')
        self.assertEqual(mapping['properties']['norma_id']['type'], 'keyword')
        self.assertEqual(mapping['properties']['cobertura_transcricao']['type'], 'keyword')

    def test_same_number_different_entes(self):
        a = cn.path_identity_candidate('municipais/3550308/br-municipal-3550308-decreto-2022-12-27-62100.md')
        b = cn.export_document('federal/br-federal-lei-2021-04-01-14133.md')
        self.assertEqual(a['esfera'], 'municipal')
        self.assertEqual(a['ibge'], '3550308')
        self.assertEqual(b['esfera'], 'federal')
        # mesmo que números coincidissem, ente/esfera separam o filtro
        self.assertNotEqual(a['esfera'], b['esfera'])

    def test_matriz_nacional_errata(self):
        matriz = cn.load_json(PROVAS / 'matriz-nacional.json')
        self.assertEqual(matriz['errata_complemento_senado']['totais_corrigidos']['chaves_agrupadas'], 61647)
        self.assertIn('#70', {x['id'] for x in matriz['lotes_diagnosticados']})
        self.assertIn('#74', {x['id'] for x in matriz['lotes_diagnosticados']})
        self.assertIn('#77', {x['id'] for x in matriz['lotes_diagnosticados']})
        self.assertTrue(matriz['universos_abertos'])

    def test_verify_command(self):
        cn.cmd_verify()


if __name__ == '__main__':
    unittest.main()
