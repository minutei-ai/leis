"""Cobertura fonte→Markdown e identidade do lote CTN / Lei do SUS.

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
import nucleo_federal_ctn_sus as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/nucleo-federal-ctn-sus'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))

DOCS = {
    'br-federal-lei-1966-10-25-5172': dict(
        arquivo='federal/br-federal-lei-1966-10-25-5172.md',
        fonte='planalto-l5172compilado',
        numero='5172',
        data='1966-10-25',
        titulo_fragmento='LEI Nº 5.172',
        denominacao='Código Tributário Nacional',
        url='https://www.planalto.gov.br/ccivil_03/leis/l5172compilado.htm',
        min_artigos=200,
        min_tabelas=2,
    ),
    'br-federal-lei-1990-09-19-8080': dict(
        arquivo='federal/br-federal-lei-1990-09-19-8080.md',
        fonte='planalto-l8080',
        numero='8080',
        data='1990-09-19',
        titulo_fragmento='LEI Nº 8.080',
        denominacao=None,
        url='https://www.planalto.gov.br/ccivil_03/leis/l8080.htm',
        min_artigos=50,
        min_tabelas=0,
    ),
}


def sha256(data: bytes) -> str:
    return nl.sha256(data)


class TestNucleoFederalCtnSus(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {key: lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes()) for key in FONTES}
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_catalogo_exato_ctn_e_sus(self):
        self.assertEqual(sorted(FONTES), sorted(d['fonte'] for d in DOCS.values()))
        self.assertEqual(sorted(DOCS), sorted(d['id'] for d in MANIFESTO['documentos']))
        self.assertEqual(MANIFESTO['lote'], 'nucleo-federal-ctn-sus')
        # Este lote não publica CDC/ECA/LGPD.
        for foreign in ('8078', '8069', '13709', '8213', '11340'):
            self.assertFalse(any(foreign in d['id'] for d in MANIFESTO['documentos']))

    def test_identidade_unica_no_acervo_federal(self):
        for number in ('5172', '8080'):
            hits = [
                p.name for p in (ROOT / 'federal').iterdir()
                if p.name.startswith('br-federal-lei-')
                and re.search(r'-' + number + r'(?:-|\.md)', p.name)
            ]
            self.assertEqual(len(hits), 1, hits)
            self.assertTrue(hits[0].endswith(f'-{number}.md'))

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
                self.assertEqual(meta['url'], DOCS[[d for d in DOCS if DOCS[d]['fonte'] == key][0]]['url'])
                self.assertIn('DOU de', meta.get('dou_aviso') or '')

    def test_reconversao_integral_bate_com_markdown_publicado(self):
        for slug, spec in DOCS.items():
            with self.subTest(slug=slug):
                path = ROOT / spec['arquivo']
                published = path.read_text(encoding='utf-8')
                self.assertEqual(published, self.docs_out[slug]['markdown'])
                meta, body = nl.parse_frontmatter(published)
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['fonte_conferencia'], 'nenhuma')
                self.assertEqual(meta['norma_numero'], spec['numero'])
                self.assertEqual(meta['norma_data'], spec['data'])
                self.assertEqual(meta['fonte_url'], spec['url'])
                self.assertIn(spec['titulo_fragmento'], body)
                self.assertIn('nota-edicao:inicio', body)
                self.assertIn('não certifica vigência', body)

    def test_cobertura_fonte_para_markdown_nao_so_hash(self):
        """Gate forte: texto normalizado da página HTML == texto do Markdown convertido."""
        for slug, spec in DOCS.items():
            with self.subTest(slug=slug):
                key = spec['fonte']
                raw = self.sources[key]
                charset = lote.SOURCES[key]['charset']
                conv = nl.convert_html(raw, charset, spec['url'])
                body = nl.blocks_to_markdown(conv.blocks, r'^LEI(?: COMPLEMENTAR)? N')
                src = nl.strip_fold(nl.source_text_chars_from_html(raw, charset))
                md_all = nl.strip_fold(nl.md_text_all(body))
                self.assertEqual(src, md_all, f'{slug}: divergência textual fonte↔Markdown')
                self.assertGreater(len(src), 10_000, slug)
                proof = self.proofs[slug]
                self.assertTrue(proof['cobertura_texto']['equivalente'])
                self.assertEqual(proof['cobertura_texto']['caracteres_normalizados_fonte'], len(src))
                published_proof = json.loads(
                    (PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8'))
                self.assertTrue(published_proof['cobertura_texto']['equivalente'])
                # Amostras de conteúdo jurídico (não bastam sozinhas; a igualdade acima é o gate).
                plain = nl.md_text_all(body)
                self.assertRegex(plain, r'Art\.\s*1')
                arts, order = nl.split_articles(conv.blocks)
                self.assertGreaterEqual(len(order), spec['min_artigos'], slug)
                self.assertGreaterEqual(
                    conv.stats['tabelas_markdown'] + conv.stats['tabelas_html'],
                    spec['min_tabelas'], slug)
                if spec['denominacao']:
                    self.assertIn(spec['denominacao'], plain)
                if slug.endswith('8080'):
                    self.assertRegex(plain, r'Sistema Único de Saúde|SUS')

    def test_ctn_preserva_tabelas_e_retificacao_dou(self):
        slug = 'br-federal-lei-1966-10-25-5172'
        text = (ROOT / DOCS[slug]['arquivo']).read_text(encoding='utf-8')
        self.assertGreaterEqual(text.count('\n| '), 20)
        self.assertIn('Inverso do índice relativo à renda per capita', text)
        self.assertIn('Categoria do Município, segundo seu número de habitantes', text)
        self.assertIn('retificado em 31.10.1966', text)
        self.assertIn('DOU de 27.10.1966', text)

    def test_sus_preserva_riscados_e_notas(self):
        slug = 'br-federal-lei-1990-09-19-8080'
        text = (ROOT / DOCS[slug]['arquivo']).read_text(encoding='utf-8')
        self.assertIn('~~', text)
        self.assertIn('DOU de 20.9.1990', text)
        self.assertRegex(text, r'Mensagem de veto|mensagem de veto', re.I)
        proof = json.loads((PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(proof['conversao']['trechos_riscados'], 1)

    def test_verify_offline_recomputa(self):
        lote.verify()


if __name__ == '__main__':
    unittest.main()
