"""Cobertura por identidade dos catálogos DLG/RSF/RCD/RCN e do lote Markdown."""
from __future__ import annotations

import json
import hashlib
import lzma
import re
import sys
import unittest
import tempfile
from unittest.mock import patch
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import especies_legislativas_federais as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/especies-legislativas-federais'


class TestColetaRetomavel(unittest.TestCase):
    def setUp(self):
        self.temporary = tempfile.TemporaryDirectory()
        self.addCleanup(self.temporary.cleanup)
        self.root = Path(self.temporary.name)
        self.progress = self.root / 'coleta.json'
        for name, value in [('ROOT', self.root), ('COLETAS_DIR', self.root),
                            ('COLETA_PROGRESS_PATH', self.progress)]:
            mocked = patch.object(lote, name, value)
            mocked.start()
            self.addCleanup(mocked.stop)

    def test_completed_capture_survives_interrupted_checkpoint(self):
        original = {'lote': 'teste', 'itens': {'old': {'slug': 'old'}}}
        lote.save_coleta(original)
        item = {'slug': 'new', 'sha256_fonte': 'evidence'}
        lote.append_coleta(item)
        before = self.progress.read_bytes()
        with patch.object(lote.os, 'replace', side_effect=OSError('disk error')):
            with self.assertRaises(OSError):
                lote.save_coleta({'lote': 'teste', 'itens': {'new': item}})
        self.assertEqual(self.progress.read_bytes(), before)
        self.assertEqual(lote.load_coleta()['itens'], {'old': {'slug': 'old'}, 'new': item})
        self.assertEqual({p.name for p in self.root.iterdir()},
                         {'coleta.json', 'coleta.journal.jsonl'})

    def test_recovery_discards_only_incomplete_tail_and_can_append_again(self):
        first, second = {'slug': 'first'}, {'slug': 'second'}
        lote.append_coleta(first)
        with lote.coleta_journal_path().open('ab') as stream:
            stream.write(b'{"slug":"interrupted')
        self.assertEqual(lote.load_coleta()['itens'], {'first': first})
        lote.append_coleta(second)
        recovered = lote.load_coleta()
        self.assertEqual(recovered['itens'], {'first': first, 'second': second})
        lote.save_coleta(recovered)
        self.assertFalse(lote.coleta_journal_path().exists())
        self.assertEqual(lote.load_coleta()['itens'], recovered['itens'])

    def test_corrupt_committed_journal_line_fails_instead_of_losing_capture(self):
        lote.coleta_journal_path().write_bytes(b'{"broken":\n')
        with self.assertRaises(json.JSONDecodeError):
            lote.load_coleta()

    def test_resume_requires_matching_source_bytes(self):
        raw = b'<html>official source</html>'
        snapshot = self.root / 'source.html.xz'
        snapshot.write_bytes(lzma.compress(raw))
        item = {'utilizavel': True, 'snapshot': snapshot.name,
                'sha256_fonte': hashlib.sha256(raw).hexdigest()}
        self.assertTrue(lote.reusable_coleta(item))
        snapshot.write_bytes(lzma.compress(b'changed source'))
        self.assertFalse(lote.reusable_coleta(item))
        snapshot.write_bytes(b'interrupted compressed snapshot')
        self.assertFalse(lote.reusable_coleta(item))
        snapshot.unlink()
        self.assertFalse(lote.reusable_coleta(item))

    def test_failed_annex_inspection_cannot_publish_html_as_integral(self):
        with patch.object(lote, 'normas_payload', return_value=({}, 'https://example.test/dados', b'{}')), \
                patch.object(lote, 'pick_html_content_url', return_value='https://example.test/texto'), \
                patch.object(lote, 'http_get', return_value=(200, b'<html>text</html>', 'https://example.test/texto')), \
                patch.object(lote, 'html_rejection_reason', return_value=None), \
                patch.object(lote, 'detail_json', side_effect=RuntimeError('HTTP 503')) as detail:
            item = lote.collect_one('DLG', '123', {'dataassinatura': '01/01/2025', 'numero': '1'})
        self.assertFalse(item['utilizavel'])
        self.assertEqual(item['estado_sugerido'], 'anexos-pendentes')
        self.assertIn('503', item['anexos_inspecao_erro'])
        self.assertFalse(lote.reusable_coleta(item))
        detail.assert_called_once()

    def test_publishing_rsf_preserves_rcn_annex_and_its_provenance(self):
        fed = self.root / 'federal'
        fed.mkdir()
        old_id = 'br-federal-resolucao-congresso-nacional-2025-01-01-1'
        old_path = fed / (old_id + '.md')
        old_text = '# Resolução com anexo recuperado\n\n| Célula | Valor |\n| A | 123 |\n'
        old_path.write_text(old_text, encoding='utf-8')
        old_source = {'tipo': 'RCN', 'anexo_fonte_alternativa': {'sha256': 'original-annex'}}
        old_doc = {'tipo': 'RCN', 'id': old_id, 'arquivo': str(old_path.relative_to(self.root))}
        old_proof = {'sha256_anexo': 'original-annex', 'tabelas': 1}
        raw = ('<html><body><p>RESOLUÇÃO Nº 1, DE 1º DE JANEIRO DE 2025</p>'
               '<p>Art. 1º Texto da resolução.</p></body></html>').encode()
        snap = self.root / 'rsf.html.xz'
        snap.write_bytes(lzma.compress(raw))
        new_id = lote.slug_for('RSF', '2025-01-01', '1')
        new = {'slug': new_id, 'tipo': 'RSF', 'numero': '1', 'data': '2025-01-01',
               'senado_id': '123', 'urn': 'urn:lex:br:federal:resolucao.senado:2025-01-01;1',
               'normaNome': 'Resolução do Senado Federal nº 1', 'ementa': 'Texto.',
               'fonte_url': 'https://example.test/source', 'capturado_em': '2026-11-05T00:00:00Z',
               'sha256_fonte': hashlib.sha256(raw).hexdigest(), 'bytes': len(raw),
               'snapshot': snap.name, 'charset': 'utf-8', 'utilizavel': True}
        lote.save_coleta({'itens': {new_id: new, old_id: {'tipo': 'RCN',
                          'anexo_fonte_alternativa': old_source['anexo_fonte_alternativa']}}})
        with patch.object(lote, 'PROVAS', self.root), patch.object(lote, 'FED', fed):
            lote.write_json(lote.fontes_json_path(), {old_id: old_source})
            lote.write_json(lote.manifesto_path(), {'documentos': [old_doc]})
            lote.write_json(lote.cobertura_path(), {'itens': {old_id: old_proof}})
            lote.build(tipos=['RSF'])
            self.assertEqual(old_path.read_text(encoding='utf-8'), old_text)
            self.assertEqual(json.loads(lote.fontes_json_path().read_text())[old_id], old_source)
            self.assertIn(old_doc, json.loads(lote.manifesto_path().read_text())['documentos'])
            self.assertEqual(json.loads(lote.cobertura_path().read_text())['itens'][old_id], old_proof)
        self.assertIn('Art. 1º Texto da resolução.', (fed / (new_id + '.md')).read_text())


class TestEspeciesLegislativasFederais(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.catalogos = json.loads((PROVAS / 'catalogos.json').read_text(encoding='utf-8'))
        cls.manifesto = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
        cls.fontes = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
        cls.limites = json.loads((PROVAS / 'limites-catalogos.json').read_text(encoding='utf-8'))
        cls.recs = {
            tipo: json.loads((PROVAS / f'reconciliacao-{tipo.lower()}.json').read_text(encoding='utf-8'))
            for tipo in lote.SPECIES
        }

    def test_catalogos_preservados_com_hash(self):
        for tipo, info in self.catalogos['especies'].items():
            with self.subTest(tipo=tipo):
                raw = lzma.decompress((ROOT / info['snapshot']).read_bytes())
                self.assertEqual(nl.sha256(raw), info['sha256'])
                self.assertEqual(len(lote.parse_lista(raw)), info['registros'])
                self.assertEqual(info['registros'], self.recs[tipo]['catalogo_registros'])
                self.assertGreater(info['registros'], 0)

    def test_reconciliacao_cobre_todas_as_identidades(self):
        published = {p.stem for p in (ROOT / 'federal').glob('br-federal-*.md')}
        for tipo, rec in self.recs.items():
            with self.subTest(tipo=tipo):
                self.assertEqual(len(rec['itens']), rec['catalogo_registros'])
                self.assertEqual(rec['orgao_emissor'], lote.SPECIES[tipo]['orgao_emissor'])
                slugs = set()
                for item in rec['itens']:
                    self.assertEqual(item['tipo'], tipo)
                    self.assertTrue(item['senado_id'])
                    self.assertTrue(item['slug'].startswith(f"br-federal-{lote.SPECIES[tipo]['slug_tipo']}-"))
                    expected = lote.slug_for(tipo, item['data'], item['numero'] or 'sn', item.get('complemento'))
                    self.assertEqual(item['slug'], expected)
                    self.assertIn(item['estado_coleta'], {
                        'publicado', 'identificado-nao-coletado', 'anexos-pendentes', 'fonte-sem-html',
                    })
                    self.assertNotIn(item['slug'], slugs)
                    slugs.add(item['slug'])
                    if item['estado_coleta'] == 'publicado':
                        self.assertIn(item['slug'], published)
                        self.assertTrue((ROOT / item['caminho_publicado']).is_file())
                    else:
                        self.assertIsNone(item['caminho_publicado'])
                self.assertEqual(len(slugs), rec['catalogo_registros'])
                self.assertEqual(rec['publicados'], sum(1 for i in rec['itens'] if i['estado_coleta'] == 'publicado'))

    def test_especies_nao_se_confundem(self):
        tipos = {doc['tipo'] for doc in self.manifesto['documentos']}
        self.assertTrue(tipos <= set(lote.SPECIES))
        # Identidade = espécie + número + data (+ complemento no slug).
        # O mesmo número em anos distintos é norma distinta.
        by_identity = {}
        for doc in self.manifesto['documentos']:
            key = (doc['tipo'], doc['norma']['numero'], doc['norma']['data'])
            by_identity.setdefault(key, []).append(doc['id'])
        for key, ids in by_identity.items():
            self.assertEqual(len(ids), 1, key)
        # Espécies distintas nunca compartilham o mesmo slug mesmo com número igual.
        slugs = [doc['id'] for doc in self.manifesto['documentos']]
        self.assertEqual(len(slugs), len(set(slugs)))

    def test_markdown_do_lote_reconverte(self):
        self.assertGreaterEqual(len(self.manifesto['documentos']), 20)
        for doc in self.manifesto['documentos']:
            slug = doc['id']
            with self.subTest(slug=slug):
                path = ROOT / doc['arquivo']
                text = path.read_text(encoding='utf-8')
                meta, body = nl.parse_frontmatter(text)
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['especie_codigo_senado'], self.fontes[slug]['tipo'])
                self.assertIn(meta['orgao_emissor'], {
                    'Congresso Nacional', 'Senado Federal', 'Câmara dos Deputados',
                })
                html = lzma.decompress((ROOT / self.fontes[slug]['snapshot']).read_bytes())
                self.assertEqual(nl.sha256(html), self.fontes[slug]['sha256'])
                item = {
                    'slug': slug,
                    'tipo': self.fontes[slug]['tipo'],
                    'fonte_url': self.fontes[slug]['url'],
                    'charset': self.fontes[slug]['charset'],
                    'normaNome': self.fontes[slug].get('normaNome') or meta['titulo'],
                    'numero': self.fontes[slug].get('numero') or meta['norma_numero'],
                    'data': self.fontes[slug].get('data') or meta['norma_data'],
                    'urn': self.fontes[slug].get('urn') or meta['urn'],
                    'ementa': self.fontes[slug].get('ementa'),
                    'capturado_em': self.fontes[slug]['capturado_em'],
                    'sha256_fonte': self.fontes[slug]['sha256'],
                    'snapshot': self.fontes[slug]['snapshot'],
                    'senado_id': self.fontes[slug]['senado_id'],
                    'fonte_orgao': meta.get('fonte_orgao'),
                }
                md2, _ = lote.build_markdown(item, html)
                if self.fontes[slug].get('anexo_fonte_alternativa'):
                    _m2, body2 = nl.parse_frontmatter(md2)
                    _mp, body_pub = nl.parse_frontmatter(text)
                    marker = '<!-- anexo-fonte-alternativa:inicio -->'
                    self.assertIn(marker, body_pub)
                    self.assertEqual(body2.rstrip(), body_pub.split(marker, 1)[0].rstrip())
                else:
                    self.assertEqual(md2, text)

    def test_limites_rcd_pos_1991_declarados(self):
        rcd = self.limites['RCD']
        self.assertEqual(rcd['senado_intervalo_observado']['fim'], '1991-09-25')
        self.assertIn('1991', rcd['aviso'])
        self.assertIn('16/2025', rcd['aviso'])
        self.assertTrue(rcd['fonte_complementar_regimento']['url'].startswith('https://bd.camara.leg.br/'))

    def test_descoberta_camara_rcd_pos_1991(self):
        path = PROVAS / 'descoberta-camara-rcd-pos-1991.json'
        self.assertTrue(path.is_file(), 'descoberta Câmara pós-1991 ausente')
        disc = json.loads(path.read_text(encoding='utf-8'))
        self.assertEqual(disc['issue'], 89)
        self.assertGreaterEqual(disc['contagem']['citacoes_unicas_numero_ano_pos_1991'], 20)
        self.assertTrue(any(i['numero'] == '16' and i['ano'] == 2025 for i in disc['itens']))
        pdf = lzma.decompress((ROOT / disc['fonte_oficial']['snapshot_pdf']).read_bytes())
        self.assertEqual(nl.sha256(pdf), disc['fonte_oficial']['sha256_pdf'])
        # Descoberta ≠ íntegra automática: estados admitidos são explícitos.
        estados_ok = {
            'identificado-nao-coletado',
            'coletado-legin-publicacaooriginal',
        }
        for item in disc['itens']:
            self.assertIn(item['estado_coleta'], estados_ok)
            if item['estado_coleta'] == 'coletado-legin-publicacaooriginal':
                self.assertTrue(item.get('slug_coletado'))
                self.assertTrue(item.get('fonte_url', '').startswith('https://www2.camara.leg.br/legin/'))
        # Limites devem apontar para o artefato.
        self.assertIn('descoberta_camara_pos_1991', self.limites['RCD'])
        self.assertEqual(
            self.limites['RCD']['descoberta_camara_pos_1991']['arquivo'],
            'provas/especies-legislativas-federais/descoberta-camara-rcd-pos-1991.json',
        )

    def test_extract_camara_legin_e_data_da_url(self):
        html = (
            b'<html><body><div id="content"><h2>RESOLUCAO DA CAMARA DOS DEPUTADOS N 16, DE 2025</h2>'
            b'<div class="textoNorma"><div class="texto">'
            b'<p>Faco saber que a CAMARA DOS DEPUTADOS aprovou e eu promulgo a seguinte Resolucao:</p>'
            b'<p>Art. 1o O Regimento Interno passa a vigorar com as alteracoes.</p>'
            b'<p>Art. 2o Esta Resolucao entra em vigor na data de sua publicacao.</p>'
            b'<p>CAMARA DOS DEPUTADOS, na data da chancela.</p>'
            b'<p>HUGO MOTTA</p>'
            b'</div></div></div></body></html>'
        )
        frag = lote.extract_camara_legin_fragment(html)
        self.assertIsNone(lote.html_rejection_reason(frag))
        self.assertIn(b'Art.', frag)
        url = (
            'https://www2.camara.leg.br/legin/fed/rescad/2025/'
            'resolucaodacamaradosdeputados-16-9-abril-2025-797341-publicacaooriginal-175166-pl.html'
        )
        self.assertEqual(
            lote.parse_camara_legin_date(html, fallback='2025-04-09', fonte_url=url),
            '2025-04-09',
        )
        # Sem URL e sem fecho datado, usa fallback (nao pega data citada no corpo).
        html_citacao = html + b'<p>aprovado pela Resolucao n 17, de 21 de setembro de 1989</p>'
        self.assertEqual(
            lote.parse_camara_legin_date(html_citacao, fallback='2025-04-09'),
            '2025-04-09',
        )

    def test_rejeita_html_de_erro_login_e_falsa_integra(self):
        cases = [
            (b'<html><body>Just a moment...</body></html>', True),
            (b'<html><title>Verifica\xc3\xa7\xc3\xa3o de seguran\xc3\xa7a</title><body>cloudflare</body></html>', True),
            (b'<html><body>acesso negado</body></html>', True),
            (b'<html><body>ok</body></html>', True),  # texto curto demais
            (
                b'<html><body><p>RESOLUCAO N 1 DE 2021</p>'
                b'<p>Art. 1o Fica alterado o regimento comum do Congresso Nacional.</p>'
                b'<p>Art. 2o Esta resolucao entra em vigor na data de sua publicacao.</p>'
                b'<p>Art. 3o Revogam-se as disposicoes em contrario.</p>'
                b'<p>Brasilia, 23 de marco de 2021.</p></body></html>',
                False,
            ),
        ]
        for html, should_reject in cases:
            with self.subTest(html=html[:40]):
                reason = lote.html_rejection_reason(html)
                if should_reject:
                    self.assertIsNotNone(reason)
                else:
                    self.assertIsNone(reason)

    def test_corrupcao_semantica_do_markdown_publicado(self):
        """Identidade no corpo: número da norma presente; remoção artificial é detectável."""
        for doc in self.manifesto['documentos']:
            slug = doc['id']
            with self.subTest(slug=slug):
                text = (ROOT / doc['arquivo']).read_text(encoding='utf-8')
                meta, body = nl.parse_frontmatter(text)
                numero = str(meta['norma_numero']).split('-')[0]
                self.assertRegex(body, rf'\b{re.escape(numero)}\b')
                corrupted = re.sub(rf'\b{re.escape(numero)}\b', '###', body)
                self.assertIsNone(
                    re.search(rf'\b{re.escape(numero)}\b', corrupted),
                    f'{slug}: corrupção do número não foi total',
                )
                # O verificador do lote rejeitaria HTML de login injetado no snapshot.
                self.assertIsNotNone(lote.html_rejection_reason(
                    b'<html><body>Verificacao de seguranca - faca login</body></html>'
                ))


    def test_rcn_anexos_recuperados_fontes_alternativas(self):
        """HTTP 200+PDF 0 bytes no Senado não prova peça inacessível em todas as fontes."""
        bloqueio = json.loads((PROVAS / 'bloqueio-anexos-rcn-pdf-vazio.json').read_text(encoding='utf-8'))
        evidencia = json.loads(
            (PROVAS / 'anexos-rcn/recuperacao-fontes-alternativas.json').read_text(encoding='utf-8')
        )
        self.assertEqual(len(evidencia['itens']), 6)
        self.assertEqual(bloqueio.get('slugs_anexos_pendentes'), [])
        self.assertIn('inacess', bloqueio.get('interpretacao', '').lower())
        rec = self.recs['RCN']
        self.assertEqual(rec['anexos_pendentes'], 0)
        self.assertEqual(rec['publicados'], rec['catalogo_registros'])
        for slug, item in evidencia['itens'].items():
            with self.subTest(slug=slug):
                alt = item['fonte_alternativa']
                raw = lzma.decompress((ROOT / alt['snapshot']).read_bytes())
                self.assertEqual(nl.sha256(raw), alt['sha256'])
                self.assertGreater(alt['bytes'], 0)
                path = ROOT / 'federal' / f'{slug}.md'
                text = path.read_text(encoding='utf-8')
                meta, body = nl.parse_frontmatter(text)
                self.assertIn('anexo-fonte-alternativa', text)
                self.assertRegex(body, re.compile(r'(?im)^#\s*ANEXO\b'))
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
                self.assertIs(meta['vigencia_certificada'], False)
                # Estado reconciliado
                rec_item = next(i for i in rec['itens'] if i['slug'] == slug)
                self.assertEqual(rec_item['estado_coleta'], 'publicado')


if __name__ == '__main__':
    unittest.main()
