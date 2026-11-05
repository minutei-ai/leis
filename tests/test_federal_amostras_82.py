"""Cobertura fonte→Markdown das amostras da issue #82.

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
import federal_amostras_82 as lote  # noqa: E402
import nucleo_licitacoes as nl  # noqa: E402

PROVAS = ROOT / 'provas/federal-amostras-82'
FONTES = json.loads((PROVAS / 'fontes.json').read_text(encoding='utf-8'))
MANIFESTO = json.loads((PROVAS / 'manifesto.json').read_text(encoding='utf-8'))
CATALOGO = json.loads((PROVAS / 'catalogo-pendencias.json').read_text(encoding='utf-8'))
RECON = ROOT / 'provas/federal-lacunas-catalogo/catalogo-82-reconciliacao.json'


class TestFederalAmostras82(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.sources = {
            key: lzma.decompress((ROOT / FONTES[key]['snapshot']).read_bytes())
            for key in lote.SOURCES
        }
        cls.docs_out, cls.proofs, cls.manifest = lote.compute(cls.sources, FONTES)

    def test_catalogo_amostras_12_publicadas(self):
        self.assertEqual(CATALOGO['issue'], 82)
        self.assertEqual(len(CATALOGO['amostras_issue']), 12)
        self.assertEqual(CATALOGO['totais']['publicadas'], 12)
        self.assertEqual(CATALOGO['totais']['pendentes'], 0)
        self.assertEqual(MANIFESTO['lote'], 'federal-amostras-82')
        self.assertEqual(len(MANIFESTO['documentos']), 12)
        self.assertEqual(len(lote.AMOSTRAS_PENDENTES), 0)
        nums = {d['norma']['numero'] for d in lote.DOCS}
        self.assertEqual(
            nums,
            {'4920', '4921', '4923', '4926', '13898', '14059', '14087', '14642', '14823', '14847', '14950', '15103'},
        )

    def test_4920_4921_4926_vem_da_camara(self):
        for n, key in [('4920', 'camara-L4920'), ('4921', 'camara-L4921'), ('4926', 'camara-L4926')]:
            doc = next(d for d in lote.DOCS if d['norma']['numero'] == n)
            self.assertEqual(doc['fonte'], key)
            self.assertEqual(doc['edicao']['identidade'], 'camara')
            self.assertIn('camara.leg.br', FONTES[key]['url'])

    def test_denominadores_reconciliados(self):
        self.assertTrue(RECON.is_file(), RECON)
        recon = json.loads(RECON.read_text(encoding='utf-8'))
        self.assertEqual(recon['criterio_identidade'], 'especie+numero/complemento+data')
        self.assertIn('1822-1965', recon['periodos'])
        self.assertIn('2010-2026', recon['periodos'])
        self.assertGreater(recon['periodos']['1822-1965']['identidades'], 0)
        self.assertGreater(recon['periodos']['2010-2026']['identidades'], 0)
        # Avanço 2010–2026 reduz ausentes sem zerar falhas de transporte/cobertura.
        self.assertLessEqual(recon['periodos']['2010-2026']['ausentes'], 20)
        self.assertGreater(recon['periodos']['2010-2026']['presentes'], 3100)
        anual = ROOT / 'provas/federal-lacunas-catalogo/senado-lei-anual/registry.json'
        self.assertTrue(anual.is_file())
        reg = json.loads(anual.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(reg['anos']), 160)

    def test_avancado_2010_2026_publicado_com_provas(self):
        docs_path = PROVAS / 'docs-avancados.json'
        self.assertTrue(docs_path.is_file(), docs_path)
        docs = json.loads(docs_path.read_text(encoding='utf-8'))
        self.assertGreaterEqual(len(docs), 100)
        for doc in docs[:5]:
            path = ROOT / doc['arquivo']
            self.assertTrue(path.is_file(), path)
            proof = PROVAS / f"reconciliacao-{doc['slug']}.json"
            self.assertTrue(proof.is_file(), proof)
            pub = json.loads(proof.read_text(encoding='utf-8'))
            self.assertTrue(pub['cobertura_texto']['equivalente'])

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
                self.assertEqual(meta['norma_numero'], doc['norma']['numero'])
                self.assertEqual(meta['norma_data'], doc['norma']['data'])
                self.assertIs(meta['vigencia_certificada'], False)
                self.assertIn('não certifica vigência', body)
                self.assertNotRegex(body, r'<<\s*(ANEXO|TABELA)\s*>>')
                proof = self.proofs[slug]
                self.assertTrue(proof['cobertura_texto']['equivalente'])
                published = json.loads(
                    (PROVAS / f'reconciliacao-{slug}.json').read_text(encoding='utf-8')
                )
                self.assertTrue(published['cobertura_texto']['equivalente'])
                cat = next(r for r in CATALOGO['amostras_issue'] if r['numero'] == doc['norma']['numero'])
                self.assertEqual(cat['senado_id'], doc['senado_id'])
                self.assertEqual(cat['estado'], 'publicado')
                self.assertEqual(cat['caminho'], doc['arquivo'])


if __name__ == '__main__':
    unittest.main()
