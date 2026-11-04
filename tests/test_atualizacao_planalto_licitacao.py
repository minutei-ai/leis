"""Regressões da atualização Planalto — issue #93.

Lê somente o repositório; não acessa a rede. Confere dispositivos-alvo,
perda de eficácia da MP 1.349/2026 e reconversão integral dos snapshots.
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
import atualizacao_planalto_licitacao as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/atualizacao-planalto-licitacao'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
BASELINE = json.loads((PROVAS / 'baseline-edicao-anterior.json').read_text(encoding='utf-8'))


class TestAtualizacaoPlanaltoLicitacao(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {k: lzma.decompress((ROOT / FONTES[k]['snapshot']).read_bytes()) for k in FONTES}
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_catalogo_exato_quatro_normas(self):
        self.assertEqual(sorted(FONTES), sorted(d['fonte'] for d in lote.DOCS))
        self.assertEqual(sorted(d['slug'] for d in lote.DOCS), sorted(d['id'] for d in MANIFESTO['documentos']))
        self.assertEqual(MANIFESTO['lote'], 'atualizacao-planalto-licitacao')
        self.assertEqual(MANIFESTO['issue'], 93)

    def test_snapshots_hashes(self):
        for key, meta in FONTES.items():
            with self.subTest(key=key):
                snap = ROOT / meta['snapshot']
                self.assertTrue(snap.is_file())
                xz = snap.read_bytes()
                self.assertEqual(nl.sha256(xz), meta['sha256_snapshot_armazenado'])
                raw = lzma.decompress(xz)
                self.assertEqual(nl.sha256(raw), meta['sha256'])
                self.assertEqual(nl.content_sha256(raw), meta['sha256_conteudo'])

    def test_markdown_publicado_bate_reconversao(self):
        for slug, payload in self.docs_out.items():
            with self.subTest(slug=slug):
                published = (ROOT / payload['arquivo']).read_text(encoding='utf-8')
                self.assertEqual(published, payload['markdown'])
                meta, body = nl.parse_frontmatter(published)
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['situacao'], 'nao-informada')
                self.assertEqual(meta['edicao_tipo'], 'consolidada')
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))

    def test_regressao_11246(self):
        body = nl.parse_frontmatter((ROOT / 'federal/br-federal-decreto-2022-10-27-11246.md').read_text(encoding='utf-8'))[1]
        self.assertRegex(body, r'§ 1º.*os gestores e os fiscais de contratos')
        self.assertIn('Decreto nº 13.031', body)
        self.assertIn('gestor setorial', body)
        self.assertRegex(body, r'III - fiscalização administrativa[\s\S]{0,900}Decreto nº 13\.031')

    def test_regressao_11878(self):
        body = nl.parse_frontmatter((ROOT / 'federal/br-federal-decreto-2024-01-09-11878.md').read_text(encoding='utf-8'))[1]
        self.assertIn('art. 79, caput, incisos I a III', body)
        self.assertIn('Decreto nº 13.106', body)

    def test_regressao_12527(self):
        body = nl.parse_frontmatter((ROOT / 'federal/br-federal-lei-2011-11-18-12527.md').read_text(encoding='utf-8'))[1]
        self.assertIn('Art. 8º-A.', body)
        self.assertRegex(body, r'Art\. 8º-B')
        self.assertIn('Lei nº 15.141', body)

    def test_regressao_12462_e_perda_mp1349(self):
        body = nl.parse_frontmatter((ROOT / 'federal/br-federal-lei-2011-08-04-12462.md').read_text(encoding='utf-8'))[1]
        self.assertRegex(body, r'§ 17\..*capital de giro')
        self.assertIn('Medida Provisória nº 1.349', body)
        st = MANIFESTO['mp_1349_status']
        self.assertEqual(st['decisao']['sigla'], 'PERDA_EFICACIA')
        self.assertEqual(st['situacao_atual'], 'SEM EFICÁCIA')
        self.assertIn('PERDA_EFICACIA', body)
        self.assertIn('perda de eficácia', body.lower())

    def test_baseline_edicao_anterior_preservada(self):
        self.assertEqual(len(BASELINE['documentos']), 4)
        for slug in (d['slug'] for d in lote.DOCS):
            self.assertIn(slug, BASELINE['documentos'])
            self.assertEqual(len(BASELINE['documentos'][slug]['sha256']), 64)

    def test_edicao_historica_publicada(self):
        for doc in lote.DOCS:
            slug = doc['slug']
            with self.subTest(slug=slug):
                hist = ROOT / lote.historica_path(slug)
                self.assertTrue(hist.is_file(), hist)
                meta, body = nl.parse_frontmatter(hist.read_text(encoding='utf-8'))
                self.assertEqual(meta['edicao_tipo'], 'historica')
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['situacao'], 'nao-informada')
                self.assertEqual(meta['sha256_corpo_preservado'], BASELINE['documentos'][slug]['sha256'])
                self.assertEqual(meta['sha256_markdown'], nl.sha256(body.encode('utf-8')))
                consol_meta, consol_body = nl.parse_frontmatter(
                    (ROOT / doc['arquivo']).read_text(encoding='utf-8'))
                self.assertEqual(consol_meta['edicao_relacionada'], f'{slug}-historica')
                self.assertIn(lote.historica_path(slug), consol_body)

    def test_cobertura_fonte_markdown(self):
        for slug, proof in self.proofs.items():
            with self.subTest(slug=slug):
                self.assertTrue(proof['cobertura_texto']['equivalente'], proof['cobertura_texto'])


if __name__ == '__main__':
    unittest.main()
