"""Cobertura fonte→Markdown do lote prioritário #71 (leis 5.000–11.999).

Lê somente o repositório; não acessa a rede. Reconverte os snapshots oficiais
preservados e confere equivalência textual integral (inclui normalização
tipográfica de ordinais do Planalto, ex. Lei 9.784).
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
CATALOGO = json.loads((PROVAS / 'prioridades-catalogo.json').read_text(encoding='utf-8'))


class TestFederalPrioridade500011999(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        # Mesma pipeline do verify/build: snapshots + normalização tipográfica de ordinais.
        cls.sources = {key: lote.source_bytes(key) for key in lote.SOURCES}
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_lote_segue_catalogo_prioridades(self):
        self.assertEqual(MANIFESTO['lote'], 'federal-prioridade-5000-11999')
        expected = len(CATALOGO['documentos'])
        self.assertEqual(expected, 94)
        self.assertEqual(len(MANIFESTO['documentos']), expected)
        self.assertEqual(len(lote.DOCS), expected)
        self.assertEqual(sorted(FONTES), sorted(lote.SOURCES))
        self.assertEqual(len(lote.SOURCES), expected)
        self.assertFalse(MANIFESTO.get('prioridade_restante'))

    def test_lei_9784_normalizacao_ordinal_sem_enfraquecer_cobertura(self):
        """Regressão 1o/1oo: cobertura integral após normalize_planalto_ordinals."""
        doc = next(d for d in lote.DOCS if d['norma']['numero'] == '9784')
        key = doc['fonte']
        raw = lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes())
        norm = lote.normalize_planalto_ordinals(raw)
        self.assertNotEqual(raw, norm)
        # Sem normalização a cobertura tipográfica diverge; com ela, deve fechar.
        conv_raw = nl.convert_html(raw, 'cp1252', FONTES[key]['url'])
        body_raw = nl.blocks_to_markdown(conv_raw.blocks, lote.TITLE_PATTERN)
        src_raw = nl.strip_fold(nl.source_text_chars_from_html(raw, 'cp1252'))
        md_raw = nl.strip_fold(nl.md_text_all(body_raw))
        self.assertNotEqual(src_raw, md_raw)

        proof = self.proofs[doc['slug']]
        self.assertTrue(proof['cobertura_texto']['equivalente'])
        self.assertTrue(proof.get('normalizacao_ordinal_planalto'))
        published = json.loads(
            (PROVAS / f"reconciliacao-{doc['slug']}.json").read_text(encoding='utf-8')
        )
        self.assertTrue(published['cobertura_texto']['equivalente'])
        self.assertTrue(published.get('normalizacao_ordinal_planalto'))
        # Validação permanece estrita: src normalizado == md (não só substring).
        src = nl.strip_fold(nl.source_text_chars_from_html(norm, 'cp1252'))
        conv = nl.convert_html(norm, 'cp1252', FONTES[key]['url'])
        body = nl.blocks_to_markdown(conv.blocks, lote.TITLE_PATTERN)
        md = nl.strip_fold(nl.md_text_all(body))
        self.assertEqual(src, md)
        self.assertEqual(len(src), proof['cobertura_texto']['caracteres_normalizados_fonte'])

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
                if doc.get('normalize_ordinals', True):
                    self.assertTrue(published.get('normalizacao_ordinal_planalto'))

    def test_reconcile_serie_artefato_e_faixa(self):
        path = PROVAS / 'catalogo-serie-reconciliacao.json'
        self.assertTrue(path.is_file(), path)
        cat = json.loads(path.read_text(encoding='utf-8'))
        totais = cat['totais']
        self.assertEqual(totais['faixa'], [5000, 11999])
        self.assertEqual(totais['anos_catalogo'], list(range(1966, 2010)))
        self.assertGreater(totais['identidades_catalogo_faixa'], 1000)
        self.assertEqual(
            totais['identidades_catalogo_faixa'],
            totais['presente_exato'] + totais['revisao_data_divergente'] + totais['ausente_canonico'],
        )
        # Prioridades do lote na faixa/anos da série devem constar no catálogo.
        published = {d['norma']['numero'] for d in MANIFESTO['documentos']}
        by_num = {}
        for row in cat['identidades']:
            by_num.setdefault(row['numero'], []).append(row)
        for doc in lote.DOCS:
            n = doc['norma']['numero']
            year = int(doc['norma']['data'][:4])
            self.assertIn(n, published)
            if 5000 <= int(n) <= 11999 and 1966 <= year <= 2009:
                rows = by_num.get(n) or []
                self.assertTrue(rows, f'série sem identidade Senado para {n}')
                self.assertTrue(
                    any(r['estado_coleta'] == 'presente-exato' for r in rows),
                    f'{n} deveria estar presente-exato após o lote',
                )


if __name__ == '__main__':
    unittest.main()
