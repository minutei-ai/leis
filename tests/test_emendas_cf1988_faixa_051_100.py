"""Cobertura fonte→Markdown e identidade do lote Emendas CF/1988 faixa 51–100.

Lê somente o repositório; não acessa a rede. Reconverte os snapshots oficiais
preservados e confere equivalência textual integral (não só hashes ou frases).
"""
from __future__ import annotations

import json
import lzma
import re
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import emendas_cf1988_faixa_051_100 as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/emendas-cf1988/faixa-051-100'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
MATRIZ = json.loads((PROVAS / 'matriz.json').read_text(encoding='utf-8'))


def sha256(data: bytes) -> str:
    return nl.sha256(data)


class TestEmendasCf1988Faixa051100(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {key: lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes()) for key in FONTES}
        cls.docs_out, cls.proofs, cls.manifest, cls.matriz = lote.compute(cls.sources, FONTES)

    def test_catalogo_exato_do_lote(self):
        self.assertEqual(sorted(FONTES), sorted(lote.SOURCES))
        self.assertEqual(sorted(d['id'] for d in MANIFESTO['documentos']), sorted(d['slug'] for d in lote.DOCS))
        self.assertEqual(MANIFESTO['lote'], lote.LOTE)
        self.assertEqual(MATRIZ['lote'], lote.LOTE)
        self.assertEqual(MATRIZ['numeros_alvo'], lote.LOTE_NUMEROS)
        self.assertEqual(MATRIZ['recuperados'], lote.LOTE_NUMEROS)
        self.assertEqual(MATRIZ['lacunas_neste_lote'], [])
        self.assertEqual(len(lote.DOCS), 29)
        # Fora deste lote.
        for foreign in ('19', '20', '45', '103', '132', '141'):
            self.assertFalse(any(d['norma']['numero'] == foreign for d in MANIFESTO['documentos']))

    def test_identidade_serie_cf1988_sem_revisao_nem_historica(self):
        federal = ROOT / 'federal'
        for doc in lote.DOCS:
            with self.subTest(numero=doc['numero']):
                path = federal / f"{doc['slug']}.md"
                self.assertTrue(path.is_file(), path)
                # Não publicar sob nomes de revisão ou constituições anteriores.
                self.assertNotIn('revisao', path.name)
                self.assertNotIn('revisão', path.name)
                year = int(doc['norma']['data'][:4])
                self.assertGreaterEqual(year, 1988)
                # Um único arquivo para o número neste padrão CF/1988.
                hits = [
                    p.name for p in federal.iterdir()
                    if re.fullmatch(
                        rf'br-federal-emenda-constitucional-\d{{4}}-\d{{2}}-\d{{2}}-{doc["numero"]}\.md',
                        p.name)
                ]
                self.assertEqual(hits, [f"{doc['slug']}.md"], hits)

    def test_snapshots_hashes_e_conteudo_estavel(self):
        for key, meta in FONTES.items():
            with self.subTest(key=key):
                snap = ROOT / meta['snapshot']
                self.assertTrue(snap.is_file(), snap)
                xz = snap.read_bytes()
                self.assertEqual(sha256(xz), meta['sha256_snapshot_armazenado'])
                raw = lzma.decompress(xz)
                self.assertEqual(sha256(raw), meta['sha256'])
                self.assertEqual(nl.content_sha256(raw), meta['sha256_conteudo'])
                self.assertEqual(len(raw), meta['bytes'])
                self.assertTrue(meta['capturado_em'].endswith('Z'))
                self.assertEqual(meta['url'], lote.SOURCES[key]['url'])
                self.assertIn('DOU', meta.get('dou_aviso') or '')

    def test_reconversao_integral_bate_com_markdown_publicado(self):
        for doc in lote.DOCS:
            slug = doc['slug']
            with self.subTest(slug=slug):
                path = ROOT / doc['arquivo']
                published = path.read_text(encoding='utf-8')
                self.assertEqual(published, self.docs_out[slug]['markdown'])
                meta, body = nl.parse_frontmatter(published)
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['fonte_conferencia'], 'nenhuma')
                self.assertEqual(meta['norma_tipo'], 'emenda-constitucional')
                self.assertEqual(meta['norma_numero'], doc['norma']['numero'])
                self.assertEqual(meta['norma_data'], doc['norma']['data'])
                self.assertEqual(meta['fonte_url'], doc['norma'] and lote.SOURCES[doc['fonte']]['url'])
                self.assertIn(f"EMENDA CONSTITUCIONAL Nº {doc['numero']}", body.upper().replace('N°', 'Nº'))
                self.assertIn('nota-edicao:inicio', body)
                self.assertIn('não certifica vigência', body)
                self.assertIn('Emenda Constitucional de Revisão', body)

    def test_cobertura_fonte_para_markdown_nao_so_hash(self):
        """Gate forte: texto normalizado da página HTML == texto do Markdown convertido."""
        for doc in lote.DOCS:
            slug = doc['slug']
            with self.subTest(slug=slug):
                key = doc['fonte']
                raw = self.sources[key]
                charset = lote.SOURCES[key]['charset']
                conv = nl.convert_html(raw, charset, lote.SOURCES[key]['url'])
                body = nl.blocks_to_markdown(conv.blocks, doc['title_pattern'])
                src = nl.strip_fold(nl.source_text_chars_from_html(raw, charset))
                md_all = nl.strip_fold(nl.md_text_all(body))
                self.assertEqual(src, md_all, f'{slug}: divergência textual fonte↔Markdown')
                self.assertGreater(len(src), 500, slug)
                proof = self.proofs[slug]
                self.assertTrue(proof['cobertura_texto']['equivalente'])
                self.assertEqual(proof['cobertura_texto']['caracteres_normalizados_fonte'], len(src))
                published_proof = json.loads(
                    (PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8'))
                self.assertTrue(published_proof['cobertura_texto']['equivalente'])
                plain = nl.md_text_all(body)
                self.assertRegex(plain, r'(?i)emenda\s+constitucional')
                self.assertIn(str(doc['numero']), plain)
                # Amostra de conteúdo jurídico (autônomo / efeitos / vigência quando a fonte traz).
                self.assertTrue(
                    re.search(r'Art\.?\s*\d+|entra em vigor|Mesas da Câmara|promulgam', plain, re.I),
                    slug)

    def test_matriz_alinha_com_manifesto(self):
        self.assertEqual(len(MATRIZ['itens']), 29)
        by_num = {it['numero']: it for it in MATRIZ['itens']}
        for doc in lote.DOCS:
            item = by_num[doc['numero']]
            self.assertEqual(item['id'], doc['slug'])
            self.assertEqual(item['situacao_coleta'], 'recuperada')
            self.assertIs(item['vigencia_certificada'], False)
            self.assertEqual(item['serie'], 'emenda-constitucional-cf1988')
            self.assertEqual(item['fonte_principal']['url'], lote.SOURCES[doc['fonte']]['url'])


if __name__ == '__main__':
    unittest.main()
