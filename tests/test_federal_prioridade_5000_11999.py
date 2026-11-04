"""Cobertura fonte→Markdown do lote prioritário #71 (leis 5.000–11.999).

Lê somente o repositório; não acessa a rede. Reconverte os snapshots oficiais
preservados e confere equivalência textual integral.
"""
from __future__ import annotations

import json
import lzma
import sys
import unittest
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / 'scripts'))
sys.dont_write_bytecode = True
import federal_prioridade_5000_11999 as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/federal-prioridade-5000-11999'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))


class TestFederalPrioridade500011999(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            key: lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes())
            for key in lote.SOURCES
        }
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_lote_tem_25_documentos(self):
        self.assertEqual(MANIFESTO['lote'], 'federal-prioridade-5000-11999')
        self.assertEqual(len(MANIFESTO['documentos']), 25)
        self.assertEqual(len(lote.DOCS), 25)
        self.assertEqual(sorted(FONTES), sorted(lote.SOURCES))

    def test_snapshots_hashes_e_conteudo_estavel(self):
        for key in lote.SOURCES:
            with self.subTest(key=key):
                meta = FONTES[key]
                snap = ROOT / meta['snapshot']
                self.assertTrue(snap.is_file(), snap)
                xz = snap.read_bytes()
                self.assertEqual(nl.sha256(xz), meta['sha256_snapshot_armazenado'])
                raw = lzma.decompress(xz)
                self.assertEqual(nl.sha256(raw), meta['sha256'])
                self.assertEqual(nl.content_sha256(raw), meta['sha256_conteudo'])
                self.assertEqual(len(raw), meta['bytes'])
                self.assertTrue(meta['capturado_em'].endswith('Z'))

    def test_markdown_reconverte_e_cobertura_integral(self):
        for doc in lote.DOCS:
            slug = doc['slug']
            with self.subTest(slug=slug):
                path = ROOT / doc['arquivo']
                text = path.read_text(encoding='utf-8')
                self.assertEqual(text, self.docs_out[slug]['markdown'])
                meta, body = nl.parse_frontmatter(text)
                self.assertEqual(meta['norma_tipo'], 'lei')
                self.assertEqual(meta['edicao_tipo'], doc['edicao']['tipo'])
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['norma_numero'], doc['norma']['numero'])
                self.assertEqual(meta['norma_data'], doc['norma']['data'])
                self.assertIn('não certifica vigência', body)
                proof = self.proofs[slug]
                self.assertTrue(proof['cobertura_texto']['equivalente'])
                published = json.loads(
                    (PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8')
                )
                self.assertTrue(published['cobertura_texto']['equivalente'])


if __name__ == '__main__':
    unittest.main()
