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
        self.assertIn('fonte_orgao', text)
        self.assertIn('órgão emissor', text.lower())
        self.assertIn('nunca é fallback', text)

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
        lc1962 = cn.export_document('federal/br-federal-lei-complementar-1962-07-17-1.md')
        lc1967 = cn.export_document('federal/br-federal-lei-complementar-1967-11-09-1.md')
        self.assertEqual(lc1962['numero'], lc1967['numero'])
        self.assertNotEqual(lc1962['norma_id'], lc1967['norma_id'])
        self.assertNotEqual(lc1962['data_ato'], lc1967['data_ato'])

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
        self.assertIn('anexo-formulario-boletim-individual-transcricao.md', md)
        self.assertIn('cobertura_transcricao=parcial', md)
        self.assertIn('3.992', md)
        evid = cn.load_json(PROVAS / 'cpp-anexo-formulario.json')
        self.assertEqual(evid['cobertura_transcricao'], 'parcial')
        self.assertEqual(evid['metodo_transcricao'], 'colacao-visual-do-fac-simile-oficial')
        self.assertEqual(evid['vigencia_campos_formulario'], 'nao-atribuida')
        transc = ROOT / evid['transcricao']
        self.assertEqual(cn.sha256_file(transc), evid['sha256_transcricao'])
        text = transc.read_text(encoding='utf-8')
        self.assertIn('BOLETIM INDIVIDUAL', text)
        self.assertIn('colação visual', text.lower())

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

    def test_export_separates_issuer_from_capture_source_and_keeps_relations(self):
        import tempfile
        from unittest.mock import patch

        with tempfile.TemporaryDirectory(prefix='acervo-export-fields-') as tmpdir:
            root = Path(tmpdir)
            rel = 'federal/br-federal-rcn-fixture.md'
            path = root / rel
            path.parent.mkdir(parents=True)
            body = '# Texto legal literal\n\nArt. 1º — íntegra preservada.\n'
            path.write_text(
                '---\n'
                'norma_id: "rcn-fixture"\n'
                'edicao_id: "rcn-fixture@original"\n'
                'norma_tipo: "resolucao-congresso-nacional"\n'
                'orgao_emissor: "Congresso Nacional"\n'
                'fonte_orgao: "Senado Federal — publicação pagina"\n'
                'serie_historica: "rcn-fixture-series"\n'
                'senado_id: "12345"\n'
                'urn: "urn:lex:br:congresso.nacional:resolucao:2020-01-02;1"\n'
                'relacoes: [{"tipo":"citacao","origem":"rcn-fixture",'
                '"destino":"target-id","dispositivo":"art. 1º",'
                '"escopo_cobertura":"parcial"}]\n'
                '---\n'
                + body,
                encoding='utf-8',
            )
            with patch.object(cn, 'ROOT', root):
                doc = cn.export_document(rel)
                meta, parsed_body = cn.parse_frontmatter(path.read_text(encoding='utf-8'))
                self.assertEqual(doc['orgao_emissor'], 'Congresso Nacional')
                self.assertEqual(doc['fonte_orgao'], 'Senado Federal — publicação pagina')
                self.assertEqual(doc['fonte_do_campo']['orgao_emissor'], 'frontmatter')
                self.assertEqual(doc['fonte_do_campo']['fonte_orgao'], 'frontmatter')
                self.assertEqual(doc['serie_historica'], meta['serie_historica'])
                self.assertEqual(doc['senado_id'], meta['senado_id'])
                self.assertEqual(doc['urn'], meta['urn'])
                self.assertEqual(doc['relacoes'], meta['relacoes'])
                self.assertEqual(doc['fonte_do_campo']['relacoes'], 'frontmatter')
                self.assertEqual(doc['markdown_integral'], parsed_body)
                self.assertEqual(doc['sha256_markdown'], cn.sha256_bytes(body.encode('utf-8')))

            # Captura identificada sozinha nunca pode virar órgão que expediu o ato.
            source_only = root / 'federal/source-only.md'
            source_only.write_text(
                '---\nfonte_orgao: "Senado Federal — página de publicação"\n---\nTexto.\n',
                encoding='utf-8',
            )
            with patch.object(cn, 'ROOT', root):
                unknown = cn.export_document('federal/source-only.md')
            self.assertEqual(unknown['orgao_emissor'], 'desconhecido')
            self.assertEqual(unknown['fonte_do_campo']['orgao_emissor'], 'desconhecido-explicito')
            self.assertEqual(unknown['fonte_orgao'], 'Senado Federal — página de publicação')

    def test_emissor_e_especie_separam_rsf_de_rcn(self):
        rcn_rel = 'federal/br-federal-resolucao-congresso-nacional-1983-10-20-1.md'
        rsf_rel = 'federal/br-federal-resolucao-senado-federal-2019-11-01-29.md'
        rcd_rel = 'federal/br-federal-resolucao-camara-deputados-1981-11-04-36.md'
        rcn = cn.export_document(rcn_rel)
        rsf = cn.export_document(rsf_rel)
        rcd = cn.export_document(rcd_rel)
        self.assertEqual(rcn['orgao_emissor'], 'Congresso Nacional')
        self.assertEqual(rcn['fonte_orgao'], 'Senado Federal — publicação pagina')
        self.assertEqual(rcn['especie'], 'resolucao-congresso-nacional')
        self.assertEqual(rsf['orgao_emissor'], 'Senado Federal')
        self.assertEqual(rsf['especie'], 'resolucao-senado-federal')
        self.assertEqual(rcd['orgao_emissor'], 'Câmara dos Deputados')
        self.assertEqual(rcd['fonte_orgao'], 'Senado Federal — publicação pagina')
        self.assertEqual(rcd['especie'], 'resolucao-camara-deputados')
        self.assertEqual(
            cn.apply_bm25_filters([rcn, rsf], {
                'orgao_emissor': 'Congresso Nacional',
                'especie': 'resolucao-congresso-nacional',
            }),
            [rcn],
        )
        self.assertEqual(
            cn.apply_bm25_filters([rcn, rsf], {
                'orgao_emissor': 'Senado Federal',
                'especie': 'resolucao-senado-federal',
            }),
            [rsf],
        )
        self.assertEqual(
            cn.apply_bm25_filters([rcn, rsf, rcd], {
                'orgao_emissor': 'Câmara dos Deputados',
                'especie': 'resolucao-camara-deputados',
            }),
            [rcd],
        )
        for rel, doc in ((rcn_rel, rcn), (rsf_rel, rsf), (rcd_rel, rcd)):
            _, body = cn.parse_frontmatter((ROOT / rel).read_text(encoding='utf-8'))
            self.assertEqual(doc['markdown_integral'], body)
            self.assertEqual(doc['sha256_markdown'], cn.sha256_bytes(body.encode('utf-8')))

    def test_acervo_comment_excludes_editorial_stub_from_integral_search(self):
        rel = 'estaduais/MG/br-mg-decreto-1945-06-26-2160.md'
        path = ROOT / rel
        raw = path.read_bytes()
        doc = cn.export_document(rel)
        self.assertEqual(cn.parse_acervo_comment(path.read_text(encoding='utf-8'))['edicao_integral'], False)
        self.assertEqual(cn.parse_acervo_comment(path.read_text(encoding='utf-8'))['excluir_denominador_integra'], True)
        self.assertEqual(doc['status_publicacao'], 'nao_publicado_integra')
        self.assertEqual(doc['corpo_status'], 'incompleto')
        self.assertTrue(doc['corpo_legal_integral_pendente'])
        self.assertTrue(doc['excluir_denominador_integra'])
        self.assertFalse(doc['texto_integral_pesquisavel'])
        self.assertEqual(doc['markdown_integral'], '')
        self.assertEqual(doc['sha256_markdown'], cn.sha256_bytes(raw))
        self.assertEqual(doc['sha256_arquivo_origem'], cn.sha256_bytes(raw))
        self.assertEqual(doc['bytes_arquivo_origem'], len(raw))
        self.assertEqual(doc['markdown_integral_bytes'], 0)
        self.assertEqual(cn.apply_bm25_filters([doc], {}), [])

        # Os 17 registros pendentes do inventário MG seguem fora da busca integral.
        mg_inventory = cn.load_json(
            PROVAS.parent / 'identidade-federal-99-102-103/mg-orfaos-inventario.json'
        )
        self.assertEqual(len(mg_inventory['pendentes']), 17)
        for item in mg_inventory['pendentes']:
            pending_doc = cn.export_document(item['arquivo'])
            self.assertTrue(pending_doc['corpo_legal_integral_pendente'])
            self.assertEqual(cn.apply_bm25_filters([pending_doc], {}), [])

        # Legítimos corpos recuperados com marcadores de fac-símile continuam exportáveis.
        for recovered in (
            'estaduais/MG/br-mg-decreto-1937-04-08-803.md',
            'estaduais/MG/br-mg-decreto-2000-03-21-40955.md',
        ):
            recovered_doc = cn.export_document(recovered)
            self.assertTrue(recovered_doc['markdown_integral'])
            self.assertNotIn('excluir_denominador_integra', recovered_doc)
            self.assertEqual(cn.apply_bm25_filters([recovered_doc], {}), [recovered_doc])

    def test_frontmatter_partial_retains_body_but_excludes_integral_search(self):
        ledger = cn.load_json(
            ROOT / 'provas/especies-legislativas-federais/textos-remetidos-pendentes.json'
        )
        item = next(x for x in ledger['itens']
                    if x.get('estado') == 'publicado-corpo-parcial-remissao-explicita')
        rel = item['arquivo_preexistente']
        doc = cn.export_document(rel)
        _meta, body = cn.parse_frontmatter((ROOT / rel).read_text(encoding='utf-8'))
        self.assertFalse(doc['edicao_integral'])
        self.assertTrue(doc['corpo_legal_integral_pendente'])
        self.assertTrue(doc['excluir_denominador_integra'])
        self.assertFalse(doc['texto_integral_pesquisavel'])
        self.assertTrue(doc['fonte_integral_preservada'])
        self.assertEqual(doc['cobertura_transcricao'], 'parcial')
        self.assertEqual(doc['markdown_integral'], body)
        self.assertEqual(doc['sha256_markdown'], cn.sha256_bytes(body.encode('utf-8')))
        self.assertGreater(doc['markdown_integral_bytes'], 0)
        self.assertEqual(cn.apply_bm25_filters([doc], {}), [])
        # The same partial marker on an editorial note still excludes the note body.
        mg = cn.export_document('estaduais/MG/br-mg-decreto-1945-06-26-2160.md')
        self.assertEqual(mg['markdown_integral'], '')
        self.assertEqual(mg['markdown_integral_bytes'], 0)

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
        self.assertEqual(mapping['properties']['corpo_legal_integral_pendente']['type'], 'boolean')
        self.assertEqual(mapping['properties']['excluir_denominador_integra']['type'], 'boolean')
        self.assertEqual(mapping['properties']['texto_integral_pesquisavel']['type'], 'boolean')
        self.assertIn({'term': {'corpo_legal_integral_pendente': True}}, mapping['bool_query_exemplo']['must_not'])
        for field in ('orgao_emissor', 'fonte_orgao', 'serie_historica', 'senado_id', 'urn'):
            self.assertEqual(mapping['properties'][field]['type'], 'keyword')
        self.assertEqual(mapping['properties']['relacoes']['type'], 'nested')

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
        self.assertIn('piloto_cabecalhos', matriz['artefatos'])
        self.assertTrue(matriz['avanco_desde_inventario_inicial'])

    def test_piloto_cabecalhos_preserva_corpo_e_proveniencia(self):
        piloto = cn.load_json(ROOT / 'metadados/acervo-geral-piloto.json')
        self.assertGreaterEqual(len(piloto['documentos']), 4)
        for item in piloto['documentos']:
            meta, body, body_hash = cn.markdown_body_hash(ROOT / item['arquivo'])
            self.assertIsNotNone(meta)
            self.assertEqual(body_hash, item['sha256_corpo_antes_depois'])
            self.assertIn('campo_fontes', meta)
            doc = cn.export_document(item['arquivo'])
            self.assertEqual(doc['markdown_integral'], body)
            self.assertIn('fonte_do_campo', doc)
            self.assertFalse(doc['vigencia_certificada'])
        ac = cn.export_document('estaduais/AC/br-ac-norma-1121.md')
        self.assertEqual(ac['numero'], '300')
        self.assertEqual(str(ac['provedor_id']), '1121')
        self.assertNotEqual(ac['numero'], str(ac['provedor_id']))
        self.assertEqual(ac['fonte_do_campo']['numero'], 'cabecalho-literal')

    def test_registro_fontes_jurisdicao(self):
        fontes = cn.load_json(PROVAS / 'registro-fontes-jurisdicao.json')
        self.assertEqual(len(fontes['ufs']), 27)
        self.assertIn('PR', fontes['ufs'])
        self.assertTrue(any('legislacao.pr.gov.br' in (f.get('url_descoberta') or '') for f in fontes['ufs']['PR']))
        sem = fontes['municipios_sem_diretorio']
        self.assertIn('ausencia-por-falta-de-pasta', sem['nao_inferir'])
        self.assertIn('ausencia-por-erro-http', sem['nao_inferir'])
        self.assertEqual(sem['estado_trabalho'], 'sem-publicacao-identificada')
        self.assertIn('3106200', fontes['municipios_publicados'])

    def test_reconciliacao_especies_e_blockers(self):
        recon = cn.load_json(PROVAS / 'reconciliacao-especies-publicadas.json')
        self.assertEqual(recon, cn.build_species_reconciliation())
        self.assertEqual(recon['errata_complemento_senado_totais']['decretos_leis_snapshot_correspondencia_inversa'], 9647)
        leitura = next(x for x in recon['leituras'] if x['especie'] == 'decreto-lei')
        self.assertEqual(leitura['delta_arquivos_vs_errata'], leitura['publicados'] - 9647)
        ids = {b['id'] for b in recon['blockers_concretos']}
        self.assertEqual(ids & {'#70', '#74', '#77', '#102', '#103'}, {'#70', '#74', '#77', '#102', '#103'})

    def test_verify_command(self):
        cn.cmd_verify()

    def test_export_meta_omits_body_preserves_hash(self):
        rel = 'federal/br-federal-lei-2021-04-01-14133.md'
        meta = cn.export_document(rel, include_markdown=False)
        full = cn.export_document(rel, include_markdown=True)
        self.assertNotIn('markdown_integral', meta)
        self.assertIn('markdown_integral', full)
        self.assertEqual(meta['sha256_markdown'], full['sha256_markdown'])
        self.assertEqual(meta['markdown_integral_bytes'], len(full['markdown_integral'].encode('utf-8')))
        _, body, body_hash = cn.markdown_body_hash(ROOT / rel)
        self.assertEqual(full['markdown_integral'], body)
        self.assertEqual(full['sha256_markdown'], body_hash)

    def test_opaque_path_without_frontmatter_keeps_numero_unknown(self):
        # Amostra opaca sem frontmatter: provedor_id ≠ numero legal.
        candidates = [
            p.relative_to(ROOT).as_posix()
            for p in (ROOT / 'estaduais/GO').glob('br-go-norma-*.md')
            if not p.read_text(encoding='utf-8', errors='replace').startswith('---\n')
        ][:3]
        self.assertTrue(candidates)
        for rel in candidates:
            doc = cn.export_document(rel, include_markdown=False)
            self.assertTrue(doc['provedor_id'])
            self.assertIsNone(doc['numero'])
            self.assertEqual(doc['numero_estado'], 'desconhecido')
            self.assertEqual(doc['armazenamento_metadados'], 'sidecar-export')
            self.assertEqual(doc['fonte_do_campo']['provedor_id'], 'caminho-opaco')
            self.assertEqual(doc['orgao_emissor'], 'desconhecido')
            self.assertEqual(doc['fonte_do_campo']['orgao_emissor'], 'desconhecido-explicito')

    def test_municipal_canonical_path_candidate(self):
        rel = 'municipais/3550308/br-municipal-3550308-decreto-2022-12-27-62100.md'
        cand = cn.path_identity_candidate(rel)
        self.assertEqual(cand['especie_candidata'], 'decreto')
        self.assertEqual(cand['numero'], '62100')
        self.assertEqual(cand['data_candidata'], '2022-12-27')
        self.assertEqual(cand['estado_identidade'], 'derivada-do-caminho-candidata')
        doc = cn.export_document(rel, include_markdown=False)
        self.assertEqual(doc['especie'], 'decreto')
        self.assertEqual(doc['numero'], '62100')
        self.assertEqual(doc['fonte_do_campo']['especie'], 'caminho-canonico')

    def test_bm25_filters_integrated_all_cases(self):
        result = cn.verify_bm25_filters_integrated()
        self.assertTrue(result['todos_ok'], result)
        ids = {c['id'] for c in result['casos']}
        self.assertIn('federal-lei-2021-historica', ids)
        self.assertIn('federal-lei-complementar-numero-1-1967', ids)
        self.assertIn('acre-opaco-provedor-nao-e-numero', ids)
        self.assertIn('municipal-ibge-decreto', ids)
        self.assertIn('facsimile-nao-texto-integral', ids)
        self.assertIn('ato-sem-numero-seq-sf', ids)
        self.assertIn('resolucao-congresso-emissor-separado-da-fonte', ids)
        self.assertIn('resolucao-senado-permanece-especie-distinta', ids)
        for case in result['casos']:
            self.assertTrue(case['ok'], case)

    def test_export_acervo_streaming_resume(self):
        import shutil
        import tempfile

        tmp = Path(tempfile.mkdtemp(prefix='acervo-export-'))
        try:
            # Lote pequeno via --limit (primeiros N do corpus ordenado).
            r1 = cn.export_acervo_streaming(
                out_dir=tmp,
                shard_size=2,
                resume=False,
                include_markdown=False,
                limit=4,
            )
            self.assertEqual(r1['manifesto']['total_edicoes'], 4)
            self.assertTrue(r1['manifesto']['completo'])  # completo relativo ao limit
            self.assertEqual(len(r1['manifesto']['shards']), 2)
            r2 = cn.export_acervo_streaming(
                out_dir=tmp / 'full',
                shard_size=3,
                resume=False,
                include_markdown=False,
                limit=6,
            )
            self.assertEqual(r2['manifesto']['total_edicoes'], 6)
            self.assertEqual(r2['inventario']['total_edicoes'], 6)
            self.assertEqual(r2['inventario']['anomalias']['provedor_id_igual_numero_sem_frontmatter'], 0)
            # Nenhuma linha carrega markdown_integral.
            n = 0
            for shard in r2['manifesto']['shards']:
                import gzip
                with gzip.open((tmp / 'full') / shard['arquivo'], 'rt', encoding='utf-8') as fh:
                    for line in fh:
                        row = json.loads(line)
                        self.assertNotIn('markdown_integral', row)
                        self.assertIn('fonte_do_campo', row)
                        self.assertFalse(row['vigencia_certificada'])
                        n += 1
            self.assertEqual(n, 6)
            # Resume: processa 2, depois completa até 6.
            partial = tmp / 'resume'
            cn.export_acervo_streaming(
                out_dir=partial, shard_size=2, resume=False, include_markdown=False, limit=2
            )
            ckpt = cn.load_json(partial / 'checkpoint.json')
            self.assertEqual(ckpt['next_index'], 2)
            cn.export_acervo_streaming(
                out_dir=partial, shard_size=2, resume=True, include_markdown=False, limit=6
            )
            man = cn.load_json(partial / 'manifesto.json')
            self.assertEqual(man['total_edicoes'], 6)
            self.assertGreaterEqual(len(man['shards']), 2)
        finally:
            shutil.rmtree(tmp, ignore_errors=True)

    def test_contrato_escolhe_sidecar_para_acervo_completo(self):
        text = (ROOT / 'metadados/CONTRATO-acervo.md').read_text(encoding='utf-8')
        self.assertIn('sidecars de exportação', text.lower())
        self.assertIn('JSONL', text)
        self.assertIn('export-acervo', text)

    def test_full_inventory_artifact_covers_all_files(self):
        inv = cn.load_json(PROVAS / 'inventario-campos-acervo.json')
        total = len(cn.iter_markdown_rels())
        self.assertEqual(inv['total_edicoes'], total)
        self.assertEqual(inv['escolha_armazenamento']['metadados_acervo_geral'], 'sidecar-export-jsonl')
        for field, states in inv['por_campo'].items():
            self.assertEqual(sum(states.values()), total, field)
        self.assertEqual(inv['anomalias']['provedor_id_igual_numero_sem_frontmatter'], 0)


if __name__ == '__main__':
    unittest.main()
