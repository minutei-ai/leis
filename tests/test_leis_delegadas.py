"""Cobertura por identidade do catálogo Senado e fonte→Markdown das leis delegadas.

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
import leis_delegadas as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/leis-delegadas'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
CATALOGO = json.loads((PROVAS / 'catalogo-reconciliacao.json').read_text(encoding='utf-8'))


class TestLeisDelegadas(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            key: lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes())
            for key in lote.SOURCES
        }
        cls.docs_out, cls.proofs, cls.manifest, cls.catalogo = lote.compute(cls.sources, FONTES)

    def test_catalogo_senado_tem_13_identidades(self):
        self.assertEqual(CATALOGO['totais']['identidades_catalogo'], 13)
        self.assertEqual(len(CATALOGO['identidades']), 13)
        self.assertEqual(CATALOGO['sha256_catalogo_issue'], lote.SENADO_LDL_SHA256_ISSUE)
        self.assertEqual(MANIFESTO['lote'], 'leis-delegadas')
        self.assertEqual(len(MANIFESTO['documentos']), 12)

    def test_cobertura_por_identidade_contra_catalogo(self):
        """Aceite #67: cada identidade do catálogo tem caminho canônico."""
        by_id = {row['senado_id']: row for row in CATALOGO['identidades']}
        expected_ids = {item['senado_id'] for item in lote.CATALOGO}
        self.assertEqual(set(by_id), expected_ids)
        for item in lote.CATALOGO:
            row = by_id[item['senado_id']]
            path = ROOT / lote.arquivo_for(item)
            self.assertTrue(path.is_file(), path)
            self.assertEqual(row['caminho_publicado'], lote.arquivo_for(item))
            if item.get('preexistente'):
                self.assertEqual(row['estado_coleta'], 'presente-preexistente')
                self.assertFalse(row['neste_lote'])
            else:
                self.assertEqual(row['estado_coleta'], 'publicado')
                self.assertTrue(row['neste_lote'])

    def test_nenhuma_identidade_nao_recuperada(self):
        self.assertEqual(CATALOGO['totais']['nao_recuperadas'], 0)
        self.assertEqual(CATALOGO['totais']['publicadas_neste_lote'], 12)
        self.assertEqual(CATALOGO['totais']['preexistentes'], 1)

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
                self.assertEqual(meta['norma_tipo'], 'lei-delegada')
                self.assertEqual(meta['edicao_tipo'], 'historica')
                self.assertEqual(meta['edicao_integral'], nl.UNKNOWN)
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertEqual(meta['norma_numero'], doc['norma']['numero'])
                self.assertEqual(meta['norma_data'], doc['norma']['data'])
                self.assertIn('LEI DELEGADA', body)
                self.assertIn('não certifica vigência', body)
                proof = self.proofs[slug]
                self.assertTrue(proof['cobertura_texto']['equivalente'])
                published = json.loads((PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8'))
                self.assertTrue(published['cobertura_texto']['equivalente'])
                self.assertEqual(published['senado_id'], doc['senado_id'])

    def test_identidade_unica_no_acervo_federal(self):
        for item in lote.CATALOGO:
            number = item['numero']
            hits = [
                p.name for p in (ROOT / 'federal').iterdir()
                if p.name.startswith('br-federal-lei-delegada-')
                and re.search(r'-' + re.escape(number) + r'\.md$', p.name)
            ]
            self.assertEqual(len(hits), 1, hits)

    def test_senado_catalogo_preservado(self):
        path = PROVAS / 'senado-LDL.json'
        self.assertTrue(path.is_file())
        data = path.read_bytes()
        self.assertEqual(nl.sha256(data) if hasattr(nl, 'sha256') else lote.sha256_bytes(data),
                         FONTES['senado-LDL']['sha256'])
        self.assertEqual(lote.sha256_bytes(data), FONTES['senado-LDL']['sha256'])
        payload = json.loads(data)
        docs = payload['ListaDocumento']['documentos']
        if isinstance(docs, dict):
            docs = docs['documento']
        self.assertEqual(len(docs), 13)
        ids = {d['id'] for d in docs}
        self.assertEqual(ids, {item['senado_id'] for item in lote.CATALOGO})


if __name__ == '__main__':
    unittest.main()
