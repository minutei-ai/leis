"""Cobertura fonte→Markdown e identidade do lote Lei 8.213 / Lei Maria da Penha.

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
import nucleo_federal_beneficios_mdp as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/nucleo-federal-beneficios-mdp'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))

DOCS = {
    'br-federal-lei-1991-07-24-8213': dict(
        arquivo='federal/br-federal-lei-1991-07-24-8213.md',
        fonte='planalto-l8213cons',
        numero='8213',
        data='1991-07-24',
        titulo_fragmento='LEI Nº 8.213',
        denominacao='Planos de Benefícios da Previdência Social',
        url='https://www.planalto.gov.br/ccivil_03/leis/l8213cons.htm',
        min_artigos=150,
        min_tabelas=1,
        orgao_fragmento='Planalto',
        exige_dou=True,
        exige_riscado=True,
    ),
    'br-federal-lei-2006-08-07-11340': dict(
        arquivo='federal/br-federal-lei-2006-08-07-11340.md',
        fonte='camara-lei-11340-normaatualizada',
        numero='11340',
        data='2006-08-07',
        titulo_fragmento='LEI Nº 11.340',
        denominacao='Lei Maria da Penha',
        url=('https://www2.camara.leg.br/legin/fed/lei/2006/'
             'lei-11340-7-agosto-2006-545133-normaatualizada-pl.html'),
        min_artigos=40,
        min_tabelas=0,
        orgao_fragmento='Câmara',
        exige_dou=False,
        exige_riscado=False,
    ),
}


def sha256(data: bytes) -> str:
    return nl.sha256(data)


class TestNucleoFederalBeneficiosMdp(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {key: lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes()) for key in FONTES}
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_catalogo_exato_beneficios_e_maria_da_penha(self):
        self.assertEqual(sorted(FONTES), sorted(d['fonte'] for d in DOCS.values()))
        self.assertEqual(sorted(DOCS), sorted(d['id'] for d in MANIFESTO['documentos']))
        self.assertEqual(MANIFESTO['lote'], 'nucleo-federal-beneficios-mdp')
        # Este lote não publica CDC/ECA/CTN/SUS.
        for foreign in ('8078', '8069', '5172', '8080'):
            self.assertFalse(any(foreign in d['id'] for d in MANIFESTO['documentos']))

    def test_identidade_unica_no_acervo_federal(self):
        for number in ('8213', '11340'):
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
                slug = [d for d in DOCS if DOCS[d]['fonte'] == key][0]
                self.assertEqual(meta['url'], DOCS[slug]['url'])
                if DOCS[slug]['exige_dou']:
                    self.assertIn('DOU de', meta.get('dou_aviso') or '')
                else:
                    # Câmara normaatualizada não traz o rodapé canônico do Planalto.
                    self.assertTrue(meta.get('dou_aviso') in (None, '') or 'DOU' in (meta.get('dou_aviso') or ''))

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
                self.assertIn(spec['orgao_fragmento'], meta['fonte_orgao'])

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
                plain = nl.md_text_all(body)
                self.assertRegex(plain, r'Art\.\s*1')
                arts, order = nl.split_articles(conv.blocks)
                self.assertGreaterEqual(len(order), spec['min_artigos'], slug)
                self.assertGreaterEqual(
                    conv.stats['tabelas_markdown'] + conv.stats['tabelas_html'],
                    spec['min_tabelas'], slug)
                if spec['denominacao']:
                    self.assertIn(spec['denominacao'], plain)

    def test_lei_8213_preserva_tabelas_riscados_e_dou(self):
        slug = 'br-federal-lei-1991-07-24-8213'
        text = (ROOT / DOCS[slug]['arquivo']).read_text(encoding='utf-8')
        self.assertGreaterEqual(text.count('\n| '), 8)
        self.assertIn('~~', text)
        self.assertIn('DOU de 25.7.1991', text)
        self.assertRegex(text, r'republicado', re.I)
        self.assertIn('Planos de Benefícios da Previdência Social', text)
        proof = json.loads((PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(proof['conversao']['trechos_riscados'], 100)
        self.assertGreaterEqual(proof['conversao']['tabelas_markdown'] + proof['conversao'].get('tabelas_html', 0), 1)

    def test_lei_11340_preserva_ementa_maria_da_penha_e_artigos(self):
        slug = 'br-federal-lei-2006-08-07-11340'
        text = (ROOT / DOCS[slug]['arquivo']).read_text(encoding='utf-8')
        self.assertIn('Lei Maria da Penha', text)
        self.assertIn('violência doméstica e familiar contra a mulher', text)
        self.assertIn('Câmara dos Deputados', text)
        self.assertRegex(text, r'Art\.\s*1')
        self.assertRegex(text, r'Art\.\s*46')
        proof = json.loads((PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8'))
        self.assertGreaterEqual(proof['conversao']['artigos'], 40)

    def test_verify_offline_recomputa(self):
        lote.verify()


if __name__ == '__main__':
    unittest.main()
